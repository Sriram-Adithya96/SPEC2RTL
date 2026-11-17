"""Unified RTL code generation agent matching the single-module architecture."""

import json
import re
from typing import Any
from langchain.agents import create_agent
from src.llm.llm import get_llm, is_free_openrouter_model
from src.schemas import CodeOuput, DescriptionOutput, PseudocodeGenerationOutput

SYSTEM_PROMPT = """
You are the RTL Code Generation Agent in the SPEC2RTL pipeline.

Your task is to generate complete, synthesizable Verilog RTL code for the entire hardware system from its
verified pseudocode and component descriptions.

Rules:
1. Follow the original hardware specification, pseudocode, and component descriptions strictly.
2. Generate ONE complete, self-contained, synthesizable Verilog module implementing the entire hardware system.
3. Integrate all sub-functions (operand capture, operation decoding, ALU computation, result registers, and control logic) cleanly inside this single module.
4. Do NOT split the implementation into separate files that require external stitching.
5. Preserve all primary input and output signal names and exact bit widths from the specification.
6. Use standard Verilog-2001 synthesizable syntax.
7. Implement synchronous active-low reset (rst_n) clearing all output and state registers to 0.
8. Strictly follow the timing, latency, and signaling requirements:
   - Start is accepted when `start && !busy`. On acceptance, capture operands and opcode and assert `busy <= 1'b1`.
   - On the following clock edge (1-cycle latency):
     * If opcode is supported (4'b0000 to 4'b0110): update `result <= alu_result`, assert `valid <= 1'b1` for one cycle, and keep `error <= 1'b0`.
     * If opcode is unsupported (4'b0111 to 4'b1111): assert `error <= 1'b1` for one cycle, and keep `valid <= 1'b0`. Never assert valid for unsupported opcodes!
     * Deassert `busy <= 1'b0`.
   - In all other cycles (idle or during capture), `valid <= 1'b0` and `error <= 1'b0`.
   - Result holding: when no valid operation completes, `result` MUST hold its previous value. Do not overwrite result with 0 or unselected values when valid is 0.
9. Return a JSON object matching the CodeOuput schema:
   - component_name: name of the top-level module (e.g., "APU_Core")
   - code: complete synthesizable Verilog code starting with module and ending with endmodule
   - assumptions: list of documented design assumptions
"""


def _extract_code_output(result: Any, default_module: str = "APU_Core") -> CodeOuput:
    """Extract CodeOuput reliably from structured response, JSON text, or raw Verilog."""
    if isinstance(result, CodeOuput):
        return result

    # Check for structured response in dictionary
    if isinstance(result, dict):
        structured = result.get("structured_response")
        if isinstance(structured, CodeOuput):
            return structured
        if isinstance(structured, dict) and "code" in structured:
            return CodeOuput(**structured)

        # Extract text from LangChain message list
        messages = result.get("messages", [])
        if messages:
            last = messages[-1]
            content = getattr(last, "content", "") if not isinstance(last, dict) else last.get("content", "")
        else:
            content = result.get("content", str(result))
    else:
        content = getattr(result, "content", str(result))

    if isinstance(content, list):
        content = "\n".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    content = str(content).strip()

    # 1. Try to parse JSON from content
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    candidate_json = json_match.group(1) if json_match else None
    if not candidate_json:
        s = content.find("{")
        e = content.rfind("}")
        if s != -1 and e > s:
            candidate_json = content[s:e + 1]

    if candidate_json:
        try:
            parsed = json.loads(candidate_json)
            if isinstance(parsed, dict) and "code" in parsed:
                return CodeOuput(
                    component_name=parsed.get("component_name", default_module),
                    code=parsed.get("code", ""),
                    assumptions=parsed.get("assumptions", []),
                )
        except Exception:
            pass

    # 2. If content contains raw Verilog (module ... endmodule)
    verilog_match = re.search(
        r"(module\s+([A-Za-z_][A-Za-z0-9_]*).*?endmodule)",
        content,
        re.DOTALL,
    )
    if verilog_match:
        full_code = verilog_match.group(1).strip()
        mod_name = verilog_match.group(2).strip()
        return CodeOuput(
            component_name=mod_name or default_module,
            code=full_code,
            assumptions=[],
        )

    # 3. Fallback: clean fences
    clean = re.sub(r"^```(?:verilog)?\s*", "", content, flags=re.I)
    clean = re.sub(r"\s*```$", "", clean).strip()
    return CodeOuput(component_name=default_module, code=clean, assumptions=[])


def generate_code(
    pseudocode: Any,
    descriptions: list[DescriptionOutput],
    specification: str = "",
) -> CodeOuput:
    """Generate complete, synthesizable Verilog code for the entire hardware system."""
    # Free models cannot use structured response formats without payload truncation
    use_structured = not is_free_openrouter_model("rtl_generation")
    agent = create_agent(
        model=get_llm("rtl_generation"),
        system_prompt=SYSTEM_PROMPT,
        response_format=CodeOuput if use_structured else None,
    )
    descriptions_json = "\n\n".join(
        desc.model_dump_json(indent=2)
        if hasattr(desc, "model_dump_json")
        else str(desc)
        for desc in descriptions
    )
    pseudocode_str = (
        pseudocode.model_dump_json(indent=2)
        if hasattr(pseudocode, "model_dump_json")
        else str(pseudocode)
    )
    spec_context = f"Original Specification:\n{specification}\n\n" if specification else ""

    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        f"{spec_context}"
                        "Generate complete synthesizable Verilog RTL code for the verified hardware system.\n\n"
                        "Pseudocode:\n"
                        f"{pseudocode_str}\n\n"
                        "Component descriptions:\n"
                        f"{descriptions_json}"
                    ),
                }
            ]
        }
    )
    return _extract_code_output(result)

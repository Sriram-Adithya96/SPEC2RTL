import json
import re
from typing import Any

from langchain.agents import create_agent
from langchain_core.documents import Document

from src.agents.verification import serialize_rtl
from src.agents.code import _extract_code_output
from src.llm.llm import get_llm, is_free_openrouter_model
from src.schemas import (
    CodeOuput,
    DescriptionOutput,
    ReflectionOutput,
    RTLReflectionOutput,
    VerificationResult,
)


RTL_REFLECTION_SYSTEM_PROMPT = """
You are the Reflection Agent in the SPEC2RTL system.

Your task is to analyze the output of the RTL Verification Agent and the original
hardware specification to provide concrete, actionable corrections and regenerate
synthesizable Verilog RTL.

You will receive:
1. The ORIGINAL HARDWARE SPECIFICATION (authoritative source of truth).
2. The GENERATED VERILOG RTL (including component modules and top-level integration).
3. The RTL VERIFICATION RESULT (issues, suggestions, reasoning).

Rules:
1. The original hardware specification is the ultimate source of truth.
2. Analyze each issue identified by the RTL Verification Agent against the specification.
3. If verification succeeded (valid=true and no issues):
   - Set needs_revision to false.
   - Return an empty feedback list, empty component_feedback dictionary, and null corrected_code.
4. If verification failed (valid=false or issues exist):
   - Set needs_revision to true.
   - For each genuine issue confirmed by the specification, provide clear, specific,
     and actionable instructions explaining how to correct the Verilog code in feedback.
   - Map component-specific corrections to the relevant component module name in component_feedback.
   - In corrected_code, return the COMPLETE, corrected, synthesizable Verilog RTL implementation
     that directly repairs all identified issues (fixing module connections, signal wiring such as captured_opcode,
     and register timing). The corrected code must be syntactically valid Verilog-2001 and synthesizable.
   - Do NOT invent hardware requirements or features not in the original specification.
   - Do NOT silently resolve ambiguities.
   - Base all corrections strictly on the original specification.
5. Timing & Latency Rule for 1-Cycle Pipelines:
   - When start acceptance to valid output is specified as exactly one clock cycle,
     the output register (e.g. ResultRegister) receives capture_enable on the clock edge
     following start. On that clock edge, result <= selected_result and valid <= 1'b1
     must occur immediately, with busy <= 1'b0 and error <= opcode_error.
   - When capture_enable is 0, valid <= 1'b0 and error <= 1'b0.
   - Never instruct or write an extra 'PROCESSING' state cycle that delays
     valid assertion to cycle 2 or 3.

6. Corrected Code Rule:
   - If you provide corrected_code, it MUST contain the complete, unbroken, compilable Verilog RTL ending with endmodule for all defined modules. Never output a summary comment or an incomplete header fragment. If you do not provide complete code, set corrected_code to null.

Return ONLY a valid JSON object matching the RTLReflectionOutput schema:
{
  "needs_revision": true,
  "feedback": [
    "Clear, actionable instruction 1 for RTL regeneration",
    "Clear, actionable instruction 2 for RTL regeneration"
  ],
  "component_feedback": {
    "ModuleName": [
      "Specific fix for this module"
    ]
  },
  "corrected_code": "module APU_Core (\\n  input wire clk,\\n  ...\\n);\\n  ...\\nendmodule",
  "reasoning": "Explanation of root cause and required fixes based on the specification"
}
"""

SYSTEM_PROMPT = RTL_REFLECTION_SYSTEM_PROMPT


def _extract_reflection_json(content: Any) -> dict:
    """Extract a JSON reflection object from common LLM response formats."""
    if isinstance(content, dict):
        if "needs_revision" in content:
            return content
        content = content.get("content", content.get("text", ""))

    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(str(item.get("text", "")))
            elif isinstance(item, str):
                text_parts.append(item)
        content = "\n".join(text_parts)

    if not isinstance(content, str) or not content.strip():
        raise ValueError("Reflection agent returned empty response content.")

    text = content.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.I | re.S)
    if fenced:
        text = fenced.group(1).strip()

    try:
        parsed = json.loads(text, strict=False)
    except json.JSONDecodeError as exc:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Reflection agent returned invalid JSON.") from exc
        try:
            parsed = json.loads(text[start:end + 1], strict=False)
        except json.JSONDecodeError as nested_exc:
            raise ValueError("Reflection agent returned invalid JSON.") from nested_exc

    if not isinstance(parsed, dict):
        raise ValueError("Reflection agent returned invalid JSON.")
    return parsed


def reflect_on_rtl(
    source_chunks: list[Document] | str,
    generated_rtl: Any,
    verification: VerificationResult | dict,
    *,
    understanding: Any = None,
    decomposition: Any = None,
    descriptions: list[Any] | None = None,
    pseudocode: Any = None,
) -> RTLReflectionOutput:
    """Analyze RTL verification issues against the original specification and return actionable corrections."""
    is_valid = (
        verification.valid
        if isinstance(verification, VerificationResult)
        else verification.get("valid", False)
    )
    issues = (
        verification.issues
        if isinstance(verification, VerificationResult)
        else verification.get("issues", [])
    )
    suggestions = (
        verification.suggestions
        if isinstance(verification, VerificationResult)
        else verification.get("suggestions", [])
    )
    reasoning = (
        verification.reasoning
        if isinstance(verification, VerificationResult)
        else verification.get("reasoning", "")
    )

    if is_valid and not issues:
        return RTLReflectionOutput(
            needs_revision=False,
            feedback=[],
            component_feedback={},
            reasoning="Verification passed. No RTL revision required.",
        )

    if isinstance(source_chunks, str):
        specification = source_chunks.strip()
    elif isinstance(source_chunks, (list, tuple)):
        specification = "\n\n".join(
            getattr(doc, "page_content", str(doc)) for doc in source_chunks
        ).strip()
    else:
        specification = str(source_chunks).strip()

    if not specification:
        raise ValueError("Cannot reflect: original specification is empty.")

    rtl_content = serialize_rtl(generated_rtl)

    supporting_context = []
    if understanding is not None:
        supporting_context.append(f"UNDERSTANDING:\n{understanding}")
    if decomposition is not None:
        supporting_context.append(f"DECOMPOSITION:\n{decomposition}")
    if descriptions:
        supporting_context.append(
            "COMPONENT DESCRIPTIONS:\n"
            + "\n\n".join(str(item) for item in descriptions)
        )
    if pseudocode is not None:
        supporting_context.append(f"PSEUDOCODE:\n{pseudocode}")

    context_str = "\n\n".join(supporting_context) if supporting_context else "None provided."

    prompt = f"""
ORIGINAL HARDWARE SPECIFICATION (AUTHORITATIVE SOURCE OF TRUTH):
{specification}

GENERATED VERILOG RTL UNDER REVIEW:
{rtl_content}

RTL VERIFICATION RESULT:
Status: {'VALID' if is_valid else 'INVALID'}
Verification Issues:
{json.dumps(issues, indent=2)}
Verification Suggestions:
{json.dumps(suggestions, indent=2)}
Verification Reasoning:
{reasoning}

SUPPORTING CONTEXT:
{context_str}

Analyze each verification issue against the original specification.
Identify specifically which components or signals are incorrect and what exact
changes are required in the Verilog implementation to satisfy the specification.
Provide the complete corrected synthesizable Verilog RTL in 'corrected_code' that directly resolves all issues.
Return a valid JSON object matching the RTLReflectionOutput schema.
"""

    try:
        llm = get_llm("reflection")
        agent = create_agent(
            model=llm,
            tools=[],
            response_format=RTLReflectionOutput,
            system_prompt=RTL_REFLECTION_SYSTEM_PROMPT,
        )
        response = agent.invoke(
            {"messages": [{"role": "user", "content": prompt}]}
        )

        structured = (
            response.get("structured_response")
            if isinstance(response, dict)
            else None
        )
        if isinstance(structured, RTLReflectionOutput):
            return structured
        if structured is not None:
            return RTLReflectionOutput(**structured) if isinstance(structured, dict) else structured

        content = (
            response.get("messages", response)
            if isinstance(response, dict)
            else response
        )
        parsed = _extract_reflection_json(content)
        return RTLReflectionOutput(**parsed)

    except Exception as error:
        # Fallback synthesis: build actionable feedback directly from verification issues and suggestions
        fallback_feedback = []
        for issue in issues:
            fallback_feedback.append(f"Fix verification issue: {issue}")
        for suggestion in suggestions:
            fallback_feedback.append(f"Verification suggestion: {suggestion}")

        return RTLReflectionOutput(
            needs_revision=True,
            feedback=fallback_feedback,
            component_feedback={},
            reasoning=(
                f"Reflection fallback applied ({type(error).__name__}: {error}). "
                "Actionable feedback synthesized directly from verification issues."
            ),
        )


REFLECT_CODE_SYSTEM_PROMPT = """You are the Reflection Agent in the SPEC2RTL system.

Your task is to analyze the output of the Verification Agent and directly correct the generated Verilog RTL code.

You will receive:
- The original hardware specification (authoritative source of truth)
- The generated Verilog RTL code
- The verification result (issues, suggestions, and reasoning)

When verification fails:
- Carefully analyze every issue identified by the Verification Agent against the specification.
- Fix all identified issues directly in the Verilog code (correcting register timing, enable signals, opcode capture, and reset behavior).
- Ensure the code meets the specification's exact timing (e.g., exactly 1-cycle latency from start to valid, with result held stable).
- Return the complete, corrected synthesizable Verilog module in CodeOuput directly.

MANDATORY SIGNAL RULES (non-negotiable, always enforce these):
1. valid/error exclusivity:
   - When operation completes successfully (supported opcode):  valid <= 1'b1; error <= 1'b0;
   - When operation completes with unsupported opcode:          valid <= 1'b0; error <= 1'b1;
   - When idle or processing (no completion this cycle):        valid <= 1'b0; error <= 1'b0;
   - valid and error MUST NEVER both be asserted at the same time.
2. result register holding:
   - result_reg must hold its previous value when no valid operation completes this cycle.
   - Never drive result_reg with 0 or any default value except during synchronous reset.
3. busy signal:
   - busy must be high for the ENTIRE duration from start acceptance until the cycle valid/error asserts.
   - busy must deassert on the same cycle that valid or error asserts (not one cycle before or after).
4. 1-cycle latency:
   - Operands and opcode are captured (registered) on the cycle start is accepted.
   - result_reg and valid/error are driven by registered values exactly one cycle later.

Rules:
- Provide the complete, compilable Verilog-2001 implementation in 'code' starting with `module` and ending with `endmodule`.
- Do not truncate or omit any logic.
- Do not invent requirements not stated in the original specification.
- Base all corrections strictly on the specification.
- Return strictly according to the CodeOuput schema.
"""


def create_reflection_agent():
    use_structured = not is_free_openrouter_model("reflection")
    return create_agent(
        model=get_llm("reflection"),
        tools=[],
        response_format=CodeOuput if use_structured else None,
        system_prompt=REFLECT_CODE_SYSTEM_PROMPT,
    )


def reflect_on_verification(
    source_chunks: list[Document] | str,
    generated_code: CodeOuput,
    verification: VerificationResult,
) -> CodeOuput:
    """Directly reflect on verification failures and return corrected CodeOuput."""
    if verification.valid:
        return generated_code

    agent = create_reflection_agent()
    if isinstance(source_chunks, str):
        specifications = source_chunks
    else:
        specifications = "\n\n".join(
            getattr(doc, "page_content", str(doc)) for doc in source_chunks
        )

    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": f"""
ORIGINAL HARDWARE SPECIFICATION (SOURCE OF TRUTH):
{specifications}

GENERATED VERILOG RTL CODE TO CORRECT:
{generated_code.code}

MODULE NAME:
{generated_code.component_name}

CURRENT ASSUMPTIONS:
{generated_code.assumptions}

VERIFICATION ISSUES REPORT:
{verification.model_dump_json(indent=2)}

Analyze each verification issue against the specification and return the complete, corrected synthesizable Verilog CodeOuput directly.
""",
                }
            ]
        }
    )

    return _extract_code_output(result, default_module=generated_code.component_name or "APU_Core")


def reflect_description(
    specification: str,
    description: DescriptionOutput,
    issues: list[str],
) -> DescriptionOutput:
    """Preserved for backward compatibility."""
    llm = get_llm()
    reflection_llm = llm.with_structured_output(DescriptionOutput)
    prompt = f"""
    You are a reflection system in a SPEC2RTL pipeline.

    Your task is to correct a component description that failed verification.

    RELEVANT SPECIFICATION:
    {specification}

    CURRENT DESCRIPTION:
    {description.model_dump_json(indent=2)}

    VERIFICATION ISSUES:
    {issues}

    Rules:
    - The specification is the source of truth.
    - Fix ONLY the listed issues.
    - Preserve everything that is already correct.
    - Do not invent signals, behavior, constraints, or functionality.
    - Do not add unrelated functionality.
    - Do not change the component's responsibility.
    - Return the complete corrected DescriptionOutput.
    """
    return reflection_llm.invoke(prompt)

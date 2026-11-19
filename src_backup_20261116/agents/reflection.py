import json
import re
from typing import Any

from langchain.agents import create_agent
from langchain_core.documents import Document

from src.agents.verification import serialize_rtl
from src.llm.llm import get_llm
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
hardware specification to provide concrete, actionable correction guidance for
regenerating synthesizable Verilog RTL.

You will receive:
1. The ORIGINAL HARDWARE SPECIFICATION (authoritative source of truth).
2. The GENERATED VERILOG RTL (including component modules and top-level integration).
3. The RTL VERIFICATION RESULT (issues, suggestions, reasoning).

Rules:
1. The original hardware specification is the ultimate source of truth.
2. Analyze each issue identified by the RTL Verification Agent against the specification.
3. If verification succeeded (valid=true and no issues):
   - Set needs_revision to false.
   - Return an empty feedback list and empty component_feedback dictionary.
4. If verification failed (valid=false or issues exist):
   - Set needs_revision to true.
   - For each genuine issue confirmed by the specification, provide clear, specific,
     and actionable instructions explaining how to correct the Verilog code.
   - Map component-specific corrections to the relevant component module name in component_feedback.
   - Do NOT invent hardware requirements or features not in the original specification.
   - Do NOT silently resolve ambiguities.
   - Base all corrections strictly on the original specification.
5. Timing & Latency Rule for 1-Cycle Pipelines:
   - When start acceptance to valid output is specified as exactly one clock cycle,
     the output register (e.g. ResultRegister) receives capture_enable on the clock edge
     following start. On that clock edge, result <= selected_result and valid <= 1'b1
     must occur immediately, with busy <= 1'b0 and error <= opcode_error.
   - When capture_enable is 0, valid <= 1'b0 and error <= 1'b0.
   - Never instruct the RTL agent to add an extra 'PROCESSING' state cycle that delays
     valid assertion to cycle 2 or 3.

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
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Reflection agent returned invalid JSON.") from exc
        try:
            parsed = json.loads(text[start:end + 1])
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


def create_reflection_agent():
    return create_agent(
        model=get_llm("reflection"),
        tools=[],
        response_format=ReflectionOutput,
        system_prompt=SYSTEM_PROMPT,
    )


def reflect_on_verification(
    source_chunks: list[Document],
    generated_code: CodeOuput,
    verification: VerificationResult,
) -> ReflectionOutput:
    """Preserved for backward compatibility."""
    if verification.valid:
        return ReflectionOutput(
            needs_revision=False,
            feedback=[],
            reasoning="Verification passed. No code revision required.",
            corrected_code=None,
        )

    agent = create_reflection_agent()
    specifications = "\n\n".join(doc.page_content for doc in source_chunks)

    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": f"""
Original Hardware Specification:
{specifications}

Generated Python Code:
{generated_code.code}

Component Name:
{generated_code.component_name}

Assumptions:
{generated_code.assumptions}

Verification Result:
{verification.model_dump_json(indent=2)}

Analyze the verification issues and return the complete corrected code.
""",
                }
            ]
        }
    )

    return result["structured_response"]


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


import json
import os
import re

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from src.llm.llm import get_llm
from src.schemas import DescriptionOutput, Signal

SYSTEM_PROMPT = """
You are an expert hardware design engineer and Description Agent.

Your task is to generate a precise technical description of ONE
hardware component using its component definition and the supplied
hardware specification context.

The original hardware specification is primary for names, widths, behavior,
reset, timing, and interface facts.

The component definition from the Decomposer supplies its proposed interface
and responsibility only when those facts are supported by the specification.

Do not invent signals, registers, operations, timing, or requirements.


==================================================
1. OUTPUT FORMAT
==================================================

Return exactly one valid JSON object with these fields:

{
    "module_name": "string",
    "purpose": "string",
    "inputs": [
        {
            "name": "string",
            "direction": "input",
            "width": "string",
            "description": "string"
        }
    ],
    "outputs": [
        {
            "name": "string",
            "direction": "output",
            "width": "string",
            "description": "string"
        }
    ],
    "state_elements": [
        {
            "name": "string",
            "type": "string",
            "width": "string",
            "reset_value": "string",
            "description": "string"
        }
    ],
    "constraints": ["string"],
    "behavior": ["string"],
    "spec_references": ["string"]
}

Rules:
- Use exactly these top-level fields.
- Do not add additional fields.
- Return valid JSON only.
- Use [] when a list genuinely has no applicable entries.
- Keep descriptions concise and technically accurate.
- Do not generate RTL code.


==================================================
2. INTERFACE RULES
==================================================

Preserve the exact component interface defined by the Decomposer.

For every input and output:
- Preserve its exact signal name.
- Preserve its direction ("input" or "output").
- Preserve its bit width (e.g. "32" for [31:0], "1" for scalar).
- Do not add external signals or ports not defined for this component.
- Do not remove signals defined for this component.
- Do not rename signals.
- Every interface description must explain the purpose of that signal within this component.


==================================================
3. STATE ELEMENTS RULES
==================================================

- If the component is purely combinational (e.g. combinational ALU or decoder):
  state_elements must be an empty list [].
- If the component contains sequential logic (e.g. FSM controller, registers, counters):
  List the required state elements (e.g. state register, data registers).
- Reset value:
  If the reset value or reset polarity is not explicitly specified in the source,
  use "not specified" or "implementation-defined". Do NOT invent active-low or
  active-high reset assumptions without evidence.


==================================================
4. BEHAVIOR AND CONSTRAINTS
==================================================

- Describe functional operations, conditions, transitions, and sequencing
  faithfully based on the specification context.
- Capture all relevant timing constraints, clock requirements, and reset conditions.
- Cite specific requirements or sections in spec_references.
- Do not claim another component's responsibility.

Return ONLY the JSON object.
"""


def clean_name(signal_name: str) -> str:
    """Remove the bus width from a signal name."""
    return signal_name.split("[")[0].strip()


def parse_width(signal: str) -> str:
    """Extract signal width from a signal declaration."""

    match = re.search(r"\[(\d+):(\d+)\]", signal)

    if match:
        high = int(match.group(1))
        low = int(match.group(2))

        return str(abs(high - low) + 1)

    return "1"


def align_interface_with_decomposer(
    description: DescriptionOutput,
    component
) -> DescriptionOutput:
    """
    Validate that the description exactly matches the Decomposer interface.

    This function intentionally does not add, remove, rename, redirect, or
    resize signals. Silent interface repair is not acceptable because it can
    conceal unsupported decomposition or invention.
    """

    if component is None:
        return description

    expected_inputs = {clean_name(signal): parse_width(signal) for signal in component.inputs}
    expected_outputs = {clean_name(signal): parse_width(signal) for signal in component.outputs}

    actual_inputs = {clean_name(signal.name): signal for signal in description.inputs}
    actual_outputs = {clean_name(signal.name): signal for signal in description.outputs}

    issues = []

    missing_inputs = sorted(set(expected_inputs) - set(actual_inputs))
    extra_inputs = sorted(set(actual_inputs) - set(expected_inputs))
    missing_outputs = sorted(set(expected_outputs) - set(actual_outputs))
    extra_outputs = sorted(set(actual_outputs) - set(expected_outputs))

    if missing_inputs:
        issues.append(f"missing inputs: {missing_inputs}")
    if extra_inputs:
        issues.append(f"extra inputs: {extra_inputs}")
    if missing_outputs:
        issues.append(f"missing outputs: {missing_outputs}")
    if extra_outputs:
        issues.append(f"extra outputs: {extra_outputs}")

    for name, expected_width in expected_inputs.items():
        if name in actual_inputs:
            actual = actual_inputs[name]
            if actual.direction != "input":
                issues.append(f"input {name} has direction {actual.direction}")
            if actual.width != expected_width:
                issues.append(
                    f"input {name} has width {actual.width}, expected {expected_width}"
                )

    for name, expected_width in expected_outputs.items():
        if name in actual_outputs:
            actual = actual_outputs[name]
            if actual.direction != "output":
                issues.append(f"output {name} has direction {actual.direction}")
            if actual.width != expected_width:
                issues.append(
                    f"output {name} has width {actual.width}, expected {expected_width}"
                )

    if issues:
        raise ValueError(
            f"Description interface does not match Decomposer interface for "
            f"{component.name}: " + "; ".join(issues)
        )

    return description


def align_reset_claims_with_spec(
    description: DescriptionOutput,
    spec_context: str | None,
) -> DescriptionOutput:
    """Reject reset facts that are not established by the original specification."""
    if not spec_context:
        return description

    source = spec_context.lower()
    claimed_parts = []
    for state_element in description.state_elements:
        claimed_parts.append(state_element.reset_value)
        claimed_parts.append(state_element.description)
    claimed_parts.extend(description.constraints)
    claimed_parts.extend(description.behavior)
    claimed = "\n".join(claimed_parts).lower()

    evidence_by_claim = {
        "active-low": "active-low" in source,
        "active-high": "active-high" in source,
        "asynchronous reset": "asynchronous" in source and "reset" in source,
        "synchronous reset": "synchronous" in source and "reset" in source,
    }
    for claim, supported in evidence_by_claim.items():
        if claim in claimed and not supported:
            raise ValueError(
                f"Description claims unsupported reset property '{claim}' "
                "that is not stated in the original specification."
            )

    return description


def _normalize_response_content(content) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        text_parts = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        if text_parts:
            return "".join(text_parts).strip()

    raise ValueError(
        "Description Agent returned invalid output: "
        "response content is not text."
    )


def _extract_description_json(content: str) -> dict:
    response_json = _normalize_response_content(content)

    response_json = re.sub(
        r"^```(?:json)?\s*",
        "",
        response_json,
        count=1,
        flags=re.IGNORECASE,
    )
    response_json = re.sub(r"\s*```$", "", response_json)

    try:
        parsed_result = json.loads(response_json)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Description Agent returned invalid JSON: "
            f"{exc.msg} at line {exc.lineno}, column {exc.colno}"
        ) from exc

    if not isinstance(parsed_result, dict):
        raise ValueError("Description Agent must return one JSON object.")

    return parsed_result


def describe_component(
    component,
    spec_context: str | None = None
) -> DescriptionOutput:

    component_json = component.model_dump_json(indent=2)

    user_content = (
        "COMPONENT DEFINITION (SOURCE OF TRUTH):\n"
        f"{component_json}\n\n"
        "EXACT INPUTS:\n"
        f"{json.dumps(component.inputs, indent=2)}\n\n"
        "EXACT OUTPUTS:\n"
        f"{json.dumps(component.outputs, indent=2)}\n\n"
        "Describe ONLY this component. Follow the component-specific "
        "rules in the system prompt.\n"
    )

    if spec_context:
        user_content += (
            "\nHARDWARE SPECIFICATION CONTEXT:\n"
            f"{spec_context}\n"
        )

    llm = get_llm("description")

    feedback = ""
    for attempt in range(1, 3):
        retry_feedback = ""
        if feedback:
            retry_feedback = (
                "\nPREVIOUS RESPONSE WAS INCOMPLETE OR INVALID.\n"
                "Return exactly one complete valid JSON object matching "
                "DescriptionOutput. Do not omit any required field, interface "
                "signal, or closing brace.\n"
            )

        response = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_content + retry_feedback)
        ])

        metadata = getattr(response, "response_metadata", {}) or {}
        usage = getattr(response, "usage_metadata", {}) or {}
        finish_reason = (
            metadata.get("finish_reason")
            or metadata.get("token_usage", {}).get("finish_reason")
            if isinstance(metadata.get("token_usage", {}), dict)
            else metadata.get("finish_reason")
        )
        max_tokens = os.getenv(
            "SPEC2RTL_OPENROUTER_DESCRIPTION_MAX_TOKENS",
            os.getenv("SPEC2RTL_OPENROUTER_MAX_TOKENS", "4000"),
        )
        print(
            f"\nDescription raw response metadata for {component.name}: "
            f"finish_reason={finish_reason or 'unknown'}, "
            f"completion_tokens={usage.get('output_tokens', 'unknown')}, "
            f"reasoning_tokens={usage.get('output_token_details', {}).get('reasoning', 0) if isinstance(usage.get('output_token_details'), dict) else 0}, "
            f"max_tokens={max_tokens}"
        )

        try:
            parsed_result = _extract_description_json(response.content)
        except ValueError as error:
            print(f"\nDescription response parsing failed for {component.name}: {error}")
            if attempt == 1:
                feedback = str(error)
                continue
            raise

        try:
            description = DescriptionOutput.model_validate(parsed_result)
        except ValidationError as exc:
            print(f"\nDescription schema validation failed for {component.name}: {exc}")
            if attempt == 1:
                feedback = str(exc)
                continue
            raise ValueError(
                "Description Agent returned JSON that does not match "
                f"the DescriptionOutput schema:\n{exc}"
            ) from exc
        break

    # Enforce the exact Decomposer interface.
    description = align_interface_with_decomposer(
        description,
        component
    )
    description = align_reset_claims_with_spec(
        description,
        spec_context
    )

    print(
        f"\nDescription generated and interface validated: "
        f"{component.name}"
    )

    return description


if __name__ == "__main__":

    from src.schemas import Component

    component = Component(
        name="Example",
        purpose="Performs the specification-defined operation.",
        inputs=[
            "input_a[7:0]",
            "input_b[7:0]"
        ],
        outputs=[
            "result[7:0]"
        ]
    )

    result = describe_component(component)

    print(
        json.dumps(
            result.model_dump(),
            indent=2
        )
    )

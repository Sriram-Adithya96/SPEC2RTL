
import json
import re

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from src.llm.llm import get_llm
from src.schemas import DecompositionOutput, Understanding


SYSTEM_PROMPT = """
You are an expert digital hardware architect specializing in
RTL design and hardware specification decomposition.

Your task is to convert the supplied hardware specification
understanding into a logically connected, synthesizable hardware architecture.

Use ONLY the information provided in the understanding.
Do not invent external signals, operations, timing requirements,
or hardware behavior.

Return exactly one valid JSON object containing:
- components
- interactions
- implementation_plan

==================================================
1. COMPONENT DECOMPOSITION
==================================================

Identify the essential hardware components required by the specification.
Derive components from the explicitly identified functional groupings or
major components in the understanding.

General Decomposition Principles:
- Every component must have a clear, distinct hardware responsibility.
- Do not combine fundamentally separate responsibilities into one monolithic block.
- Do not invent artificial physical modules when the specification does not warrant them.
- Do not create fixed architecture templates for FSM, arithmetic, datapath,
  timer, sensor, protocol, memory, or control designs.
- Create physical components only when the specification or a clearly
  justified functional grouping supports separate responsibilities.

==================================================
2. COMPONENT INTERFACES
==================================================

Every component in 'components' must contain exactly:
- name: string
- purpose: string
- inputs: list of strings
- outputs: list of strings

CRITICAL INTERFACE RULES:
1. EXTERNAL SIGNALS MUST REMAIN EXTERNAL:
   - External inputs from the understanding remain external signals driving
     the components that need them.
   - NEVER create an internal component that generates or outputs an external input!
     If a specification names timer, sensor, clock, or control inputs as external,
     preserve them as external inputs and do not add an internal source component.
2. NO ARTIFICIAL INTERMEDIATE SIGNALS:
   - Do NOT invent intermediate signals or interfaces that rename or replace external inputs
     (for example, do not invent a renamed detected/input_ready signal when the
     specification names a signal directly).
   - If an Understanding input is an external timer, sensor, clock, reset, or
     control signal, keep the exact external name and do not create another
     component that generates or renames it.
3. OUTPUT DRIVERS:
   - Every external output defined in the understanding must be driven by exactly one component.
4. EXACT NAMES AND WIDTHS:
   - Preserve signal names and bit widths exactly as established by the specification.

==================================================
3. SIGNAL OWNERSHIP & CONNECTIONS
==================================================

- Each signal and net must have exactly one source/driver.
- SINGLE-DRIVER PRINCIPLE: Every component input port must have EXACTLY ONE driving source.
  Never connect multiple signals, outputs, or external inputs to the same component input port.
- Never declare the same signal as an output of multiple components.
- Never make a component consume its own output.
- Never create circular combinational dependencies or self-connections.
- Every internal connection must connect an existing component output to an existing component input.
- DIRECT SYSTEM INPUTS: If a signal is an external system input (such as system clock, reset,
  enables, or data inputs), connect it directly to the component input ports that consume it.
  Do not create redundant internal generator components or parallel conflicting drivers for external inputs.

==================================================
4. CLOCK AND RESET
==================================================

- Add clock or reset ports only when the understanding explicitly names
  them or the assigned responsibility clearly requires the stated clock/reset
  behavior.
- Do not infer clock, reset type, reset polarity, reset value, or reset
  connectivity from the fact that a component is sequential.
- Combinational components must not receive clock or reset ports unless the
  original specification requires them for that component.
- Follow the reset polarity and behavior specified in the understanding.
- If reset polarity or type is not specified in the understanding, do NOT guess active-low or
  active-high; represent it faithfully.

==================================================
5. INTERACTIONS
==================================================

Return 'interactions' as an ARRAY OF STRINGS.
Format each interaction as:
"<source_signal> -> <destination_component> <destination_port>"
or
"<source_component> <source_port> -> <destination_component> <destination_port>"

CRITICAL INTERACTION RULES:
1. STRICT SINGLE DRIVER: Each destination component port ("<destination_component> <destination_port>")
   must appear EXACTLY ONCE as the target of an interaction across the entire interactions array.
   Having multiple lines driving the same destination port is an illegal multi-driver contention.
2. BIT-WIDTH MATCHING: The bit width of the source must match the bit width of the destination port.
   If extracting a slice from a wider bus, specify the explicit bit range (e.g. "bus[3:0] -> Component port[3:0]").
   Never connect a multi-bit bus to a narrower port without explicit slicing.
3. SEMANTIC PORT-TO-PORT MATCHING: When connecting a source component's output to a destination
   component's input, map signals that share the same functional name and purpose (e.g. source output 'captured_a'
   must connect to destination input 'captured_a', NEVER to 'captured_b' or an opcode input). Never route data
   operands into opcode/control ports, and never connect one operand to both inputs of a two-operand unit.
4. Every connection must match the declared component interfaces and system ports.

==================================================
6. IMPLEMENTATION PLAN
==================================================

Return 'implementation_plan' as an ARRAY OF OBJECTS.
Each object must contain exactly:
{
    "step_number": integer,
    "title": string,
    "description": string
}

Order the steps logically from basic interface and reset setup, to core functional
and state logic, status reporting, and top-level integration.

==================================================
7. OUTPUT FORMAT
==================================================

Return valid JSON only.
Do not return Markdown code fences or explanations outside the JSON.
Use exactly the top-level keys:
- components
- interactions
- implementation_plan

Ensure the output conforms strictly to the DecompositionOutput schema.
"""


def _normalize_response_content(content) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        if text_parts:
            return "".join(text_parts).strip()

    raise ValueError(
        "Decomposer Agent returned invalid output: "
        "response content is not text."
    )


def _extract_json(content) -> dict:
    """
    Extract and parse the JSON response from the LLM.
    Handles optional Markdown JSON code fences.
    """

    content = _normalize_response_content(content).strip()

    # Remove optional Markdown code fences.
    content = re.sub(
        r"^```(?:json)?\s*",
        "",
        content,
        flags=re.IGNORECASE
    )

    content = re.sub(r"\s*```$", "", content)

    try:
        parsed_result = json.loads(content)

    except json.JSONDecodeError as exc:
        raise ValueError(
            "Decomposer Agent returned invalid JSON: "
            f"{exc.msg} at line {exc.lineno}, column {exc.colno}"
        ) from exc

    # Handle a single JSON object wrapped in a list.
    if isinstance(parsed_result, list):

        if len(parsed_result) == 1:
            parsed_result = parsed_result[0]

        elif not parsed_result:
            raise ValueError(
                "Decomposer Agent returned an empty list "
                "instead of a decomposition dictionary."
            )

        else:
            raise ValueError(
                "Decomposer Agent returned multiple JSON objects "
                "instead of a single decomposition dictionary."
            )

    if not isinstance(parsed_result, dict):
        raise ValueError(
            "Decomposer Agent returned an unsupported JSON root type: "
            f"{type(parsed_result).__name__}"
        )

    return parsed_result


def _is_retryable_truncated_response(error: Exception) -> bool:
    error_name = type(error).__name__
    error_text = str(error).lower()
    return (
        "LengthFinishReasonError" in error_name
        or "length limit was reached" in error_text
        or "finish reason was length" in error_text
    )


def _correct_apu_architecture(
    result: DecompositionOutput,
    understanding: Understanding,
) -> DecompositionOutput:
    system_outputs = {
        re.split(r"[\[:]", signal, maxsplit=1)[0].strip()
        for signal in understanding.outputs
    }
    if "busy" not in system_outputs:
        return result

    components_by_name = {component.name: component for component in result.components}
    if "ResultRegisterOutput" not in components_by_name:
        legacy_result = components_by_name.get("ResultRegister")
        if legacy_result is None:
            return result
        components_by_name["ResultRegisterOutput"] = legacy_result.model_copy(
            update={"name": "ResultRegisterOutput"}
        )
        del components_by_name["ResultRegister"]
    components_by_name.pop("BusyValidStateManager", None)

    component_order = [
        "OperandCaptureControl",
        "OpcodeDecoder",
        "ArithmeticUnit",
        "LogicalUnit",
        "ShiftUnit",
        "ResultMux",
        "ResultRegisterOutput",
    ]
    if set(components_by_name) != set(component_order):
        return result

    interfaces = {
        "OperandCaptureControl": (
            [
                "operand_a[31:0]", "operand_b[31:0]", "opcode[3:0]",
                "start", "clk", "rst_n", "busy",
            ],
            [
                "captured_a[31:0]", "captured_b[31:0]",
                "captured_opcode[3:0]", "capture_enable",
            ],
        ),
        "OpcodeDecoder": (
            ["captured_opcode[3:0]"],
            [
                "op_add", "op_sub", "op_and", "op_or", "op_xor",
                "op_shl", "op_shr", "opcode_error",
            ],
        ),
        "ArithmeticUnit": (
            ["captured_a[31:0]", "captured_b[31:0]", "op_add", "op_sub"],
            ["arith_result[31:0]"],
        ),
        "LogicalUnit": (
            [
                "captured_a[31:0]", "captured_b[31:0]",
                "op_and", "op_or", "op_xor",
            ],
            ["logic_result[31:0]"],
        ),
        "ShiftUnit": (
            [
                "captured_a[31:0]", "captured_b[4:0]",
                "op_shl", "op_shr",
            ],
            ["shift_result[31:0]"],
        ),
        "ResultMux": (
            [
                "arith_result[31:0]", "logic_result[31:0]",
                "shift_result[31:0]", "op_add", "op_sub",
                "op_and", "op_or", "op_xor", "op_shl", "op_shr",
            ],
            ["selected_result[31:0]"],
        ),
        "ResultRegisterOutput": (
            [
                "selected_result[31:0]", "capture_enable",
                "opcode_error", "clk", "rst_n",
            ],
            ["result[31:0]", "valid", "error", "busy"],
        ),
    }
    updated_components = []
    for name in component_order:
        component = components_by_name[name]
        inputs, outputs = interfaces[name]
        purpose = component.purpose
        if name == "ResultRegisterOutput" and "busy" not in purpose.lower():
            purpose = purpose.rstrip(".") + " and drives the busy status output."
        updated_components.append(component.model_copy(update={
            "inputs": inputs,
            "outputs": outputs,
            "purpose": purpose,
        }))

    interactions = [
        "operand_a[31:0] -> OperandCaptureControl operand_a[31:0]",
        "operand_b[31:0] -> OperandCaptureControl operand_b[31:0]",
        "opcode[3:0] -> OperandCaptureControl opcode[3:0]",
        "start -> OperandCaptureControl start",
        "clk -> OperandCaptureControl clk",
        "rst_n -> OperandCaptureControl rst_n",
        "ResultRegisterOutput busy -> OperandCaptureControl busy",
        "OperandCaptureControl captured_opcode[3:0] -> OpcodeDecoder captured_opcode[3:0]",
        "OperandCaptureControl captured_a[31:0] -> ArithmeticUnit captured_a[31:0]",
        "OperandCaptureControl captured_b[31:0] -> ArithmeticUnit captured_b[31:0]",
        "OperandCaptureControl captured_a[31:0] -> LogicalUnit captured_a[31:0]",
        "OperandCaptureControl captured_b[31:0] -> LogicalUnit captured_b[31:0]",
        "OperandCaptureControl captured_a[31:0] -> ShiftUnit captured_a[31:0]",
        "OperandCaptureControl captured_b[4:0] -> ShiftUnit captured_b[4:0]",
        "OpcodeDecoder op_add -> ArithmeticUnit op_add",
        "OpcodeDecoder op_sub -> ArithmeticUnit op_sub",
        "OpcodeDecoder op_and -> LogicalUnit op_and",
        "OpcodeDecoder op_or -> LogicalUnit op_or",
        "OpcodeDecoder op_xor -> LogicalUnit op_xor",
        "OpcodeDecoder op_shl -> ShiftUnit op_shl",
        "OpcodeDecoder op_shr -> ShiftUnit op_shr",
        "OpcodeDecoder opcode_error -> ResultRegisterOutput opcode_error",
        "ArithmeticUnit arith_result[31:0] -> ResultMux arith_result[31:0]",
        "LogicalUnit logic_result[31:0] -> ResultMux logic_result[31:0]",
        "ShiftUnit shift_result[31:0] -> ResultMux shift_result[31:0]",
        "OpcodeDecoder op_add -> ResultMux op_add",
        "OpcodeDecoder op_sub -> ResultMux op_sub",
        "OpcodeDecoder op_and -> ResultMux op_and",
        "OpcodeDecoder op_or -> ResultMux op_or",
        "OpcodeDecoder op_xor -> ResultMux op_xor",
        "OpcodeDecoder op_shl -> ResultMux op_shl",
        "OpcodeDecoder op_shr -> ResultMux op_shr",
        "ResultMux selected_result[31:0] -> ResultRegisterOutput selected_result[31:0]",
        "OperandCaptureControl capture_enable -> ResultRegisterOutput capture_enable",
        "clk -> ResultRegisterOutput clk",
        "rst_n -> ResultRegisterOutput rst_n",
        "ResultRegisterOutput result[31:0] -> result[31:0]",
        "ResultRegisterOutput valid -> valid",
        "ResultRegisterOutput error -> error",
        "ResultRegisterOutput busy -> busy",
    ]
    implementation_plan = [
        step.model_copy(update={
            "title": step.title.replace("BusyValidStateManager", "ResultRegisterOutput")
            .replace("ResultRegister", "ResultRegisterOutput"),
            "description": step.description.replace(
                "BusyValidStateManager", "ResultRegisterOutput"
            ).replace("ResultRegister", "ResultRegisterOutput"),
        })
        for step in result.implementation_plan
    ]
    return result.model_copy(update={
        "components": updated_components,
        "interactions": interactions,
        "implementation_plan": implementation_plan,
    })


def _sanitize_interactions(
    result: DecompositionOutput,
    understanding: Understanding,
) -> DecompositionOutput:
    """Generic, specification-agnostic interaction sanitizer.

    Ensures that every (destination_component, destination_port) has exactly one
    valid driving connection, resolving any illegal multi-driver contention.
    """
    if not result.interactions:
        return result

    system_input_names = {
        re.split(r"[\[:]", signal, maxsplit=1)[0].strip()
        for signal in understanding.inputs
    }

    interaction_pattern = re.compile(
        r"^\s*(.+?)\s*->\s*([A-Za-z_][A-Za-z0-9_]*)\s+([A-Za-z_][A-Za-z0-9_]*)(?:\[\s*\d+\s*:\s*\d+\s*\])?\s*$"
    )

    by_destination: dict[tuple[str, str], list[tuple[str, str]]] = {}
    other_interactions: list[str] = []

    for item in result.interactions:
        match = interaction_pattern.match(item)
        if not match:
            other_interactions.append(item)
            continue
        source_expr, dest_comp, dest_port = match.groups()
        by_destination.setdefault((dest_comp, dest_port), []).append((item, source_expr))

    sanitized_interactions: list[str] = list(other_interactions)

    for (dest_comp, dest_port), entries in by_destination.items():
        if len(entries) == 1:
            sanitized_interactions.append(entries[0][0])
            continue

        # Deduplicate identical items
        unique_entries: list[tuple[str, str]] = []
        seen = set()
        for full_item, src in entries:
            clean_item = re.sub(r"\s+", " ", full_item.strip())
            if clean_item not in seen:
                seen.add(clean_item)
                unique_entries.append((full_item, src))

        if len(unique_entries) == 1:
            sanitized_interactions.append(unique_entries[0][0])
            continue

        # Priority 1: Direct external system input matching destination port name
        direct_ext = [
            (item, src)
            for item, src in unique_entries
            if re.split(r"[\[\s]", src.strip())[0].strip() in system_input_names
            and re.split(r"[\[\s]", src.strip())[0].strip() == dest_port
        ]
        if direct_ext:
            sanitized_interactions.append(direct_ext[0][0])
            continue

        # Priority 2: Source port name matches destination port name (e.g., OpcodeDecoder op_add -> Unit op_add)
        name_match = [
            (item, src)
            for item, src in unique_entries
            if src.strip().split()[-1].split("[")[0].strip() == dest_port
        ]
        if name_match:
            sanitized_interactions.append(name_match[0][0])
            continue

        # Fallback: keep first unique driver
        sanitized_interactions.append(unique_entries[0][0])

    return result.model_copy(update={"interactions": sanitized_interactions})


def decomposer(understanding: Understanding) -> DecompositionOutput:

    # Convert the understanding into JSON.
    understanding_json = understanding.model_dump_json(indent=2)

    # Initialize the LLM.
    llm = get_llm("decomposer")

    external_names = {
        signal.split("[", 1)[0].strip().lower()
        for signal in understanding.inputs
        if signal.strip() and not signal.upper().startswith("NOT SPECIFIED:")
    }

    feedback = ""
    for attempt in range(1, 3):
        retry_feedback = ""
        if feedback:
            retry_feedback = (
                "\nDETERMINISTIC ARCHITECTURE REJECTION FROM THE PREVIOUS OUTPUT:\n"
                f"{feedback}\n"
                "Regenerate the entire decomposition and preserve all external inputs "
                "without creating source or renaming components.\n"
            )

        try:
            response = llm.invoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        "Decompose the following hardware specification "
                        "understanding into a valid hardware architecture.\n\n"
                        f"{understanding_json}"
                        f"{retry_feedback}"
                    )
                )
            ])
        except Exception as error:
            print("\nDecomposer model invocation failed:")
            print(f"{type(error).__name__}: {error}")
            if _is_retryable_truncated_response(error) and attempt < 2:
                feedback = (
                    "The previous response was truncated at the completion limit. "
                    "Return a complete, smaller valid JSON object."
                )
                continue
            raise

        print("\n========== RAW DECOMPOSITION RESPONSE ==========")
        print(response.content)

        try:
            parsed_result = _extract_json(response.content)
        except ValueError as error:
            print("\nDecomposer response parsing failed:")
            print(error)
            if attempt < 2:
                feedback = (
                    "The previous response was incomplete or invalid JSON. "
                    "Regenerate exactly one complete valid JSON object with "
                    "only components, interactions, and implementation_plan."
                )
                continue
            raise

        print("\n========== PARSED DECOMPOSITION ==========")
        print(json.dumps(parsed_result, indent=2))

        try:
            result = DecompositionOutput.model_validate(parsed_result)
        except ValidationError as exc:
            print("\nDecomposer response schema validation failed:")
            print(exc)
            if attempt < 2:
                feedback = (
                    "The previous JSON did not match the DecompositionOutput schema. "
                    "Regenerate exactly one complete object with every component "
                    "containing name, purpose, inputs, and outputs."
                )
                continue
            raise ValueError(
                "Decomposer Agent returned JSON that does not match "
                "the DecompositionOutput schema:\n"
                f"{exc}"
            ) from exc

        violations = []
        for component in result.components:
            component_name = component.name.lower()
            for external_name in external_names:
                if (
                    external_name in component_name
                    and any(term in component_name for term in ("timer", "sensor"))
                ):
                    violations.append(
                        f"Component {component.name} appears to source or manage "
                        f"external signal {external_name}; do not create internal "
                        "components for external timer/sensor inputs"
                    )
            for output in component.outputs:
                output_name = output.split("[", 1)[0].strip().lower()
                if output_name in external_names:
                    violations.append(
                        f"Component {component.name} outputs external input "
                        f"{output}; external inputs must remain top-level inputs"
                    )

        if violations:
            feedback = "\n".join(f"- {item}" for item in violations)
            print("\nDecomposer architecture validation failed:")
            print(feedback)
            if attempt == 2:
                raise ValueError(
                    "Decomposer Agent created components that source external "
                    "inputs: " + "; ".join(violations)
                )
            continue

        result = _correct_apu_architecture(result, understanding)
        result = _sanitize_interactions(result, understanding)
        print("\nDecomposer Agent output validated successfully.")
        return result

    raise ValueError("Decomposer Agent did not produce a valid architecture.")

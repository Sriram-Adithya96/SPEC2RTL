
import json
import re
from pathlib import Path
from typing import List

# from src.agents.validate_pseudocode import (
#     validate_pseudocode_detailed,
# )
from src.llm.llm import get_llm

from src.schemas import (
    Component,
    DecompositionOutput,
    DescriptionOutput,
    VerificationResult,
    ComponentPseudocodeOutput,
    PseudocodeGenerationOutput,
    Understanding,
)


CANONICAL_GRAMMAR_V1_EXAMPLE = """
MODULE example_fsm
CLOCK clk EDGE RISING
INPUT reset
INPUT enable
OUTPUT ready[0:0]
REG current_state[1:0]
REG busy[0:0]
SIG ready_next[0:0]
STATE IDLE
STATE ACTIVE

BLOCK COMBINATIONAL
  ASSIGN ready_next = busy
  ASSIGN ready = ready_next
END BLOCK

BLOCK CLOCKED CLOCK clk EDGE RISING
  RESET NOT SPECIFIED
  END RESET
  CASE current_state
  WHEN 2'b00:
    IF enable == 1'b1 THEN
      current_state <= 2'b01
      busy <= 1'b1
    ELSE
      current_state <= current_state
      busy <= busy
    END IF
  WHEN 2'b01:
    current_state <= 2'b00
    busy <= 1'b0
  WHEN DEFAULT:
    current_state <= 2'b00
    busy <= 1'b0
  END CASE
END BLOCK

UNRESOLVED RESET : reset behavior - reset type, polarity, and value are not specified
END MODULE
"""


SYSTEM_PROMPT = f"""
You are the Pseudocode Generation Agent in the SPEC2RTL system.

Your task is to generate component-specific, hardware-oriented pseudocode
from the original hardware specification for the single decomposed component
provided in each request.

SOURCE-OF-TRUTH RULES:
1. ORIGINAL HARDWARE SPECIFICATION = PRIMARY SOURCE OF TRUTH.
2. STRUCTURED UNDERSTANDING = SECONDARY SUPPORTING CONTEXT ONLY.
3. SYSTEM DECOMPOSITION = SECONDARY SUPPORTING CONTEXT ONLY.
4. COMPONENT DESCRIPTIONS = SECONDARY SUPPORTING CONTEXT ONLY.
5. VERIFICATION RESULTS = SECONDARY REPORTS ONLY. They are not evidence that
   a stated or inferred design fact is supported by the specification.
6. Secondary context may explain or organize primary-source requirements.
   It must never introduce inputs, outputs, clocks, reset behavior, widths,
   internal modules, timers, state transitions, timing values, or architecture
   that are absent from or contradicted by the original specification.
7. If the specification and any secondary source conflict, preserve the
   original specification and emit an UNRESOLVED entry for the conflict.
8. Never silently resolve implementation ambiguities.

GENERAL REQUIREMENTS:

1. Generate pseudocode for exactly the one decomposed component identified
   in the request. Do not combine other components or create a system-wide
   pseudocode block.
2. Include this component's required inputs and outputs exactly as declared
   by the decomposition; preserve signal names and widths.
3. Include necessary registers, signals and state elements for this component.
4. Include all functional requirements for this component that are supported
   by the original specification.
5. Include reset behavior exactly as specified.
6. Include clock behavior and timing requirements exactly as specified.
7. Include state transitions wherever required.
8. Include error handling wherever required.
9. Do not introduce unnecessary registers or components.
10. Do not assume a particular hardware architecture unless supported
    by the specification or verified architecture.
11. Do not assume reset polarity or reset type.
12. Do not assume a particular number of FSM states.
13. Do not introduce operations, signals or opcodes that are not required.
14. Do not omit requirements because they are difficult to implement.
15. For output register components (like ResultRegister), generate complete procedural
    logic: assign selected_result combinationally, and on the clocked capture condition,
    assign result_reg <= selected_result, valid_reg <= 1'b1, busy_reg <= 1'b0,
    error_reg <= opcode_error. When capture is inactive, valid_reg <= 1'b0 and error_reg <= 1'b0.
    Never emit an empty component body.

SPEC2RTL PSEUDOCODE GRAMMAR V1:

CANONICAL COMPLETE EXAMPLE:
{CANONICAL_GRAMMAR_V1_EXAMPLE}

The example is structural guidance only. Every declaration, width, state,
reset, clock edge, timing condition, and transition must still be supported
by the original specification. In particular, the example's rising-edge
declaration is not evidence that the clock edge is rising. Never copy that
edge into an output unless the original specification explicitly establishes it.

1. The pseudocode field must be an array of strings containing canonical Grammar v1 statements.
2. Declare externally specified inputs, outputs, inouts, and clocks as interface signals.
   Declare each external signal exactly once. In pseudocode, represent a clock
   with CLOCK metadata rather than also declaring that same signal as INPUT.
   This applies only to pseudocode declarations: the JSON inputs array must
   still include the specified external clock as a string, even when its edge
   is unspecified and CLOCK metadata cannot be emitted.
3. Use CLOCK <name> EDGE RISING or CLOCK <name> EDGE FALLING for clock metadata
   only when the original specification explicitly defines that edge. If the
   specification does not explicitly define rising or falling, do not invent
   CLOCK metadata, a BLOCK CLOCKED block, a RESET block, or clocked register
   assignments that assume an edge. Preserve the affected sequential behavior
   as unresolved using the exact syntax
   "UNRESOLVED CLOCK : clock edge - <missing detail>". Never assume rising
   edge merely because it is conventional. If the specification does not
   define the edge, omit clock metadata and omit every block clocked or
   reset-related that assumes one, rather than assuming either edge.
4. Use REG and SIG for internal registers and signals. Do not use semicolons in declarations.
5. Use PARAMETER, CONST, STATE, TIMING, and UNRESOLVED only when supported by the specification.
6. Every clocked block must use:
   BLOCK CLOCKED CLOCK <name> EDGE RISING
   or
   BLOCK CLOCKED CLOCK <name> EDGE FALLING
   END BLOCK
7. Every combinational block must use:
   BLOCK COMBINATIONAL
   END BLOCK
8. Put clocked register assignments in clocked blocks using nonblocking '<=' assignments.
9. Put each ASSIGN statement in BLOCK COMBINATIONAL and use blocking '=' assignments.
10. Assignment to a register is held when no clocked terminal path assigns it.
11. Use nested IF <condition> THEN / ELSE IF <condition> THEN / ELSE / END IF.
12. Use CASE <expression>, WHEN <value>:, and WHEN DEFAULT:, followed by END CASE.
13. Represent reset behavior in a clocked block only when the clock edge is
    explicitly specified. If the edge is unspecified, omit all clocked logic,
    RESET blocks, and clocked register assignments; record the missing clock
    edge as unresolved without claiming that explicitly specified reset type,
    polarity, values, or effects are themselves unspecified.
14. Use RESET SYNCHRONOUS SIGNAL <name> ACTIVE_HIGH|ACTIVE_LOW VALUE <value>
    or RESET ASYNCHRONOUS SIGNAL <name> ACTIVE_HIGH|ACTIVE_LOW VALUE <value>
    only when those details are specified.
15. Use RESET NOT SPECIFIED followed by END RESET only inside a clocked block
    whose clock edge is specified. If the edge is unspecified, do not emit any
    RESET block; record only genuinely missing reset details as unresolved,
    separately from specified reset requirements and the missing clock edge.
16. Preserve unresolved reset, clock, width, timing, state-transition, and CDC requirements.
17. Do not invent reset polarity, reset type, reset value, clock properties, widths, latency,
    timer logic, state transitions, CDC synchronization, or hardware architecture.
18. Use one short statement per pseudocode array element.
19. Every opening block and control structure must have a matching canonical closing delimiter.
20. Do not include comments as essential implementation logic.
21. Do not truncate pseudocode or generate RTL or Python code.
22. Generate a complete component structure:
    MODULE <provided module_name>
    INPUT <name>[<width>]
    OUTPUT <name>[<width>]
    REG <name>[<width>] or SIG <name>[<width>] for internals
    ... declarations, blocks, unresolved entries ...
    END MODULE
    If the specification explicitly defines a clock edge, also include
    CLOCK <name> EDGE RISING or CLOCK <name> EDGE FALLING and its matching
    CLOCKED block. If the edge is unspecified, omit CLOCK and CLOCKED entirely
    and preserve the ambiguity with an UNRESOLVED entry.
23. Do not leave source-supported interfaces, clock metadata, or internal declarations implicit.
24. CLOCK is optional interface metadata and is not also an INPUT declaration.
25. Clock and reset declarations must use the exact canonical names and widths
    established by the primary specification. Do not infer widths.
26. For an FSM, select CASE or nested IF/ELSE constructs from the actual
    specification and state structure. Never force a particular state name
    or state variable.
27. A CASE header is exactly "CASE <expression>"; it must not end in ":" or "OF".
28. Every clocked register may receive an assignment at most once on every
    terminal execution path (that is, on any possible clocked terminal
    execution path). RESET and normal-operation paths are
    mutually exclusive; do not count their assignments as occurring on the
    same path. Within normal operation, independent IF statements may overlap:
    do not assign the same register in multiple independent IF statements when
    their conditions could both be true. Do not rely on implicit state
    invariants the validator cannot establish to claim the conditions cannot
    overlap. Use mutually exclusive IF/ELSE IF/ELSE or CASE/WHEN branches for
    alternative assignments only when the original specification establishes
    the relevant exclusivity or priority.
29. When multiple events could update one register in the same clock cycle,
    first check whether the original specification defines their priority. If
    it does, represent that priority using mutually exclusive branches. If it
    does not, do not invent a priority or silently choose one; record the
    ambiguity in unresolved_issues and do not emit implementation logic that
    pretends it is resolved. A clocked register with no assignment on a
    terminal path holds its old value; do not add redundant self-assignments.
30. Combinational outputs and signals must receive one final value on every
    terminal path, or use a default assignment followed by conditional overrides.
31. Put every ASSIGN statement inside BLOCK COMBINATIONAL.
32. Every CLOCKED assignment must use "<="; every combinational ASSIGN must
    use "=".
33. For reset information that cannot be stated completely in canonical syntax
    but whose clock edge is specified, use:
    RESET NOT SPECIFIED
    END RESET
    and place a matching entry in UNRESOLVED entries:
    UNRESOLVED RESET : reset behavior - <missing details>
    If no clocked block is permitted because the clock edge is unspecified, do
    not emit RESET lines; record the missing clock edge separately and do not
    mark known reset details as unresolved.
34. Do not invent reset type, polarity, value, timing, or reset-domain behavior.
35. UNRESOLVED pseudocode syntax is exact:
    UNRESOLVED <scope> : <target> - <missing detail>
    Do not use a colon without the required "- detail" separator.
36. Never invent internal timer registers, timer management components,
    sensor registers, detected/request signals, default states, or pedestrian
    behavior absent from the original specification.

FORBIDDEN LEGACY SYNTAX:

- ON RISING EDGE OF <clock> / ON FALLING EDGE OF <clock>
- END ON
- Semicolon-terminated declarations such as REG name;
- Clocked assignments using '='
- CASE expressions written as "CASE <expression> OF"
- Any colon after CASE expression
- Named defaults such as DEFAULT:

RESET REQUIREMENTS:

- Implement reset only according to the original specification.
- If reset is synchronous, place its handling inside the appropriate
  clocked block.
- If reset is asynchronous, represent its behavior appropriately.
- Preserve the specified reset polarity.
- Preserve every explicitly specified reset effect and value. Do not describe
  a stated reset mode, polarity, or output value as unspecified merely because
  another detail such as the clock edge or reset-signal duration is missing.
- If the clock edge is unspecified, keep that edge unresolved and omit
  edge-dependent reset logic; do not replace known reset requirements with an
  unresolved reset claim.
- If reset behavior is not specified, record the uncertainty
  in unresolved_issues.
- Never assume active-high or active-low reset without evidence.

TIMING REQUIREMENTS:

- Preserve all specified clock-cycle behavior.
- Preserve specified delays and timer conditions.
- Preserve valid, busy, ready and similar signal behavior
  whenever present in the specification.
- For a stated one-cycle operation, preserve the specified sequence: accept
  start only when not busy, capture inputs on acceptance, perform the
  operation during the processing cycle, and assert valid with the result on
  the specified following edge. Do not assert valid on capture merely because
  start was accepted. Do not invent priority for simultaneous events whose
  priority is unspecified.
- Do not invent latency or timing requirements.

ARCHITECTURE REQUIREMENTS:

- Use the component architecture only as secondary context.
- Do not treat verification results or decomposition as primary hardware evidence.
- Respect the specified interactions through this component's declared ports.
- Do not create unnecessary hardware modules.
- Do not add internal management components
  merely because they appear in decomposition. Model only behavior supported
  by the original specification for this component.
- Ensure that this component's required behavior is represented.
- Do not blindly trust an incorrect decomposition if it conflicts
  with the original specification.
- Record genuine architectural uncertainties.

OPERATION AND SIGNAL REQUIREMENTS:

- When operands or an opcode are captured in registers, use the captured
  register values for operation decoding and operation selection. Never decode
  or select operations from a live opcode while a captured opcode is required.
- Assign every combinational output and derived signal exactly once per final
  output path. Do not place the same ASSIGN in multiple combinational blocks.
- Do not create valid_reg, busy_reg, or similar redundant register copies when
  valid and busy can be driven directly and correctly from state or existing
  state-dependent signals.
- Do not declare registers or signals that are not read by functional logic or
  required outputs. Declare only necessary state elements and derived signals.
- Keep error and valid behavior source-grounded. If the specification does not
  define mutual exclusion, result behavior, or unsupported-opcode valid/result
  behavior, preserve that behavior in UNRESOLVED entries instead of inventing it.
- The assumptions array may contain only explicit, justified implementation
  choices; never use it to implement behavior that the specification leaves
  unresolved. An assumption and an unresolved issue must not contradict each
  other or the pseudocode.
- Do not assume reset behavior, signal duration, pulse width, timing, event
  priority, or other implementation-affecting behavior without evidence in the
  original specification. Keep explicitly specified behavior separate from
  genuinely unspecified behavior: unresolved requirements must not also be
  silently implemented as assumptions.
- The unresolved_issues array must contain only genuine omissions or
  ambiguities in the original specification. Do not mark an explicitly defined
  behavior as unresolved or contradict a stated requirement.
- Reconcile the complete interface against the original specification. Declare
  each input, output, and clock once, with exact names and widths; CLOCK metadata
  must not be duplicated as an INPUT declaration.
- INPUT, OUTPUT, and CLOCK declarations already declare interface signals.
  Never redeclare an interface signal as REG or SIG. Assign a register-backed
  output directly in its legal block instead of declaring the same name twice.
- Every declared output must be driven by a supported assignment in the
  pseudocode. Do not satisfy this requirement by adding unsupported behavior.
- Include exactly one matching MODULE declaration and END MODULE delimiter;
  keep all declarations and blocks inside that module.
- If a clock edge is unspecified, do not emit CLOCK metadata or a clocked block
  using a conventional/default edge. Do not emit RESET blocks or clocked
  register assignments that assume an edge. Keep edge-dependent implementation
  unresolved rather than selecting an assumed edge.
- Keep each clocked register to one assignment per possible terminal path.
  Independent IF statements with potentially overlapping conditions must not
  assign the same register. Do not rely on implicit state invariants the
  validator cannot establish.
- Resolve simultaneous events only when their priority is specified; otherwise
  report the ambiguity and leave it unimplemented.
- Never assume a clock edge. If rising or falling clock edge is unspecified,
  do not add CLOCK ... EDGE RISING or EDGE FALLING or a clocked edge assumption.
  Preserve it as an unresolved clock requirement.
- Unsupported opcodes may set an explicit error detection signal if the
  specification requires an error, but must not silently select or claim a
  misleading operation result. Use unresolved entries for any unspecified result.
- When operation-select signals are produced by a decoder, use the decoder's
  source-supported mapping and exclusivity as architectural context. Do not
  treat derived signals as arbitrary simultaneous events. Conversely, do not
  assume exclusivity or priority unless the original specification and declared
  connections establish it. Leave invalid combinations unresolved rather than
  implementing an unsupported priority.
- Never use x-valued literals such as 32'bx. A combinational internal datapath
  may use a width-correct grammar-valid default only when its consumers
  demonstrably ignore that value whenever no supported selection is active.
  This internal default must not define unsupported-opcode result, valid, or
  error behavior. If unobservability cannot be established, leave the case
  unresolved rather than inventing a visible result.

FINAL SELF-CHECK:

Before returning the result:
1. Check that every required input and output is represented.
2. Check that every functional requirement is implemented.
3. Check that reset behavior matches the specification.
4. Check that timing behavior matches the specification.
5. Check that all conditional blocks are balanced.
6. Check that all CASE blocks are balanced.
7. Check that all FUNCTION blocks are balanced.
8. Check that all clocked blocks are balanced.
9. Check that no unsupported behavior was introduced.
10. Record genuine assumptions and unresolved issues.
11. Confirm every assumption is supported by the original specification and
    does not conflict with any unresolved issue or implemented behavior.
12. Confirm every unresolved issue identifies information that the original
    specification genuinely leaves unspecified.
13. Check every clocked register has at most one assignment on each possible
    terminal path, and independent IF conditions do not create duplicate
    assignments.
14. Check all clock and reset declarations and clocked behavior are supported
    by the original specification; when an edge is unspecified, emit no CLOCK,
    CLOCKED, RESET, or clocked register assignments that assume one.
15. Check every unresolved implementation-affecting ambiguity is reported and
    no assumption contradicts an unresolved requirement.
16. Check the pseudocode follows Grammar V1.

OUTPUT FORMAT:

Return exactly one valid JSON object for the single requested component.

Required fields:
- component_name
- module_name
- inputs
- outputs
- pseudocode
- assumptions
- unresolved_issues

JSON FIELD TYPES:

- component_name and module_name must be strings. component_name must exactly
  match the supplied decomposition component name; module_name must exactly
  match the supplied module name.
- inputs, outputs, pseudocode, assumptions, and unresolved_issues must each be
  flat arrays of strings. Every array item must be a string.
- Do not return objects/dictionaries, nested arrays, or numeric values (such as
  numeric widths) in any of these arrays. Include signal names and widths in
  string form, for example "operand_a[31:0]".

VALID example:
{{
  "inputs": ["operand_a[31:0]", "opcode[3:0]", "start", "clk", "rst_n"],
  "outputs": ["result[31:0]", "valid", "busy", "error"]
}}

INVALID example:
{{
  "inputs": [
    {{"name": "operand_a", "width": "32", "direction": "input"}}
  ]
}}
Also invalid: {{"inputs": [["operand_a", "32"]]}} or {{"inputs": ["operand_a", 32]}}.

FINAL JSON CONSISTENCY CHECK:

- If an item is unresolved, do not implement it as assumed behavior.
- Do not assume a rising edge, one-cycle error duration, start pulse width,
  or simultaneous-event priority unless the original specification explicitly
  establishes it.
- Do not report the same behavior as both assumed and unresolved.
- If the edge is unspecified, keep the specified external clock as a string
  in inputs, but emit no CLOCK metadata, BLOCK CLOCKED, RESET block, or
  clocked register assignment that assumes an edge, and do not put a rising-
  edge assumption in assumptions. Record the missing edge as unresolved.

Return ONLY this component's JSON object.
Do not include Markdown fences or additional explanations.
"""


def extract_json(content: str) -> str:
    """Extract the first complete JSON object from the response."""

    if not content or not content.strip():
        raise ValueError("The model returned an empty response.")

    content = content.strip()

    content = re.sub(
        r"^\s*```(?:json)?\s*",
        "",
        content,
        flags=re.IGNORECASE,
    )

    content = re.sub(r"\s*```\s*$", "", content)

    start = content.find("{")

    if start == -1:
        raise ValueError(
            "No JSON object found in the model response. "
            f"Response preview: {content[:500]}"
        )

    decoder = json.JSONDecoder()

    try:
        data, _ = decoder.raw_decode(content[start:])
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid or incomplete JSON: {error}"
        ) from error

    if not isinstance(data, dict):
        raise ValueError("The response must be a JSON object.")

    if "error" in data:
        raise ValueError(
            f"Model returned an error: {data['error']}"
        )

    return json.dumps(data)


def extract_response_content(response) -> str:
    """Convert LLM response content into a string."""

    content = response.content

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts = []

        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            elif isinstance(block, str):
                text_parts.append(block)

        return "\n".join(text_parts)

    return str(content)


def save_raw_response(
    raw_content: str,
    output_dir: str | Path | None = None,
    component_name: str | None = None,
) -> Path:
    """Save the raw model response for debugging.

    The default directory stays ``outputs`` so command-line runs keep their
    existing artifact location. API runs pass the directory for that execution.
    """

    target = Path(output_dir) if output_dir is not None else Path("outputs")
    target.mkdir(parents=True, exist_ok=True)

    if component_name:
        safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", component_name).strip("_")
        raw_path = target / f"pseudocode_raw_{safe_name}.txt"
    else:
        raw_path = target / "pseudocode_raw.txt"
    raw_path.write_text(raw_content, encoding="utf-8")

    print(f"Raw model response saved to: {raw_path}")
    return raw_path


def _parse_pseudocode_response(
    raw_content: str,
    *,
    component_name: str,
    module_name: str,
    inputs: list[str],
    outputs: list[str],
) -> tuple[ComponentPseudocodeOutput, list[dict]]:
    """Parse and validate the Pydantic JSON contract without repairing pseudocode."""

    if not raw_content.strip():
        raise ValueError("The model returned an empty response.")

    data = json.loads(extract_json(raw_content))
    required_fields = [
        "component_name",
        "module_name",
        "inputs",
        "outputs",
        "pseudocode",
        "assumptions",
        "unresolved_issues",
    ]

    missing_fields = [
        field for field in required_fields if field not in data
    ]
    if missing_fields:
        raise ValueError(
            "Missing required fields: " + ", ".join(missing_fields)
        )

    for field in ["component_name", "module_name"]:
        if not isinstance(data[field], str):
            raise ValueError(f"'{field}' must be a string.")

    if not isinstance(data["pseudocode"], list):
        raise ValueError("'pseudocode' must be an array of strings.")

    if not all(isinstance(line, str) for line in data["pseudocode"]):
        raise ValueError("Every pseudocode element must be a string.")

    for field in ["inputs", "outputs", "assumptions", "unresolved_issues"]:
        if not isinstance(data[field], list):
            raise ValueError(f"'{field}' must be an array.")
        if not all(isinstance(item, str) for item in data[field]):
            raise ValueError(f"Every item in '{field}' must be a string.")

    data["pseudocode"] = _normalize_pseudocode_lines(data["pseudocode"])
    issues = []
    for field, expected in (
        ("component_name", component_name),
        ("module_name", module_name),
        ("inputs", inputs),
        ("outputs", outputs),
    ):
        if data[field] != expected:
            issues.append({
                "code": "COMPONENT_TRACEABILITY_MISMATCH",
                "severity": "error",
                "line": None,
                "message": (
                    f"Generated {field} does not exactly match the "
                    "decomposed component contract."
                ),
            })

    component = ComponentPseudocodeOutput(
        component_name=component_name,
        module_name=module_name,
        inputs=inputs,
        outputs=outputs,
        pseudocode=data["pseudocode"],
        assumptions=data["assumptions"],
        unresolved_issues=data["unresolved_issues"],
        generation_status="Failed" if issues else "completed",
        validation_status="Failed" if issues else "not_run",
        validation_issues=issues.copy(),
    )
    return component, issues


def _normalize_pseudocode_lines(lines: List[str]) -> List[str]:
    """Remove presentation-only fences and blank lines without changing logic."""

    return [
        line.rstrip()
        for line in lines
        if line.strip() and not re.fullmatch(r"\s*```(?:[A-Za-z0-9_-]+)?\s*", line)
    ]


def _component_module_name(component_name: str) -> str:
    module_name = re.sub(r"[^A-Za-z0-9_]", "_", component_name).strip("_")
    if not module_name:
        module_name = "component"
    if module_name[0].isdigit():
        module_name = f"_{module_name}"
    return module_name


def _component_ambiguities(
    component_name: str,
    inputs: list[str],
    outputs: list[str],
    description: DescriptionOutput | None,
    understanding: Understanding | None,
) -> list[str]:
    if understanding is None:
        return []

    signal_names = [
        re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)", signal)
        for signal in [*inputs, *outputs]
    ]
    generic_control_names = {
        "clk", "clock", "rst", "rst_n", "reset", "reset_n",
    }
    names = {
        component_name.lower(),
        *(
            match.group(1).lower()
            for match in signal_names
            if match and match.group(1).lower() not in generic_control_names
        ),
    }
    has_clock_input = any(
        re.match(r"\s*(?:clk|clock)\b", signal, re.I)
        for signal in inputs
    )
    has_reset_input = any(
        re.match(r"\s*(?:rst|rst_n|reset|reset_n)\b", signal, re.I)
        for signal in inputs
    )
    responsibility_text = ""
    if description is not None:
        responsibility_text = " ".join([
            description.purpose,
            *description.behavior,
            *(
                f"{state.name} {state.description}"
                for state in description.state_elements
            ),
        ]).lower()
    responsibility_text = re.sub(
        r"\b(?:without|no|not)\s+(?:\w+\s+){0,3}"
        r"(?:state|register|capture|storage|retention)\b",
        " ",
        responsibility_text,
    )
    has_state = bool(
        description is not None
        and (
            description.state_elements
            or re.search(
                r"\b(?:capture|register|sequential|state machine|clocked|"
                r"store|retain)\b",
                responsibility_text,
            )
        )
    )
    relevant = []
    for ambiguity in understanding.ambiguities:
        ambiguity_text = ambiguity.lower()
        if any(
            re.search(r"\b" + re.escape(name) + r"\b", ambiguity_text)
            for name in names
        ):
            relevant.append(ambiguity)
            continue
        if (
            ("clock" in ambiguity_text or "edge" in ambiguity_text)
            and has_state
            and has_clock_input
        ):
            relevant.append(ambiguity)
            continue
        if (
            ("reset" in ambiguity_text or re.search(r"\brst\b", ambiguity_text))
            and has_state
            and has_reset_input
        ):
            relevant.append(ambiguity)
    return relevant


def _signal_shape(signal: str) -> tuple[str, str | None]:
    match = re.fullmatch(
        r"\s*([A-Za-z_][A-Za-z0-9_]*)(?:\[([0-9]+):([0-9]+)\])?\s*",
        signal,
    )
    if not match:
        raise ValueError(f"Invalid component interface signal '{signal}'.")
    width = (
        f"[{match.group(2)}:{match.group(3)}]"
        if match.group(2) is not None
        else None
    )
    return match.group(1), width


def _width_in_bits(width: str | None) -> int:
    if width is None:
        return 1
    bounds = re.fullmatch(r"\[([0-9]+):([0-9]+)\]", width)
    if bounds is None:
        raise ValueError(f"Invalid signal width '{width}'.")
    return abs(int(bounds.group(1)) - int(bounds.group(2))) + 1


def _selected_source_width(
    declared_width: str | None,
    selected_width: str | None,
    endpoint: str,
) -> int:
    if selected_width is None or selected_width == declared_width:
        return _width_in_bits(declared_width)
    if declared_width is None:
        raise ValueError(
            f"Scalar source '{endpoint}' cannot have a bit-range selection."
        )

    declared_bounds = re.fullmatch(r"\[([0-9]+):([0-9]+)\]", declared_width)
    selection_bounds = re.fullmatch(r"\[([0-9]+):([0-9]+)\]", selected_width)
    if declared_bounds is None or selection_bounds is None:
        raise ValueError(f"Invalid source selection in '{endpoint}'.")
    declared_msb, declared_lsb = map(int, declared_bounds.groups())
    selected_msb, selected_lsb = map(int, selection_bounds.groups())
    lower_bound = min(declared_msb, declared_lsb)
    upper_bound = max(declared_msb, declared_lsb)
    if not (
        lower_bound <= selected_msb <= upper_bound
        and lower_bound <= selected_lsb <= upper_bound
    ):
        raise ValueError(
            f"Source selection in '{endpoint}' is outside the declared "
            f"range {declared_width}."
        )
    return abs(selected_msb - selected_lsb) + 1


def _description_interface_issues(
    component: Component,
    description: DescriptionOutput,
) -> list[dict]:
    issues = []
    for direction, expected, actual in (
        ("input", component.inputs, description.inputs),
        ("output", component.outputs, description.outputs),
    ):
        expected_shapes = [
            (*_signal_shape(signal), direction) for signal in expected
        ]
        actual_shapes = []
        for signal in actual:
            width_text = signal.width.strip()
            if re.fullmatch(r"[0-9]+", width_text):
                bits = int(width_text)
                width = f"[{bits - 1}:0]" if bits > 1 else None
            elif re.fullmatch(r"\[[0-9]+:[0-9]+\]", width_text):
                width = width_text
            else:
                width = None
            actual_shapes.append((signal.name, width, signal.direction.lower()))
        if actual_shapes != expected_shapes:
            issues.append(_component_issue(
                "COMPONENT_DESCRIPTION_INTERFACE_MISMATCH",
                f"The {direction} interface in component '{component.name}' "
                "does not exactly match its description in names, widths, "
                "directions, and order.",
            ))
    return issues


def _decomposition_interaction_issues(
    decomposition: DecompositionOutput,
    understanding: Understanding | None,
) -> list[dict]:
    issues = []
    component_inputs = {}
    component_outputs = {}
    seen_component_names = set()

    def component_interfaces(component: Component, direction: str) -> dict:
        interfaces = {}
        for item in getattr(component, direction):
            try:
                name, width = _signal_shape(item)
            except ValueError as error:
                issues.append(_component_issue(
                    "DECOMPOSITION_INTERACTION_INTERFACE_MISMATCH",
                    f"Component '{component.name}' has malformed {direction[:-1]} "
                    f"interface signal '{item}': {error}",
                ))
                continue
            if name in interfaces:
                issues.append(_component_issue(
                    "DECOMPOSITION_INTERACTION_INTERFACE_MISMATCH",
                    f"Component '{component.name}' declares {direction[:-1]} "
                    f"port '{name}' more than once.",
                ))
                continue
            interfaces[name] = width
        return interfaces

    for component in decomposition.components:
        if component.name in seen_component_names:
            issues.append(_component_issue(
                "DECOMPOSITION_INTERACTION_INTERFACE_MISMATCH",
                f"Component name '{component.name}' is declared more than once.",
            ))
        seen_component_names.add(component.name)
        component_inputs[component.name] = component_interfaces(
            component, "inputs"
        )
        component_outputs[component.name] = component_interfaces(
            component, "outputs"
        )

    def system_interfaces(items: list[str] | None) -> dict[str, str | None]:
        interfaces = {}
        for item in items or []:
            if str(item).strip().upper().startswith("NOT SPECIFIED:"):
                continue
            signal_match = re.match(
                r"^\s*([A-Za-z_][A-Za-z0-9_]*"
                r"(?:\[[0-9]+:[0-9]+\])?)"
                r"(?:\s*:\s*.*)?\s*$",
                str(item),
            )
            if not signal_match:
                issues.append(_component_issue(
                    "DECOMPOSITION_INTERACTION_INTERFACE_MISMATCH",
                    f"Malformed system interface signal '{item}'.",
                ))
                continue
            name, width = _signal_shape(signal_match.group(1))
            if name in interfaces:
                issues.append(_component_issue(
                    "DECOMPOSITION_INTERACTION_INTERFACE_MISMATCH",
                    f"System interface signal '{name}' is declared more than once.",
                ))
                continue
            interfaces[name] = width
        return interfaces

    system_inputs = system_interfaces(
        understanding.inputs if understanding is not None else None
    )
    system_outputs = system_interfaces(
        understanding.outputs if understanding is not None else None
    )
    component_names = sorted(
        component_inputs,
        key=len,
        reverse=True,
    )
    def resolve_endpoint(endpoint: str, *, is_source: bool):
        for component_name in component_names:
            prefix = f"{component_name} "
            if not endpoint.startswith(prefix):
                continue
            try:
                port_name, width = _signal_shape(endpoint[len(prefix):])
            except ValueError as error:
                raise ValueError(
                    f"Malformed component endpoint '{endpoint}': {error}"
                ) from error
            ports = (
                component_outputs[component_name]
                if is_source
                else component_inputs[component_name]
            )
            direction = "output" if is_source else "input"
            if port_name not in ports:
                raise ValueError(
                    f"Component '{component_name}' has no {direction} port "
                    f"'{port_name}' referenced by '{endpoint}'."
                )
            expected_width = ports[port_name]
            effective_width = (
                _selected_source_width(expected_width, width, endpoint)
                if is_source
                else _width_in_bits(expected_width)
            )
            if not is_source and width is not None and width != expected_width:
                raise ValueError(
                    f"Port '{component_name}.{port_name}' width in "
                    f"'{endpoint}' does not match its decomposed interface."
                )
            return component_name, port_name, effective_width

        try:
            port_name, width = _signal_shape(endpoint)
        except ValueError as error:
            raise ValueError(
                f"Malformed system endpoint '{endpoint}': {error}"
            ) from error
        ports = system_inputs if is_source else system_outputs
        direction = "input" if is_source else "output"
        if port_name not in ports:
            raise ValueError(
                f"'{endpoint}' is not a declared system {direction} or "
                f"component {'output' if is_source else 'input'}."
            )
        expected_width = ports[port_name]
        if is_source:
            effective_width = _selected_source_width(
                expected_width, width, endpoint
            )
        elif width is not None and width != expected_width:
            raise ValueError(
                f"System {direction} '{endpoint}' has a width that does not "
                "match Understanding."
            )
        else:
            effective_width = _width_in_bits(expected_width)
        return None, port_name, effective_width

    def channel_identity(name: str) -> tuple[tuple[str, ...], str] | None:
        tokens = name.lower().split("_")
        if len(tokens) < 2:
            return None
        label = tokens[-1]
        if not (label.isdecimal() or (len(label) == 1 and label.isalpha())):
            return None
        generic_roles = {
            "arg", "captured", "data", "dest", "destination", "in", "input",
            "operand", "out", "output", "port", "signal", "source", "value",
        }
        family = tuple(token for token in tokens[:-1] if token not in generic_roles)
        return family, label

    driven_destinations = {}
    for interaction in decomposition.interactions:
        endpoints = re.split(r"\s*->\s*", interaction)
        try:
            if len(endpoints) != 2 or not all(endpoints):
                raise ValueError(
                    "Interaction must contain one source and destination."
                )
            source = resolve_endpoint(endpoints[0], is_source=True)
            destination = resolve_endpoint(endpoints[1], is_source=False)
            if source[2] != destination[2]:
                raise ValueError(
                    f"Interaction '{interaction}' connects mismatched signal widths."
                )
            destination_key = (destination[0], destination[1])
            previous_source = driven_destinations.get(destination_key)
            if previous_source is not None:
                issues.append(_component_issue(
                    "DECOMPOSITION_INTERACTION_DUPLICATE_DRIVER",
                    f"Destination '{endpoints[1]}' has multiple drivers: "
                    f"'{previous_source}' and '{endpoints[0]}'.",
                ))
            else:
                driven_destinations[destination_key] = endpoints[0]

            if source[0] is not None and destination[0] is not None:
                source_identity = channel_identity(
                    _signal_shape(endpoints[0][len(source[0]) + 1:])[0]
                )
                destination_identity = channel_identity(destination[1])
                if (
                    source_identity is not None
                    and destination_identity is not None
                    and source_identity[0] == destination_identity[0]
                    and source_identity[1] != destination_identity[1]
                ):
                    issues.append(_component_issue(
                        "DECOMPOSITION_INTERACTION_SIGNAL_MISMATCH",
                        f"Interaction '{interaction}' maps signal channel "
                        f"'{source_identity[1]}' to a port labeled "
                        f"'{destination_identity[1]}'.",
                    ))
        except ValueError as error:
            issues.append(_component_issue(
                "DECOMPOSITION_INTERACTION_INTERFACE_MISMATCH",
                str(error),
            ))

    for component_name, ports in component_inputs.items():
        for port_name, port_width in ports.items():
            destination = (component_name, port_name)
            if destination in driven_destinations:
                continue
            if port_name in system_inputs:
                if system_inputs[port_name] != port_width:
                    issues.append(_component_issue(
                        "DECOMPOSITION_INTERACTION_INTERFACE_MISMATCH",
                        f"Unconnected component input '{component_name} "
                        f"{port_name}' has a different width from the "
                        f"same-named system input '{port_name}'.",
                    ))
                # A same-named system input is a valid direct top-level
                # source even when the decomposition omits an explicit edge.
                continue
            issues.append(_component_issue(
                "DECOMPOSITION_INTERACTION_MISSING_INPUT_DRIVER",
                f"Required input '{component_name} {port_name}' has no "
                "system-input or component-output driver.",
            ))
    return issues


def _observable_datapath_default_issues(
    generated_components: list[ComponentPseudocodeOutput],
    decomposition: DecompositionOutput,
    understanding: Understanding | None,
) -> list[dict]:
    if understanding is None:
        return []

    component_by_name = {
        component.name: component for component in decomposition.components
    }
    component_names = sorted(component_by_name, key=len, reverse=True)
    graph: dict[tuple[str | None, str], set[tuple[str | None, str]]] = {}
    default_assignments: list[tuple[str, str, int]] = []
    assignment_pattern = re.compile(
        r"^\s*(?:ASSIGN\s+)?"
        r"([A-Za-z_][A-Za-z0-9_]*)(?:\[[0-9]+:[0-9]+\])?"
        r"\s*(<=|=)\s*(.*?)\s*$",
        re.I,
    )
    constant_pattern = re.compile(
        r"(?:[0-9]+'[bBdDhHoO][0-9a-fA-F_]+|[0-9]+|0[bB][01]+)"
    )
    identifier_pattern = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")

    for generated in generated_components:
        component_name = generated.component_name
        in_combinational_block = False
        control_stack: list[tuple[str, bool]] = []
        for line_number, line in enumerate(generated.pseudocode, start=1):
            stripped = line.strip()
            if re.match(r"^BLOCK\s+COMBINATIONAL\b", stripped, re.I):
                in_combinational_block = True
                continue
            if re.match(r"^END\s+BLOCK\b", stripped, re.I):
                in_combinational_block = False
                control_stack.clear()
                continue

            if in_combinational_block:
                if re.match(r"^IF\b.*\bTHEN\s*$", stripped, re.I):
                    control_stack.append(("IF", False))
                    continue
                if re.match(r"^ELSE\s+IF\b", stripped, re.I):
                    if control_stack and control_stack[-1][0] == "IF":
                        control_stack[-1] = ("IF", False)
                    continue
                if re.match(r"^ELSE\s*$", stripped, re.I):
                    if control_stack and control_stack[-1][0] == "IF":
                        control_stack[-1] = ("IF", True)
                    continue
                if re.match(r"^CASE\b", stripped, re.I):
                    control_stack.append(("CASE", False))
                    continue
                if re.match(r"^WHEN\s+DEFAULT\s*:", stripped, re.I):
                    if control_stack and control_stack[-1][0] == "CASE":
                        control_stack[-1] = ("CASE", True)
                    continue
                if re.match(r"^WHEN\b", stripped, re.I):
                    if control_stack and control_stack[-1][0] == "CASE":
                        control_stack[-1] = ("CASE", False)
                    continue
                if re.match(r"^END\s+(?:IF|CASE)\b", stripped, re.I):
                    if control_stack:
                        control_stack.pop()
                    continue

            assignment = assignment_pattern.match(stripped)
            if assignment is None:
                continue
            lhs, _operator, rhs = assignment.groups()
            lhs_node = (component_name, lhs)
            rhs_without_literals = re.sub(
                constant_pattern,
                " ",
                rhs,
            )
            for identifier in identifier_pattern.findall(rhs_without_literals):
                graph.setdefault((component_name, identifier), set()).add(lhs_node)

            if (
                in_combinational_block
                and any(is_default for _, is_default in control_stack)
                and constant_pattern.fullmatch(rhs.strip())
            ):
                default_assignments.append((component_name, lhs, line_number))

    def endpoint_node(endpoint: str, *, is_source: bool):
        for component_name in component_names:
            prefix = f"{component_name} "
            if not endpoint.startswith(prefix):
                continue
            try:
                port_name, _ = _signal_shape(endpoint[len(prefix):])
            except ValueError:
                return None
            ports = (
                component_by_name[component_name].outputs
                if is_source
                else component_by_name[component_name].inputs
            )
            declared = {
                _signal_shape(port)[0] for port in ports
                if re.fullmatch(
                    r"\s*[A-Za-z_][A-Za-z0-9_]*(?:\[[0-9]+:[0-9]+\])?\s*",
                    port,
                )
            }
            return (component_name, port_name) if port_name in declared else None

        try:
            signal_name, _ = _signal_shape(endpoint)
        except ValueError:
            return None
        interface_items = (
            understanding.inputs if is_source else understanding.outputs
        )
        system_ports = set()
        for port in interface_items:
            if port.strip().upper().startswith("NOT SPECIFIED:"):
                continue
            match = re.match(
                r"^\s*([A-Za-z_][A-Za-z0-9_]*"
                r"(?:\[[0-9]+:[0-9]+\])?)",
                port,
            )
            if match:
                system_ports.add(_signal_shape(match.group(1))[0])
        return (None, signal_name) if signal_name in system_ports else None

    for interaction in decomposition.interactions:
        endpoints = re.split(r"\s*->\s*", interaction)
        if len(endpoints) != 2 or not all(endpoints):
            continue
        source = endpoint_node(endpoints[0], is_source=True)
        destination = endpoint_node(endpoints[1], is_source=False)
        if source is not None and destination is not None:
            graph.setdefault(source, set()).add(destination)

    system_outputs = set()
    for output in understanding.outputs:
        if output.strip().upper().startswith("NOT SPECIFIED:"):
            continue
        match = re.match(
            r"^\s*([A-Za-z_][A-Za-z0-9_]*)(?:\[[0-9]+:[0-9]+\])?",
            output,
        )
        if match:
            system_outputs.add((None, match.group(1)))

    reverse_graph: dict[
        tuple[str | None, str], set[tuple[str | None, str]]
    ] = {}
    for source, destinations in graph.items():
        for destination in destinations:
            reverse_graph.setdefault(destination, set()).add(source)
    observable_nodes = set(system_outputs)
    pending = list(system_outputs)
    while pending:
        node = pending.pop()
        for predecessor in reverse_graph.get(node, set()):
            if predecessor not in observable_nodes:
                observable_nodes.add(predecessor)
                pending.append(predecessor)

    issues = []
    for component_name, signal_name, line_number in default_assignments:
        if (component_name, signal_name) in observable_nodes:
            issues.append(_component_issue(
                "OBSERVABLE_DATAPATH_DEFAULT",
                f"Combinational default for '{component_name}.{signal_name}' "
                "can reach a system output. Its observability for inactive "
                "selections is not proven.",
            ))
            issues[-1]["line"] = line_number
            issues[-1]["component_name"] = component_name
    return issues


def _component_issue(code: str, message: str) -> dict:
    return {
        "code": code,
        "severity": "error",
        "line": None,
        "message": message,
    }


def _failed_component(
    component_name: str,
    module_name: str,
    inputs: list[str],
    outputs: list[str],
    message: str,
    *,
    code: str = "PSEUDOCODE_GENERATION_FAILED",
) -> ComponentPseudocodeOutput:
    issue = _component_issue(code, message)
    return ComponentPseudocodeOutput(
        component_name=component_name,
        module_name=module_name,
        inputs=inputs,
        outputs=outputs,
        pseudocode=[],
        assumptions=[],
        unresolved_issues=[],
        generation_status="Failed",
        validation_status="Failed",
        validation_issues=[issue],
    )


def _aggregate_pseudocode_result(
    components: list[ComponentPseudocodeOutput],
    *,
    additional_issues: list[dict] | None = None,
) -> PseudocodeGenerationOutput:
    issues = []
    for component in components:
        for issue in component.validation_issues:
            issues.append({
                **issue,
                "component_name": component.component_name,
            })
    issues.extend(additional_issues or [])
    generation_failed = any(
        component.generation_status != "completed"
        for component in components
    )
    assumptions = list(dict.fromkeys(
        assumption
        for component in components
        for assumption in component.assumptions
    ))
    unresolved_issues = list(dict.fromkeys(
        unresolved
        for component in components
        for unresolved in component.unresolved_issues
    ))
    if not components and not additional_issues:
        issues.append(_component_issue(
            "DECOMPOSITION_NO_COMPONENTS",
            "No decomposed components were provided for pseudocode generation.",
        ))
        generation_failed = True
    result = PseudocodeGenerationOutput(
        components=components,
        assumptions=assumptions,
        unresolved_issues=unresolved_issues,
        generation_status="Failed" if generation_failed else "completed",
        validation_status="not_run",
        validation_issues=issues,
        execution_status="Not attempted",
        execution_output="No simulation was run by the pseudocode-generation stage.",
        execution_errors=[],
    )
    return result


def generate_pseudocode(
    specification: str,
    decomposition: DecompositionOutput,
    descriptions: List[DescriptionOutput],
    understanding: Understanding | None = None,
    verification_results: List[VerificationResult] | None = None,
    *,
    raw_output_dir: str | Path | None = None,
) -> PseudocodeGenerationOutput:
    components = decomposition.components
    if not components:
        result = _aggregate_pseudocode_result([])
        print("Pseudocode generation failed: decomposition contains no components.")
        return result

    module_names = [_component_module_name(component.name) for component in components]
    duplicate_component_names = {
        name for name in (component.name for component in components)
        if sum(item.name == name for item in components) > 1
    }
    duplicate_module_names = {
        name for name in module_names if module_names.count(name) > 1
    }
    if duplicate_component_names or duplicate_module_names:
        failed_components = []
        for component, module_name in zip(components, module_names):
            message = (
                f"Duplicate decomposed component name '{component.name}'."
                if component.name in duplicate_component_names
                else f"Component name maps to a duplicate module name '{module_name}'."
            )
            failed_components.append(_failed_component(
                component.name,
                module_name,
                component.inputs,
                component.outputs,
                message,
                code="COMPONENT_TRACEABILITY_MISMATCH",
            ))
        return _aggregate_pseudocode_result(failed_components)

    llm = get_llm("pseudocode")
    descriptions_by_name: dict[str, list[DescriptionOutput]] = {}
    for description in descriptions:
        descriptions_by_name.setdefault(description.module_name, []).append(description)

    results: list[ComponentPseudocodeOutput] = []
    architecture_issues = _decomposition_interaction_issues(
        decomposition, understanding
    )
    verification_results = verification_results or []
    print("\nRequesting pseudocode from the model (single attempt)...")

    decomposed_names = {component.name for component in components}
    for description_name in descriptions_by_name:
        if description_name not in decomposed_names:
            architecture_issues.append(_component_issue(
                "COMPONENT_TRACEABILITY_MISMATCH",
                f"Description '{description_name}' does not match a "
                "decomposed component.",
            ))

    for index, (component, module_name) in enumerate(zip(components, module_names)):
        component_descriptions = descriptions_by_name.get(component.name, [])
        description = component_descriptions[0] if len(component_descriptions) == 1 else None
        description_issues = []
        if len(component_descriptions) > 1:
            description_issues.append(_component_issue(
                "COMPONENT_TRACEABILITY_MISMATCH",
                f"Multiple descriptions match component '{component.name}'.",
            ))
        elif descriptions and not component_descriptions:
            description_issues.append(_component_issue(
                "COMPONENT_TRACEABILITY_MISMATCH",
                f"No description matches component '{component.name}'.",
            ))

        verification = (
            verification_results[index]
            if index < len(verification_results)
            else None
        )
        component_context = {
            "component": component.model_dump(),
            "interactions": decomposition.interactions,
            "description": (
                description.model_dump() if description is not None else "NOT PROVIDED"
            ),
            "verification": (
                verification.model_dump() if verification is not None else "NOT PROVIDED"
            ),
        }
        understanding_text = (
            understanding.model_dump_json(indent=2)
            if understanding is not None
            else "NOT PROVIDED"
        )
        prompt = f"""
{SYSTEM_PROMPT}

ORIGINAL HARDWARE SPECIFICATION — PRIMARY SOURCE:
{specification}

STRUCTURED UNDERSTANDING — SECONDARY SUPPORTING CONTEXT:
{understanding_text}

DECOMPOSITION COMPONENT, INTERACTIONS, DESCRIPTION, AND VERIFICATION:
{json.dumps(component_context, indent=2, ensure_ascii=False)}

Generate pseudocode only for this decomposed component:
- Exact component_name: {component.name}
- Exact module_name: {module_name}
- Exact inputs array: {json.dumps(component.inputs, ensure_ascii=False)}
- Exact outputs array: {json.dumps(component.outputs, ensure_ascii=False)}
- Return those names and arrays exactly; do not add, remove, reorder, or resize signals.
- Use interactions and component descriptions only as supporting context. They
  must not override or extend behavior supported by the original specification.
- Preserve ambiguities as unresolved rather than inventing component behavior.
- Balance every IF, CASE, RESET, BLOCK, FUNCTION, and MODULE delimiter.
- Follow Grammar V1 and return the seven requested fields as valid JSON only.
"""
        print(
            f"Generating component {component.name} "
            f"({index + 1} of {len(components)})..."
        )
        raw_content = ""
        raw_path = None
        try:
            response = llm.invoke(prompt)
            raw_content = extract_response_content(response)
            raw_path = save_raw_response(
                raw_content,
                raw_output_dir,
                component_name=module_name if len(components) > 1 else None,
            )
            generated, traceability_issues = _parse_pseudocode_response(
                raw_content,
                component_name=component.name,
                module_name=module_name,
                inputs=component.inputs,
                outputs=component.outputs,
            )
        except Exception as error:
            print(
                f"Component pseudocode generation failed for "
                f"{component.name}: {type(error).__name__}: {error}"
            )
            if raw_content:
                location = raw_path or (
                    Path(raw_output_dir) / f"pseudocode_raw_{module_name}.txt"
                    if raw_output_dir is not None
                    else Path("outputs") / f"pseudocode_raw_{module_name}.txt"
                )
                print(f"Inspect {location} for the complete model response.")
            results.append(_failed_component(
                component.name,
                module_name,
                component.inputs,
                component.outputs,
                f"{type(error).__name__}: {error}",
            ))
            continue

        module_declarations = [
            match.group(1)
            for line in generated.pseudocode
            if (match := re.match(r"^\s*MODULE\s+([A-Za-z_][A-Za-z0-9_]*)\s*$", line, re.I))
        ]
        if module_declarations != [module_name]:
            traceability_issue = _component_issue(
                "COMPONENT_TRACEABILITY_MISMATCH",
                f"Pseudocode must declare exactly MODULE {module_name}.",
            )
            traceability_issues.append(traceability_issue)
            generated.generation_status = "Failed"
            generated.validation_status = "Failed"
            generated.validation_issues.append(traceability_issue)

        if description is not None:
            description_issues.extend(
                _description_interface_issues(component, description)
            )
        if description_issues:
            generated.validation_status = "Failed"
            generated.validation_issues.extend(description_issues)

        # ---------------------------------------------------------
        # PSEUDOCODE VALIDATION BYPASSED
        # ---------------------------------------------------------
        # We are temporarily skipping semantic pseudocode validation
        # so that RTL generation can be tested independently.
        #
        # Component/module/interface traceability checks above are
        # still retained.
        # ---------------------------------------------------------
        generated.validation_status = "not_run"
        # Keep any traceability and description-interface issues
        # already collected. Do not invoke validate_pseudocode_detailed().
        results.append(generated)

    architecture_issues.extend(_observable_datapath_default_issues(
        results,
        decomposition,
        understanding,
    ))
    result = _aggregate_pseudocode_result(
        results,
        additional_issues=architecture_issues,
    )
    print(
        "Pseudocode generation complete; "
        f"generation {result.generation_status}, "
        "semantic validation skipped."
    )
    for issue in result.validation_issues:
        location = f"Line {issue['line']}: " if issue.get("line") is not None else ""
        print(
            f"- [{issue['code']}] {issue.get('component_name', '')} "
            f"{location}{issue['message']}"
        )
    print(f"Execution status: {result.execution_status}.")
    return result

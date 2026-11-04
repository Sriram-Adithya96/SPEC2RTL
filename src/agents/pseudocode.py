
import json
import re
from pathlib import Path
from typing import List

from src.agents.validate_pseudocode import validate_pseudocode_detailed
from src.llm.llm import get_llm

from src.schemas import (
    DecompositionOutput,
    DescriptionOutput,
    VerificationResult,
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

Your task is to generate complete, hardware-oriented pseudocode
from the original hardware specification.

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

1. Generate pseudocode for the entire hardware system.
2. Include all required inputs and outputs.
3. Include necessary registers, signals and state elements.
4. Include all functional requirements from the specification.
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
3. Use CLOCK <name> EDGE RISING or CLOCK <name> EDGE FALLING for clock metadata
   only when the original specification explicitly defines that edge. If the
   specification does not define the edge, omit CLOCK metadata and omit every
   BLOCK CLOCKED clocked implementation block rather than assuming either edge.
   Preserve the ambiguity with the exact unresolved syntax
   "UNRESOLVED CLOCK : clock edge - <missing detail>" and no invented edge.
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
13. Every reset behavior must be declared authoritatively in the clocked block.
14. Use RESET SYNCHRONOUS SIGNAL <name> ACTIVE_HIGH|ACTIVE_LOW VALUE <value>
   or RESET ASYNCHRONOUS SIGNAL <name> ACTIVE_HIGH|ACTIVE_LOW VALUE <value>.
15. Use RESET NOT SPECIFIED followed by an END RESET block and a matching UNRESOLVED entry
   when reset behavior is unsupported or unspecified.
16. Preserve unresolved reset, clock, width, timing, state-transition, and CDC requirements.
17. Do not invent reset polarity, reset type, reset value, clock properties, widths, latency,
    timer logic, state transitions, CDC synchronization, or hardware architecture.
18. Use one short statement per pseudocode array element.
19. Every opening block and control structure must have a matching canonical closing delimiter.
20. Do not include comments as essential implementation logic.
21. Do not truncate pseudocode or generate RTL or Python code.
22. Generate a complete top-level structure:
    MODULE <name>
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
28. Assign each clocked register at most once per terminal branch. Use mutually
    exclusive branches such as CASE/IF-ELSE for alternate values.
29. A clocked register with no assignment on a terminal path holds its old value.
30. Combinational outputs and signals must receive one final value on every
    terminal path, or use a default assignment followed by conditional overrides.
31. Put every ASSIGN statement inside BLOCK COMBINATIONAL.
32. Every CLOCKED assignment must use "<="; every combinational ASSIGN must
    use "=".
33. For reset information that cannot be stated completely in canonical syntax,
    use:
    RESET NOT SPECIFIED
    END RESET
    and place a matching entry in UNRESOLVED entries:
    UNRESOLVED RESET : reset behavior - <missing details>
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
- If reset behavior is not specified, record the uncertainty
  in unresolved_issues.
- Never assume active-high or active-low reset without evidence.

TIMING REQUIREMENTS:

- Preserve all specified clock-cycle behavior.
- Preserve specified delays and timer conditions.
- Preserve valid, busy, ready and similar signal behavior
  whenever present in the specification.
- Do not invent latency or timing requirements.

ARCHITECTURE REQUIREMENTS:

- Use the component architecture only as secondary context.
- Do not treat verification results or decomposition as primary hardware evidence.
- Include the interactions between components.
- Do not create unnecessary hardware modules.
- Do not add internal management components
  merely because they appear in decomposition. Model only behavior supported
  by the original specification in the top-level module.
- Ensure that required component behavior is represented.
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
- Never assume a clock edge. If rising or falling clock edge is unspecified,
  do not add CLOCK ... EDGE RISING or EDGE FALLING or a clocked edge assumption.
  Preserve it as an unresolved clock requirement.
- Unsupported opcodes may set an explicit error detection signal if the
  specification requires an error, but must not silently select or claim a
  misleading operation result. Use unresolved entries for any unspecified result.

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

OUTPUT FORMAT:

Return exactly one valid JSON object matching
PseudocodeGenerationOutput.

Required fields:
- module_name
- objective
- inputs
- outputs
- pseudocode
- assumptions
- unresolved_issues

The pseudocode field must be an array of strings.

Return ONLY the JSON object.
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


def save_raw_response(raw_content: str) -> None:
    """Save the raw model response for debugging."""

    output_dir = Path("outputs")
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_path = output_dir / "pseudocode_raw.txt"
    raw_path.write_text(raw_content, encoding="utf-8")

    print(f"Raw model response saved to: {raw_path}")


def _parse_pseudocode_response(raw_content: str) -> PseudocodeGenerationOutput:
    """Parse and validate the Pydantic JSON contract without repairing pseudocode."""

    if not raw_content.strip():
        raise ValueError("The model returned an empty response.")

    data = json.loads(extract_json(raw_content))
    required_fields = [
        "module_name",
        "objective",
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

    for field in ["module_name", "objective"]:
        if not isinstance(data[field], str):
            raise ValueError(f"'{field}' must be a string.")

    if not isinstance(data["pseudocode"], list):
        raise ValueError("'pseudocode' must be an array of strings.")

    if not all(isinstance(line, str) for line in data["pseudocode"]):
        raise ValueError("Every pseudocode element must be a string.")

    if not data["pseudocode"]:
        raise ValueError("Generated pseudocode is empty.")

    for field in ["inputs", "outputs", "assumptions", "unresolved_issues"]:
        if not isinstance(data[field], list):
            raise ValueError(f"'{field}' must be an array.")
        if not all(isinstance(item, str) for item in data[field]):
            raise ValueError(f"Every item in '{field}' must be a string.")

    return PseudocodeGenerationOutput.model_validate(data)


def generate_pseudocode(
    specification: str,
    decomposition: DecompositionOutput,
    descriptions: List[DescriptionOutput],
    understanding: Understanding | None = None,
    verification_results: List[VerificationResult] | None = None,
) -> PseudocodeGenerationOutput:

    llm = get_llm()

    decomposition_text = decomposition.model_dump_json(indent=2)
    descriptions_text = "\n\n".join(
        item.model_dump_json(indent=2)
        for item in descriptions
    )
    verification_text = "\n\n".join(
        item.model_dump_json(indent=2)
        for item in (verification_results or [])
    )
    understanding_text = (
        understanding.model_dump_json(indent=2)
        if understanding is not None
        else "NOT PROVIDED"
    )

    evidence_sections = f"""
ORIGINAL HARDWARE SPECIFICATION — PRIMARY SOURCE:
{specification}

STRUCTURED UNDERSTANDING — SECONDARY SUPPORTING CONTEXT:
{understanding_text}

SYSTEM DECOMPOSITION — SECONDARY SUPPORTING CONTEXT:
{decomposition_text}

COMPONENT DESCRIPTIONS — SECONDARY SUPPORTING CONTEXT:
{descriptions_text}

VERIFICATION RESULTS — SECONDARY REPORTS ONLY:
{verification_text}

The verification agent's valid=true field is not proof that a reset, timer,
width, state transition, or architecture fact is supported by the primary
specification. Secondary context never overrides the PRIMARY SOURCE.
"""

    print("\nRequesting pseudocode from the model (single attempt)...")

    prompt = f"""
{SYSTEM_PROMPT}

{evidence_sections}

Generate complete pseudocode for the entire hardware system.

Additional instructions:
- Follow the original specification over every secondary source.
- Include all required implementation logic only when supported.
- Preserve required state transitions and external timer behavior.
- Select IF/ELSE and CASE/WHEN structures based on the actual specification.
- Use one short statement per pseudocode array element.
- Include exact top-level module, clock, interface, and internal declarations.
- Balance every IF, CASE, RESET, BLOCK, FUNCTION, and MODULE delimiter.
- Include matching UNRESOLVED entries for implementation-affecting ambiguities.
- Do not use legacy syntax.
- Return all seven required fields.
- Return exactly one valid JSON object and no Markdown.
"""

    raw_content = ""
    try:
        response = llm.invoke(prompt)
        raw_content = extract_response_content(response)
        save_raw_response(raw_content)
        result = _parse_pseudocode_response(raw_content)
    except Exception as error:
        print("\n[PSEUDOCODE AGENT ERROR]")
        print("Error type:", type(error).__name__)
        print("Error details:", str(error))
        if raw_content:
            print(
                "\nInspect outputs/pseudocode_raw.txt "
                "for the complete model response."
            )
        print("Pseudocode generation stopped after one API attempt.")
        raise

    detailed_result = validate_pseudocode_detailed(
        result.pseudocode,
        specification=specification,
        understanding=understanding,
        decomposition=decomposition,
        descriptions=descriptions,
    )

    if detailed_result.blocking_issues:

        print("\nPseudocode validation failed:")

        for issue in detailed_result.blocking_issues:
            location = f"Line {issue.line}: " if issue.line is not None else ""
            print(f"- [{issue.code}] {location}{issue.message}")

        print("\nWARNING: Continuing despite validation failures.")

    return result

    print("\nPseudocode passed deterministic validation.")
    return result

import json
import re
from typing import Any, List, Union

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from src.llm.llm import get_llm, is_free_openrouter_model
from src.schemas import Understanding

try:
    from langchain.agents import create_agent
except ImportError:
    def create_agent(*args: Any, **kwargs: Any) -> Any:
        pass
SYSTEM_PROMPT = """
You are the Understanding Agent, the first stage of a
general-purpose hardware-to-RTL pipeline.

Your responsibility is to carefully understand a hardware specification
and extract its information into the Understanding schema.

You must work with different types of hardware specifications, including
arithmetic units, counters, ALUs, FIFO buffers, UART, SPI, memory controllers,
finite state machines, and other digital hardware systems.

Do not assume that the input describes any particular hardware architecture.

You are NOT an RTL designer at this stage.

CORE RULES:

1. Use the supplied specification as the primary source of truth.

2. Do not invent signal names, widths, values, timing, protocols,
   components, or behaviors.

3. Preserve identifiers, numeric values, units, frequencies, widths,
   timing values, reset polarity, and protocol names exactly as written.

4. Do not generate RTL, pseudocode, algorithms, or implementation suggestions.

5. Do not resolve ambiguities or contradictions.

6. Do not silently fill missing information using general hardware knowledge.

7. Distinguish explicitly stated facts from functional groupings.

8. Do not claim that a functional grouping is a physically separate
   hardware module unless the specification explicitly states so.

9. If information required by the schema is missing, use:
   "NOT SPECIFIED: <item>"

10. If the specification contains conflicting information, record
    the conflict in ambiguities instead of choosing an interpretation.

11. Extract all relevant requirements. Do not omit requirements merely
    because they appear in different sections of the specification.

12. Treat external timer, sensor, clock, reset, and control signals exactly
    as the specification defines them. Do not convert external inputs into
    inferred internal registers, counters, timers, or management components.

13. If reset type, polarity, value, or clock edge is absent, record it in
    ambiguities as unspecified rather than inferring a conventional value.

SIGNAL IDENTIFICATION RULE:

Only classify something as a signal if the specification explicitly
identifies it as a signal, port, input, output, clock, reset,
or member of an explicitly defined interface.

Do not invent signal names from functional descriptions.

If a required signal name is absent, use:
"NOT SPECIFIED: signal name"


COMPONENT IDENTIFICATION RULE:

STEP 1: Extract every distinct operation and functional responsibility explicitly described in the specification.

STEP 2: Categorize data-processing operations into distinct functional categories when supported:

- Arithmetic: addition, subtraction, multiplication, division.
- Logical: AND, OR, XOR, NOT.
- Shifting: logical shifts, arithmetic shifts, rotations.
- Comparison: equality and magnitude comparisons.

STEP 3: Keep different operation categories as separate functional components. Do not combine arithmetic, logical and shift operations into one generic component.

STEP 4: Identify other supported responsibilities separately:

- Command/opcode decoding.
- Control and sequencing.
- Reset management.
- Result generation and handling.
- Storage and buffering.
- Error detection and reporting.

STEP 5: Convert the identified functional groups into concise component names in `major_components`.

IMPORTANT:

- These categories are examples, not mandatory components.
- Only include components supported by the actual specification.
- Do not create Timer Management, Sensor Management, or similar internal
  components merely because timer or sensor names appear as external inputs.
- External timer/sensor signals remain inputs and functional requirements;
  they are not evidence that a source component exists.
- Do not invent physical RTL modules.
- Do not create a component for every individual operation or signal.
- Do not force a fixed number of components.
- Every component must be traceable to explicit specification requirements.


OUTPUT FIELD REQUIREMENTS:

1. system_purpose:

   Provide a concise description of the explicitly stated
   purpose of the system.

2. major_components:

   Include explicitly named components and meaningful functional
   groupings supported by the specification.

   Do not claim inferred groupings are mandatory physical modules.

3. inputs:

   Extract all explicitly defined input signals and interfaces.

   Preserve exact names and widths.

   Include explicitly stated input behavior when relevant.

   Every entry MUST follow the SIGNAL ENTRY FORMAT below.

4. outputs:

   Extract all explicitly defined output signals and interfaces.

   Preserve exact names and widths.

   Include explicitly stated output behavior when relevant.

   Every entry MUST follow the SIGNAL ENTRY FORMAT below.

5. functional_requirements:

   Extract every explicitly stated functional behavior.

   Pay particular attention to:

   - Supported operations and their selection conditions
   - Opcode mappings or command mappings
   - Input capture conditions
   - Output generation conditions
   - Reset behavior
   - Error handling
   - State transitions
   - Arithmetic and logical behavior
   - Timing-dependent behavior

   IMPORTANT REQUIREMENT EXTRACTION RULES:

   - Do not summarize or merge distinct functional requirements.
   - Extract every operation and its corresponding opcode separately.
   - If multiple operations are specified, include every operation.
   - Preserve all numeric values, conditions, and identifiers.
   - Extract arithmetic, logical, shift, reset, control, and
     error-handling behavior as separate requirements where the
     specification distinguishes them.
   - For each opcode or command mapping, record the exact opcode or
     command value, the selected operation, and any explicitly stated
     operand or result behavior.
   - Capture timing requirements explicitly, including input capture
     conditions, operation duration, one-cycle behavior, result and
     valid-signal timing, and busy-signal behavior where stated.
   - Do not combine the input, execution, output-valid, or busy
     conditions into one generic requirement when the specification
     defines them separately.
   - Include arithmetic overflow, underflow, truncation,
     saturation, and wrapping behavior whenever specified.
   For arithmetic operations, explicitly extract the specified
   overflow, underflow, wrapping, truncation, and saturation behavior.
   Do not assume standard arithmetic behavior when the specification
   defines a particular rule. Record that wrapping is modulo 2^32,
   modulo the declared width, or another specified modulus only when
   the specification states it; do not infer saturation when absent.
   - Include shift direction and shift amount whenever specified.
   - Include behavior for unsupported or invalid commands, including
     outputs or status changes explicitly defined for that condition.
   - Include all explicitly stated reset effects and reset timing.
   - Include the conditions under which outputs change.
   - Do not replace detailed requirements with generic statements.

   For example, do not write only:
   "The unit performs operations based on the opcode."

   Instead, extract each explicitly defined opcode mapping
   and its corresponding operation as a separate requirement.

6. constraints:

   Extract all explicitly stated constraints, including:

   - Clock frequency
   - Timing and latency
   - Reset requirements
   - Signal synchronization
   - Data widths
   - Arithmetic limitations
   - Resource constraints
   - Performance requirements
   - Protocol requirements
   - Implementation restrictions

   Extract explicitly stated implementation restrictions,
   including whether memory blocks, registers, or other hardware
   resources are required or prohibited.
   Preserve reset polarity and whether reset is synchronous
   or asynchronous.

   Preserve exact values and conditions.

7. ambiguities:

   Identify:

   - Explicit contradictions
   - Unclear requirements
   - Underspecified behavior
   - Missing information necessary to interpret an explicit requirement
   - Missing signal names, widths, timing, reset behavior,
     or protocol details when relevant

   Do not report a reset mode, polarity, or reset effect as unspecified when
   the specification states it explicitly. A missing clock edge or reset
   duration does not make separately stated reset requirements unknown;
   record only the missing detail as an ambiguity.

   Do not invent missing requirements.

   Do not report optional features as missing requirements.

   Use "NOT SPECIFIED: <item>" for relevant missing information.


SIGNAL ENTRY FORMAT (applies to every entry in inputs and outputs):

Each entry must be a single string in exactly this form:

    <signal_name> [MSB:LSB] : <description>

Rules for the format:

- <signal_name> is the exact identifier from the specification
  (letters, digits, underscores only). It must be the FIRST token.
- [MSB:LSB] is the bit range, for example [7:0] for an 8-bit signal.
  Include it ONLY for signals wider than 1 bit and ONLY when the
  width is stated. Omit it entirely for 1-bit signals.
- Use a colon to separate the name/width from the description.
- <description> is the specification's own comment, preserved as written.
  It is optional; omit the colon if there is no description.
- Do NOT use parentheses, "N-bit" wording, dashes, or commas between the
  name and the description. Do NOT put the width or description before
  the name.
- Do NOT add direction words such as "input" or "output" to the entry.

Correct examples:

    clk : system clock
    reset : system asynchronous reset
    car : a car wants to cross HWY
    data_in [7:0] : input data bus
    opcode [3:0]

Incorrect examples (never produce these):

    clk (1-bit, system clock)
    clk - system clock
    input clk : system clock
    8-bit data_in : input data bus

If a signal name is absent from the specification, use exactly:
"NOT SPECIFIED: signal name"


FINAL COMPLETENESS CHECK:

Before returning the structured output, internally review
the entire supplied specification.

Verify the following:

1. All explicitly defined inputs are extracted.
2. All explicitly defined outputs are extracted.
3. Every listed operation or supported function is captured and
   separated into arithmetic, logical, shifting, control, reset,
   result, or error behavior where the specification distinguishes it.
4. Every opcode or command mapping is captured individually, including
   its exact value and any explicitly defined operation behavior.
5. All input capture and output generation conditions are captured.
6. All one-cycle behavior, result timing, valid timing, and busy behavior
   explicitly stated in the specification are captured.
7. All reset conditions, polarity, reset timing, and reset effects are captured.
8. All timing and clock requirements are captured.
9. All arithmetic overflow, underflow, wrapping, truncation, and
   saturation behavior is captured without adding unspecified arithmetic rules.
10. All explicitly stated constraints are captured.
11. All stated ambiguities and contradictions are recorded.
12. Every identified functional component is supported by an explicit
    requirement, and operations with materially different behaviors are
    not merged into an overly generic component.
13. No unsupported hardware architecture or signal has been invented.
14. Every inputs and outputs entry follows the SIGNAL ENTRY FORMAT.

Do not return a partially summarized understanding when
the specification contains more detailed requirements.

OUTPUT RULES:

Return only information required by the Understanding schema.

Every list item in the JSON output must be a plain JSON string.
Never return dictionaries, nested objects, arrays, or other non-string
values inside major_components, inputs, outputs,
functional_requirements, constraints, or ambiguities.

The inputs, outputs, functional_requirements, constraints, and ambiguities
fields must contain arrays of strings, not arrays of objects.
Do not add fields that are absent from the Understanding schema.

For example, format the output exactly like this structure:

{
  "system_purpose": "Description",
  "major_components": ["Component 1", "Component 2"],
  "inputs": ["clk : system clock", "data_in [7:0] : input data bus"],
  "outputs": ["valid : result valid flag", "result [15:0] : operation result"],
  "functional_requirements": ["Requirement 1", "Requirement 2"],
  "constraints": ["Constraint 1"],
  "ambiguities": ["Ambiguity 1"]
}

Do not include explanations outside the structured response.

Accuracy, completeness, and faithfulness to the supplied
hardware specification are the highest priorities.
"""


# --------------------------------------------------------------------------
# Signal-entry normalization
#
# Downstream agents (RTL Generation) require every port entry to look like:
#     name [MSB:LSB] : description
# LLM output often drifts, e.g. "clk (1-bit, system clock)". The helpers
# below repair such entries deterministically so one stray format does not
# fail the whole pipeline.
# --------------------------------------------------------------------------

_PORT_NAME_RE = re.compile(r"^\s*([A-Za-z_]\w*)\s*(.*)$", re.DOTALL)
_RANGE_RE = re.compile(r"\[\s*(\d+)\s*:\s*(\d+)\s*\]")
_BITS_RE = re.compile(r"\b(\d+)\s*-?\s*bits?\b", re.IGNORECASE)
_LEADING_JUNK_RE = re.compile(r"^[\s:,;\-\u2013\u2014()]+")
_DIRECTION_RE = re.compile(r"^(?:input|output|inout)\s+", re.IGNORECASE)


def normalize_port(entry: str) -> str:
    """Rewrite a port string into 'name [MSB:LSB] : description'.

    Examples:
        'clk (1-bit, system clock)'   -> 'clk : system clock'
        'data_in (8-bit, input bus)'  -> 'data_in [7:0] : input bus'
        'opcode[3:0]'                 -> 'opcode [3:0]'
        'input car - a car waits'     -> 'car : a car waits'
        'NOT SPECIFIED: signal name'  -> unchanged
    """
    if not isinstance(entry, str):
        return entry

    text = entry.strip()
    if not text or text.upper().startswith("NOT SPECIFIED"):
        return text

    text = _DIRECTION_RE.sub("", text)

    match = _PORT_NAME_RE.match(text)
    if not match:
        return text  # cannot repair; let the downstream validator report it

    name, rest = match.group(1), match.group(2).strip()

    # Remove one outer pair of parentheses: "(1-bit, system clock)"
    if rest.startswith("(") and rest.endswith(")"):
        rest = rest[1:-1].strip()

    # Width: an explicit [MSB:LSB] wins, otherwise derive it from "N-bit".
    width = ""
    range_match = _RANGE_RE.search(rest)
    if range_match:
        width = f"[{range_match.group(1)}:{range_match.group(2)}]"
        rest = _RANGE_RE.sub("", rest, count=1)
    else:
        bits_match = _BITS_RE.search(rest)
        if bits_match:
            bits = int(bits_match.group(1))
            if bits > 1:
                width = f"[{bits - 1}:0]"
            rest = _BITS_RE.sub("", rest, count=1)

    description = _LEADING_JUNK_RE.sub("", rest).strip()
    if description.endswith(")") and description.count(")") > description.count("("):
        description = description[:-1].strip()
    description = description.rstrip(",;").strip()

    result = name
    if width:
        result += f" {width}"
    if description:
        result += f" : {description}"
    return result


def normalize_understanding_ports(parsed: dict) -> dict:
    """Normalize every inputs/outputs entry in a parsed Understanding dict."""
    for key in ("inputs", "outputs"):
        items = parsed.get(key)
        if isinstance(items, list):
            parsed[key] = [normalize_port(item) for item in items]
    return parsed


def create_understanding_agent():
    """Create the tool-free Understanding Agent."""
    return create_agent(
        model=get_llm("understanding"),
        tools=[],
        system_prompt=SYSTEM_PROMPT,
        response_format=None if is_free_openrouter_model("understanding") else Understanding,
    )


def _normalize_understanding_response_content(content: Any) -> str:
    """Extract text from string or LangChain content-block responses."""
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, str):
                text_parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                block_text = block.get("text", "")
                if isinstance(block_text, str):
                    text_parts.append(block_text)
        text = "".join(text_parts)
    else:
        raise ValueError(
            "Understanding Agent returned invalid output: "
            "response content is not text."
        )

    text = text.strip()
    if not text:
        raise ValueError("Understanding Agent returned empty response content.")
    return text


def _extract_understanding_json(content: Any) -> str:
    """Normalize response content and isolate its JSON object."""
    text = _normalize_understanding_response_content(content)

    # Strip optional markdown code fences (raw strings: single backslash).
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(
            "Understanding Agent returned invalid JSON output: "
            "no complete JSON object was found."
        )

    return text[start:end + 1]


def understand_specification(documents: Union[str, Document, List[Union[Document, str]]]) -> Understanding:

    if isinstance(documents, str):
        specification = documents.strip()
    elif isinstance(documents, Document):
        specification = documents.page_content.strip()
    elif isinstance(documents, (list, tuple)):
        specification = "\n\n".join(
            doc.page_content if hasattr(doc, "page_content") else str(doc)
            for doc in documents
        ).strip()
    else:
        specification = str(documents).strip()

    if not specification:
        raise ValueError("specification must not be empty")

    # Free OpenRouter models are used in this project. Call the model directly
    # once because the free-model agent path does not guarantee a structured_response.
    llm = get_llm("understanding")
    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=specification),
    ])

    print("RAW UNDERSTANDING RESPONSE CONTENT:")
    print(response.content)
    print("UNDERSTANDING RESPONSE METADATA:")
    print(getattr(response, "response_metadata", None))
    print("UNDERSTANDING RESPONSE USAGE METADATA:")
    print(getattr(response, "usage_metadata", None))

    content = _extract_understanding_json(response.content)

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Understanding Agent returned invalid JSON: "
            f"{exc.msg} at line {exc.lineno}, column {exc.colno}"
        ) from exc

    # Repair port strings such as "clk (1-bit, system clock)" before validation.
    if isinstance(parsed, dict):
        parsed = normalize_understanding_ports(parsed)

    try:
        return Understanding.model_validate(parsed)
    except ValidationError as exc:
        raise ValueError(
            "Understanding Agent returned JSON that does not match the "
            f"Understanding schema: {exc}"
        ) from exc
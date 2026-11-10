from langchain_core.callbacks import usage
from typing import List
from langchain.agents import create_agent
from langchain_core.documents import Document
from src.llm.llm import get_llm
from src.schemas import Understanding
from langchain_core.callbacks import UsageMetadataCallbackHandler

SYSTEM_PROMPT_UNCLEAR = """You are the Understanding Agent, the first stage of a hardware-to-RTL pipeline.

Your job is ONLY to extract and organize information explicitly stated in the hardware specification.

You are NOT an RTL designer at this stage.

CORE RULES:
1. Use only information explicitly present in the specification.
2. Do not infer, assume, calculate, redesign, or fill in missing information.
3. Do not generate RTL, pseudocode, architecture, algorithms, or implementation suggestions.
4. Do not resolve ambiguities or contradictions.
5. Do not invent signal names, widths, values, timing, protocols, components, or behaviors.
6. Preserve identifiers exactly as written in the specification.
7. Preserve numeric values, units, frequencies, widths, timing values, reset polarity, and protocol names exactly as written.
8. If the specification does not state something required by the schema field,
   leave that field empty. Do not write placeholders. The only place missing
   information may be reported is the ambiguities field, under its own rules.
9. If the specification contains conflicting information, record the conflict in ambiguities instead of choosing one interpretation.
10. Do not repeat large portions of the original specification. Extract concise structured information only.

SIGNAL RULE:
Only classify something as a signal if the specification explicitly identifies it as:
- a signal
- a port
- an input
- an output
- a clock
- a reset
- or a member of an explicitly defined interface.

Do not infer signals from functional descriptions.

For example:
"The engine receives packet data" does NOT justify inventing a signal named packet_data.

If the specification does not provide the signal name:
"NOT SPECIFIED: signal name"

OUTPUT:
Return ONLY information required by the Understanding schema.

The schema contains:

1. system_purpose
   - Concise description of the explicitly stated purpose of the system.
   - Do not add implementation details.

2. major_components
   - Components explicitly mentioned in the specification.
   - Do not create components based on your own architectural interpretation.

3. inputs
   - Explicitly defined input signals and interfaces.
   - Preserve exact signal names and widths.
   - Include explicitly stated input behavior when relevant.

4. outputs
   - Explicitly defined output signals and interfaces.
   - Preserve exact signal names and widths.
   - Include explicitly stated output behavior when relevant.

5. functional_requirements
   - Required behaviors explicitly stated in the specification.
   - Do not convert implied behavior into requirements.

6. constraints
   - Explicit timing, frequency, protocol, reset, performance, implementation,
     synthesis, clocking, and other design constraints.

7. ambiguities
   - Missing information
   - Contradictions
   - Unclear requirements
   - Underspecified behavior
   - Missing signal names, widths, timing, reset behavior, protocol details, etc.
   - Use "NOT SPECIFIED: <item>" when something expected by the specification is absent.

IMPORTANT:
Do not resolve any ambiguity.

Do not make assumptions about what the designer "probably meant".

The Understanding output will be consumed by downstream agents, so accuracy and
faithfulness to the source specification are more important than completeness.

Return concise structured information and nothing else.
1"""

AMBIGUITIES_SECTION = """
7. ambiguities
   Record places where the specification text leaves the design unclear.
   Every entry must be anchored to exact words in the specification.

   TYPES (start each entry with one):
   - "CONFLICT:"      two parts of the text state different values or behaviors.
                      Quote both. Do not choose one.
   - "UNCLEAR:"       one passage can be read in more than one way, or the prose
                      and an interface table describe the same thing differently.
                      Quote the passage(s). Do not choose a reading.
   - "NOT SPECIFIED:" the text names a signal, input, event, limit or phase but
                      does not state the behavior, condition or outcome that
                      goes with it. Quote the text that names it.

   WHERE TO LOOK:
   - A signal in an interface table with no described behavior
   - An input or event with no stated system response
   - Two inputs that can be active together, with no stated priority
   - A minimum or maximum with no stated condition for moving between them
   - One signal shared by several blocks, with no stated per-block behavior
   - A request that can arrive before it is allowed to act, with no stated handling
   - Prose that disagrees with an interface table

   RULES:
   1. Format: TYPE: <the gap in one sentence> ("<exact quote from spec>").
   2. No quote, no entry. Generic items (clock frequency, signal widths, safety or
      fault handling) are never listed unless the text itself mentions them.
   3. Before listing a gap, search the WHOLE spec (tables, captions, footnotes).
      If it is answered anywhere, do not list it.
   4. Compare against your own constraints and functional_requirements. If they
      already state it, do not list it.
   5. Never fill a gap. No "presumably", "likely", "probably", "should", and no
      suggested defaults.
   6. Order by how much of the design the gap affects.
   7. An empty list is valid. Do not pad.
"""
FEW_SHOT_EXAMPLES = """
EXAMPLES (format and judgment only; never reuse their content):

--- EXAMPLE 1 ---
SPECIFICATION:
Design a UART transmitter. Inputs: clk, rst_n (active-low, asynchronous),
tx_start, tx_data[7:0]. Outputs: tx, tx_busy. The transmitter sends one start
bit, 8 data bits LSB first, and one stop bit at 115200 baud. The system clock
is 50 MHz. tx_busy is high while a frame is being sent. Use a two-process FSM
coding style. Write a testbench to verify the design.

OUTPUT:
{
  "system_purpose": "Transmit 8-bit data serially as UART frames.",
  "major_components": ["UART transmitter", "FSM"],
  "inputs": ["clk", "rst_n - active-low, asynchronous", "tx_start", "tx_data[7:0]"],
  "outputs": ["tx", "tx_busy - high while a frame is being sent"],
  "functional_requirements": [
    "Send one start bit, 8 data bits LSB first, and one stop bit per frame",
    "Transmit at 115200 baud",
    "tx_busy is high while a frame is being sent"
  ],
  "constraints": [
    "System clock: 50 MHz",
    "Baud rate: 115200",
    "Reset rst_n: active-low, asynchronous",
    "Coding style: two-process FSM",
    "Verification: write a testbench"
  ],
  "ambiguities": [
    "NOT SPECIFIED: response when tx_start is asserted while a frame is in progress (\\"tx_busy is high while a frame is being sent\\"; no tx_start behavior stated).",
    "NOT SPECIFIED: whether tx_data is captured at tx_start or must be held (\\"tx_data[7:0]\\" listed with no capture behavior)."
  ]
}
WHY: Clock, baud, reset polarity and widths are stated, so they are not listed.
Each ambiguity quotes the text that names the signal and says what is missing.
Idle level of tx is not listed because no sentence in the text raises it.

--- EXAMPLE 2 ---
SPECIFICATION:
FIFO controller. Interface: clk, reset (active-high, synchronous), push, pop,
full, empty, almost_full. The FIFO holds 16 entries. A push is ignored when the
FIFO is full. [Section 4] The FIFO depth shall be 32 entries.

OUTPUT:
{
  "system_purpose": "Control a FIFO buffer with push and pop operations.",
  "major_components": ["FIFO controller"],
  "inputs": ["clk", "reset - active-high, synchronous", "push", "pop"],
  "outputs": ["full", "empty", "almost_full"],
  "functional_requirements": ["A push is ignored when the FIFO is full"],
  "constraints": ["Reset: active-high, synchronous"],
  "ambiguities": [
    "CONFLICT: FIFO capacity differs between sections (\\"The FIFO holds 16 entries\\" vs \\"The FIFO depth shall be 32 entries\\"). Neither chosen.",
    "NOT SPECIFIED: condition for asserting almost_full (\\"almost_full\\" listed in the interface; no threshold stated).",
    "NOT SPECIFIED: effect of pop when the FIFO is empty (\\"A push is ignored when the FIFO is full\\" is stated; nothing for pop).",
    "NOT SPECIFIED: priority when push and pop are active together (\\"push, pop\\" both listed as inputs; no combined behavior)."
  ]
}
WHY: The conflict quotes both sides and picks neither. almost_full appears as an
output but gets no invented behavior. Every gap quotes the text that raises it.

--- EXAMPLE 3 ---
SPECIFICATION:
Motor controller. Inputs: clk, rst, enable, speed_sel. Output: pwm_out.
The controller drives the motor "at the selected speed" when enable is high.
pwm_out is low when enable is low. Two speed levels are supported.

OUTPUT:
{
  "system_purpose": "Drive a motor at a selected speed using a PWM output.",
  "major_components": ["Motor controller"],
  "inputs": ["clk", "rst", "enable", "speed_sel"],
  "outputs": ["pwm_out"],
  "functional_requirements": [
    "Drive the motor at the selected speed when enable is high",
    "pwm_out is low when enable is low",
    "Two speed levels are supported"
  ],
  "constraints": [],
  "ambiguities": [
    "UNCLEAR: link between selection and speed levels (\\"at the selected speed\\" vs \\"Two speed levels are supported\\"; speed_sel is not tied to either). No reading chosen."
  ]
}
WHY: constraints is empty because the text states none. PWM frequency and duty
values are not listed because no sentence in the text raises them.
"""


SYSTEM_PROMPT = SYSTEM_PROMPT_UNCLEAR+ AMBIGUITIES_SECTION + FEW_SHOT_EXAMPLES

def create_understanding_agent():
    """Create the tool‑free Understanding Agent."""
    return create_agent(
        model=get_llm(),
        tools=[],
        system_prompt=SYSTEM_PROMPT,
        response_format=Understanding,
    )

def understand_specification(documents: List[Document]) -> Understanding:
    if not documents:
        raise ValueError("specification must not be empty")
    print(documents)
    specification = "\n\n".join(doc.page_content for doc in documents)
    print("==========================================================================")
    print(specification)

   
    agent = create_understanding_agent()
    token_usage = UsageMetadataCallbackHandler()

    result = agent.invoke(
    {
        "messages": [
            {"role": "user", "content": specification}
        ]
    },
    config={"callbacks": [token_usage]},)

    input_tokens = sum(
        data["input_tokens"]
        for data in token_usage.usage_metadata.values()
    )

    output_tokens = sum(
        data["output_tokens"]
        for data in token_usage.usage_metadata.values()
    )

    total_tokens = sum(
        data["total_tokens"]
        for data in token_usage.usage_metadata.values()
    )

    print("\n========== UNDERSTANDING AGENT TOKEN USAGE ==========")
    print(f"Input tokens:  {input_tokens}")
    print(f"Output tokens: {output_tokens}")
    print(f"Total tokens:  {total_tokens}")
    print("=====================================================\n")


    return result['structured_response']
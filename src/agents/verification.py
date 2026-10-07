 from src.schemas import DescriptionOutput
from langchain.agents import create_agent

from src.llm import get_llm
from src.schemas import VerificationResult
from src.agents.description import describe_component

SYSTEM_PROMPT = """You are the Verification Agent in the Spec2RTL-Agent system.

Compare the supplied hardware specification with the supplied RTL using
static review only.

Do not claim that the RTL was compiled, simulated, or formally verified.
Do not generate or modify RTL.
Do not assume behavior that is not stated in the specification.

Check the RTL for:
- Required modules, ports, signal names, and widths
- Functional behavior explicitly required by the specification
- Reset, clock, and timing behavior where specified
- Obvious incomplete or contradictory logic

For VerificationResult:
- Set valid to true only when the RTL appears to satisfy the explicit
  requirements and no clear mismatch is found by static review.
- Set valid to false when a clear mismatch or missing required behavior is
  found.
- Put mismatches and anything that cannot be established by static review in
  issues. Do not present uncertain conclusions as facts.
- Suggest relevant simulator tests in suggestions. Static review is not a
  substitute for compilation or simulation.
- Explain the review scope and evidence in reasoning, including that no
  simulator was run.

The final response must conform strictly to the VerificationResult schema.
"""


def create_verification_agent():
    return create_agent(
        model=get_llm(),
        tools=[],
        response_format=VerificationResult,
        system_prompt=SYSTEM_PROMPT
    )


def verify_description(
    source_chunks: list,
    description: DescriptionOutput
) -> VerificationResult:

    agent = create_verification_agent()

    specifications = "\n\n".join(
      doc.page_content for doc in source_chunks 
    )


    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": f"""
Original Specification:
{specifications}

RTL Description to Verify:
{description.model_dump_json(indent=2)}

Verify only the component represented by the RTL description.

Identify the relevant specification requirements for this component and ignore unrelated components.

Perform static verification only.
"""
                }
            ]
        }
    )

    return result["structured_response"]
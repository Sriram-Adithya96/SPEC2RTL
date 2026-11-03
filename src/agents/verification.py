from langchain.agents import create_agent
from langchain_core.documents import Document

from src.llm.llm import get_llm
from src.schemas import CodeOuput, VerificationResult


SYSTEM_PROMPT = """You are the Verification Agent in the Spec2RTL-Agent system.

Your task is to verify generated Python code against the original hardware specification.

Use static code review only.

The original hardware specification is the source of truth.
The generated Python code is the implementation being verified.

Check the following:

1. Whether the code implements the functionality required by the specification.
2. Whether all required inputs and outputs are correctly handled.
3. Whether signal names and widths are correctly represented.
4. Whether the operations and calculations follow the specified behavior.
5. Whether all required functional requirements are implemented.
6. Whether any required behavior is missing.
7. Whether the code contains behavior that contradicts the specification.
8. Whether constraints and special conditions are followed.

Important rules:

- Do not invent requirements.
- Do not assume behavior that is not stated in the specification.
- Do not modify or rewrite the generated code.
- Do not generate new code.
- Do not execute or compile the code.
- Do not claim that simulation or formal verification was performed.
- Use only the supplied specification evidence.
- If the evidence is insufficient to verify something, clearly mention it.

For VerificationResult:

- Set valid to true only when no clear mismatch is found.
- Set valid to false when a clear implementation error or missing required behavior is found.
- Record identified problems in issues.
- Give possible corrections in suggestions without writing replacement code.
- Explain the verification decision in reasoning.

The final response must conform strictly to the VerificationResult schema.
"""


def create_verification_agent():
    return create_agent(
        model=get_llm(),
        tools=[],
        response_format=VerificationResult,
        system_prompt=SYSTEM_PROMPT
    )


def verify_code(
    source_chunks: list[Document],
    generated_code: CodeOuput
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
Original Hardware Specification:
{specifications}

Generated Python Code:
{generated_code.code}

Component Name:
{generated_code.component_name}

Assumptions:
{generated_code.assumptions}

Perform static verification of the generated code against
the original hardware specification.

Do not execute the code.
"""
                }
            ]
        }
    )

    return result["structured_response"]

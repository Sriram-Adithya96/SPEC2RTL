from langchain.agents import create_agent
from langchain_core.documents import Document

from src.llm.llm import get_llm
from src.schemas import CodeOuput, VerificationResult


SYSTEM_PROMPT = """You are the Reflection Agent in the Spec2RTL-Agent system.

Your task is to analyze the output of the Verification Agent.

You will receive:
- The original hardware specification
- The generated Python code
- The verification result

When verification fails:
- Analyze the issues identified by the Verification Agent.
- Identify exactly what needs to be corrected in the generated code.
- Return the complete corrected CodeOuput directly.

Rules:
- Return a complete replacement for the generated CodeOuput.
- Do not invent hardware requirements.
- Base all corrections on the original specification.
- Do not silently resolve ambiguities.
- Preserve the existing implementation and its assumptions where the
  specification does not support a safe change.
- Return the result strictly according to the CodeOuput schema.
"""


def create_reflection_agent():
    return create_agent(
        model=get_llm(),
        tools=[],
        response_format=CodeOuput,
        system_prompt=SYSTEM_PROMPT
    )


def reflect_on_verification(
    source_chunks: list[Document],
    generated_code: CodeOuput,
    verification: VerificationResult
) -> CodeOuput:

    if verification.valid:
        return generated_code

    agent = create_reflection_agent()

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

Verification Result:
{verification.model_dump_json(indent=2)}

Analyze the verification issues and return the complete corrected CodeOuput.
"""
                }
            ]
        }
    )

    return result["structured_response"]

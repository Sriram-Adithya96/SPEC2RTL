from langchain.agents import create_agent
from langchain_core.documents import Document

from src.llm.llm import get_llm
from src.schemas import CodeOuput, ReflectionOutput, VerificationResult


SYSTEM_PROMPT = """You are the Reflection Agent in the Spec2RTL-Agent system.

Your task is to analyze the output of the Verification Agent.

You will receive:
- The original hardware specification
- The generated Python code
- The verification result

If verification is successful:
- Set needs_revision to false.
- Return an empty feedback list.

If verification fails:
- Analyze the issues identified by the Verification Agent.
- Identify exactly what needs to be corrected in the generated code.
- Provide clear, specific feedback for the Coder Agent.
- Set needs_revision to true when corrections are supported by the specification.
- Return the complete corrected CodeOuput in corrected_code.

Rules:
- The corrected_code must be a complete replacement for the generated code.
- Do not invent hardware requirements.
- Base all corrections on the original specification.
- Do not silently resolve ambiguities.
- If a safe correction cannot be supported by the specification, explain the
  unresolved issue in feedback and do not claim that the code is corrected.
- Return the result strictly according to the ReflectionOutput schema.
"""


def create_reflection_agent():
    return create_agent(
        model=get_llm(),
        tools=[],
        response_format=ReflectionOutput,
        system_prompt=SYSTEM_PROMPT
    )


def reflect_on_verification(
    source_chunks: list[Document],
    generated_code: CodeOuput,
    verification: VerificationResult
) -> ReflectionOutput:

    if verification.valid:
        return ReflectionOutput(
            needs_revision=False,
            feedback=[],
            reasoning="Verification passed. No code revision required.",
            corrected_code=None,
        )

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

Analyze the verification issues and return the complete corrected code.
"""
                }
            ]
        }
    )

    return result["structured_response"]
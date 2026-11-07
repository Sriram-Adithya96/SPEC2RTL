
from langchain.agents import create_agent

from src.schemas import DescriptionOutput, CodeOuput
from src.llm.llm import get_llm


SYSTEM_PROMPT = """
You are a code generation agent in the SPEC2RTL pipeline.

Your task is to generate Python code from a verified component description.

Rules:
- Follow the component description strictly.
- Generate code only for the specified component.
- Do not invent functionality, inputs, outputs, or dependencies.
- Use clear function and variable names.
- Include necessary imports.
- Make the implementation consistent with the specified requirements.
- If the description is ambiguous, identify the ambiguity instead
  of silently inventing behavior.
- When feedback is provided, correct the previous code according
  to that feedback.
- Preserve correct parts of the previous code.
- Do not introduce changes unrelated to the feedback.
"""

llm = get_llm()


def generate_code(
    description: DescriptionOutput,
    feedback: list[str] | None = None,
    previous_code: CodeOuput | None = None
) -> CodeOuput:

    agent = create_agent(
        model=llm,
        system_prompt=SYSTEM_PROMPT,
        response_format=CodeOuput
    )

    djson = description.model_dump_json()

    if previous_code is None:
        task = f"""
Generate Python code for this verified component:

{djson}
"""
    else:
        task = f"""
Revise the previously generated Python code.

Component Description:
{djson}

Previous Code:
{previous_code.code}

Previous Assumptions:
{previous_code.assumptions}

Reflection Agent Feedback:
{feedback}

Correct the code according to the feedback.
Return the complete revised code.
"""

    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": task
                }
            ]
        }
    )

    return result["structured_response"]

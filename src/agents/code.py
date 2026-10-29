from langchain.agents import create_agent 
from src.schemas import DescriptionOutput , CodeOuput 
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
"""

llm = get_llm()


def generate_code(description:DescriptionOutput):
    agent = create_agent(model  = llm ,system_prompt=SYSTEM_PROMPT , response_format=CodeOuput)
    djson = description.model_dump_json()
    result= agent.invoke(
        {
            'messages':[
                {
                    "role": "user",
                    "content": (
                        "Generate Python code for this verified component:\n\n"
                        f"{djson}"
                    ),
                }

            ]
        }
    )
    return result['structured_response']






    


    
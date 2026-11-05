from langchain.agents import create_agent 
from src.schemas import CodeOuput, DescriptionOutput, PseudocodeGenerationOutput
from src.llm.llm import get_llm 

SYSTEM_PROMPT = """
You are a code generation agent in the SPEC2RTL pipeline.

Your task is to generate RTL code for the complete hardware system from its
verified pseudocode and all component descriptions.

Rules:
- Follow the pseudocode and component descriptions strictly.
- Generate one complete RTL implementation for the entire hardware system.
- Include all described components and their interactions.
- Do not invent functionality, inputs, outputs, or dependencies.
- Use clear function and variable names.
- Include necessary imports.
- Make the implementation consistent with the specified requirements.
- If the description is ambiguous, identify the ambiguity instead
  of silently inventing behavior.
"""

llm = get_llm()


def generate_code(
    pseudocode: PseudocodeGenerationOutput,
    descriptions: list[DescriptionOutput],
) -> CodeOuput:
    agent = create_agent(
        model=llm,
        system_prompt=SYSTEM_PROMPT,
        response_format=CodeOuput,
    )
    descriptions_json = "\n\n".join(
        description.model_dump_json(indent=2)
        for description in descriptions
    )
    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Generate complete RTL code for the verified hardware "
                        "system.\n\n"
                        "Pseudocode:\n"
                        f"{pseudocode.model_dump_json(indent=2)}\n\n"
                        "All component descriptions:\n"
                        f"{descriptions_json}"
                    ),
                }
            ]
        }
    )
    return result["structured_response"]

    


    
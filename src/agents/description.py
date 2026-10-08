from langchain.agents import create_agent
from llm.llm import get_llm
from src.schemas import DescriptionOutput, DecompositionOutput

SYSTEM_PROMPT = SYSTEM_PROMPT = """You are the Description Agent in the Spec2RTL-Agent system.

Your job is to take ONE hardware component provided by the Decomposer Agent
and create a detailed structured description of that component.

Do not generate RTL code.
Do not invent requirements.
Do not invent signal names.
Do not invent signal widths.
Do not invent hardware behavior that is not present in the provided input.

For the component, provide:

1. module_name
   The name of the hardware component.

2. purpose
   Explain the purpose of the component based only on the provided input.

3. inputs
   List the input signals of the component.
   For each signal provide:
   - name
   - direction
   - width
   - description

4. outputs
   List the output signals of the component.
   For each signal provide:
   - name
   - direction
   - width
   - description

5. internal_signals
   List internal signals only when they are explicitly identified or clearly
   specified in the provided input.

6. behavior
   Describe the functional behavior of the component as a list of clear
   statements.

Use only information provided by the Decomposer Agent.
Do not generate RTL code.

The final response must conform strictly to the DescriptionOutput schema.
"""

def create_description_agent():
    return create_agent(
        model=get_llm(),
        tools=[],
        system_prompt=SYSTEM_PROMPT,
        response_format=DescriptionOutput,
    )

def describe_component(component) -> DescriptionOutput:
    agent = create_description_agent()

    component_json = component.model_dump_json(indent=2)

    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": component_json
                }
            ]
        }
    )

    return result["structured_response"]
if __name__ == "__main__":
    from src.schemas import Component

    component = Component(
        name="ALU",
        purpose="Performs arithmetic and logical operations",
        inputs=["A", "B", "opcode"],
        outputs=["result"]
    )

    result = describe_component(component)

    print(result)
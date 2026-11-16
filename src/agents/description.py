from langchain.agents import create_agent
from src.llm.llm import get_llm
from src.schemas import Component, DescriptionOutput

SYSTEM_PROMPT = """You are the Description Agent in the Spec2RTL-Agent system.

Your job is to take ONE hardware component provided by the Decomposer Agent
and create a detailed structured description of that component.

Do not generate RTL code.
Do not invent requirements.
Do not invent signal names.
Do not invent signal widths.
Do not invent hardware behavior that is not present in the provided input.

Return exactly the fields required by DescriptionOutput:

1. module_name
   The name of the hardware component.

2. purpose
   Explain the purpose of the component based only on the provided input.

3. inputs
   List the input signals of the component.
   For each signal provide:
   - name
   - direction, set to "input"
   - width; if the input does not specify it, use "not specified in input"
   - description

4. outputs
   List the output signals of the component.
   For each signal provide:
   - name
   - direction, set to "output"
   - width; if the input does not specify it, use "not specified in input"
   - description

5. state_elements
   List state elements only when they are explicitly identified in the input.
   Each item must include name, type, width, reset_value, and description.
   Do not treat unspecified internal signals as state elements.

6. constraints
   List only explicitly stated constraints. Use an empty list if none are given.

7. behavior
   Describe the functional behavior of the component as a list of clear
   statements.

8. spec_references
   List only references explicitly present in the input. Use an empty list if
   none are given.

If a state element's type, width, or reset value is not specified, do not
invent it; use "not specified in input" for that field.
Use empty lists for fields with no supported items.

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

def describe_component(component: Component) -> DescriptionOutput:
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
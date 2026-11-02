from langchain.agents import create_agent
from src.llm.llm import get_llm
from src.schemas import DescriptionOutput, DecompositionOutput

SYSTEM_PROMPT = """You are the Description Agent in the Spec2RTL-Agent system.

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

Use the original component information and any supplied reflection feedback.
Treat feedback as suggested corrections, not as new hardware requirements.
Never invent details missing from the original component.

The final response must conform strictly to the DescriptionOutput schema.
"""

def create_description_agent():
    return create_agent(
        model=get_llm(),
        tools=[],
        system_prompt=SYSTEM_PROMPT,
        response_format=DescriptionOutput,
    )

def describe_component(
    component,
    feedback=None,
    previous_description=None
) -> DescriptionOutput:

    agent = create_description_agent()

    component_json = component.model_dump_json(indent=2)

    if feedback is None:
        prompt = component_json

    else:
        prompt = f"""
        Original Component:
        {component_json}

        Previous Description:
        {previous_description.model_dump_json(indent=2)
         if previous_description else "None"}

        Reflection Feedback:
        {feedback}

        Revise the previous description using the feedback.

        Only make corrections supported by the original component.
        Do not invent missing requirements.
        """

    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
    )

    return result["structured_response"]
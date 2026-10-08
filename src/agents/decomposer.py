from textwrap import indent
from langchain.agents import create_agent 
from llm.llm import get_llm 
from src.schemas import DecompositionOutput, Understanding 




SYSTEM_PROMPT = """You are the Decomposer Agent in the Spec2RTL-Agent system, a multi-agent system that converts complex hardware specification documents into RTL (Register Transfer Level) code.

Your primary responsibility is to take the structured hardware understanding output from the Understanding Agent and break down the complete hardware design into smaller, manageable sub-modules or sub-functions.

Large hardware systems should not be generated in one step. Your decomposition allows the subsequent agents to implement each module separately.

INPUT:
You will receive structured information (like JSON) containing:
- Hardware purpose
- Inputs
- Outputs
- Functional requirements
- Constraints
- Important equations
- Relevant tables and information

TASK:
1. Decompose the Design: Break down the overall hardware system into smaller, logical sub-modules. For example, a CPU can be broken down into a Controller, ALU, Register File, Instruction Decoder, and Memory Interface. A FIFO can be broken down into Memory, Write pointer, Read pointer, Full logic, and Empty logic.
2. Create an Implementation Plan: Outline the sequence of steps needed to build the complete system. For example, an implementation plan for a FIFO might be: Create memory, Create write logic, Create read logic, Create status flags, and finally Connect modules.

OUTPUT FORMAT:
Output your decomposition and implementation plan in a structured format (such as JSON) that clearly lists the sub-modules and the step-by-step implementation plan.
"""


def create_decomposer_agent():
    return create_agent(
        model = get_llm(),
        tools = [], 
        system_prompt=SYSTEM_PROMPT,
        response_format=DecompositionOutput,
    )


def decomposer(understanding: Understanding )->DecompositionOutput:
    agent = create_decomposer_agent()
    understanding_json = understanding.model_dump_json(indent=42)
    result = agent.invoke(
        {
            "messages":[
                {
                    "role":"user",
                    "content":understanding_json 
                    
                }
            ]
        }
    )
    return result['structured_response']



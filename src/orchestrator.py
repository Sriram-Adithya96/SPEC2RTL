
from typing import TypedDict

from langgraph.graph import StateGraph, START, END  

from src.ingestion import ingest_spec
from src.agents.understanding import understand_specification
from src.agents.decomposer import decomposer
from src.agents.description import describe_component
from src.agents.code import generate_code
from src.agents.verification import verify_code
from src.schemas import CodeOuput, DecompositionOutput, Understanding, VerificationResult


class Spec2RTLState(TypedDict):
    file_path: str
    parent: list
    understanding: Understanding
    decomposition: DecompositionOutput
    generated_code: list[str]
    generated_outputs: list[CodeOuput]
    status: str
    verification: list[VerificationResult]
    iteration: int


def ingest_node(state: Spec2RTLState):
    parent, children = ingest_spec(state["file_path"])
    return {"parent": parent}


def understanding_node(state: Spec2RTLState):
    result = understand_specification(state["parent"])
    return {"understanding": result}


def decomposition_node(state: Spec2RTLState):
    result = decomposer(state["understanding"])
    return {"decomposition": result}


def generation_node(state: Spec2RTLState):
    code = []
    generated_outputs = []

    for component in state["decomposition"].components:
        description = describe_component(component)
        result = generate_code(description)
        code.append(result.code)
        generated_outputs.append(result)

    return {
        "generated_code": code,
        "generated_outputs": generated_outputs,
        "status": "generated",
    }


def verify_node(state: Spec2RTLState):
    verification = [
        verify_code(state["parent"], generated_output)
        for generated_output in state["generated_outputs"]
    ]
    return {
        "verification": verification,
        "status": "verified",
    }


# pyrefly: ignore[bad-specialization]
builder = StateGraph(Spec2RTLState)
builder.add_node("ingest", ingest_node)
builder.add_node("understand", understanding_node)
builder.add_node("decompose", decomposition_node)
builder.add_node("generate", generation_node)
builder.add_node("verify", verify_node)

builder.add_edge(START, "ingest")
builder.add_edge("ingest", "understand")
builder.add_edge("understand", "decompose")
builder.add_edge("decompose", "generate")
builder.add_edge("generate", "verify")
builder.add_edge("verify", END)

graph = builder.compile()

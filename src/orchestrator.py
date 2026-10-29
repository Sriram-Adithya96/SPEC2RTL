
from typing  import TypedDict

from langgraph.graph import StateGraph, START, END

from src.ingestion import ingest_spec
from src.agents.understanding import understand_specification
from src.agents.decomposer import decomposer
from src.agents.description import describe_component
from src.agents.code import generate_code
from src.schemas import Understanding, DecompositionOutput


class Spec2RTLState(TypedDict):
    file_path: str
    parent: list
    understanding: Understanding
    decomposition: DecompositionOutput
    generated_code: list[str]
    status: str


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

    for component in state["decomposition"].components:
        description = describe_component(component)
        result = generate_code(description)
        code.append(result.code)

    return {
        "generated_code": code,
        "status": "generated",
    }


# pyrefly: ignore[bad-specialization]
builder = StateGraph(Spec2RTLState)
builder.add_node("ingest", ingest_node)
builder.add_node("understand", understanding_node)
builder.add_node("decompose", decomposition_node)
builder.add_node("generate", generation_node)

builder.add_edge(START, "ingest")
builder.add_edge("ingest", "understand")
builder.add_edge("understand", "decompose")
builder.add_edge("decompose", "generate")
builder.add_edge("generate", END)

graph = builder.compile()

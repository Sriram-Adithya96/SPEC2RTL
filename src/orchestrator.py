
from typing import TypedDict

from langgraph.graph import StateGraph, START, END  

from src.ingestion import ingest_spec
from src.agents.understanding import understand_specification
from src.agents.decomposer import decomposer
from src.agents.description import describe_component
from src.agents.code import generate_code
from src.agents.pseudocode import generate_pseudocode
from src.agents.verification import verify_code
from src.schemas import (
    CodeOuput,
    DecompositionOutput,
    DescriptionOutput,
    PseudocodeGenerationOutput,
    Understanding,
    VerificationResult,
)


class Spec2RTLState(TypedDict):
    file_path: str
    parent: list
    understanding: Understanding
    decomposition: DecompositionOutput
    descriptions: list[DescriptionOutput]
    pseudocode: PseudocodeGenerationOutput
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


def description_node(state: Spec2RTLState):
    descriptions = [
        describe_component(component)
        for component in state["decomposition"].components
    ]
    return {"descriptions": descriptions}


def pseudocode_node(state: Spec2RTLState):
    specification = "\n\n".join(
        document.page_content for document in state["parent"]
    )
    result = generate_pseudocode(
        specification=specification,
        decomposition=state["decomposition"],
        descriptions=state["descriptions"],
        understanding=state["understanding"],
    )
    return {"pseudocode": result}


def generation_node(state: Spec2RTLState):
    result = generate_code(
        pseudocode=state["pseudocode"],
        descriptions=state["descriptions"],
    )

    return {
        "generated_code": [result.code],
        "generated_outputs": [result],
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
builder.add_node("describe", description_node)
builder.add_node("pseudocode", pseudocode_node)
builder.add_node("generate", generation_node)
builder.add_node("verify", verify_node)

builder.add_edge(START, "ingest")
builder.add_edge("ingest", "understand")
builder.add_edge("understand", "decompose")
builder.add_edge("decompose", "describe")
builder.add_edge("describe", "pseudocode")
builder.add_edge("pseudocode", "generate")
builder.add_edge("generate", "verify")
builder.add_edge("verify", END)

graph = builder.compile()

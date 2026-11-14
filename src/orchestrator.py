
from typing import TypedDict

from langgraph.graph import StateGraph, START, END  

from src.ingestion import ingest_spec
from src.agents.understanding import understand_specification
from src.agents.decomposer import decomposer
from src.agents.description import describe_component
from src.agents.code import generate_code
from src.agents.pseudocode import generate_pseudocode
from src.agents.reflection import reflect_on_verification
from src.agents.verification import verify_code
from src.schemas import (
    CodeOuput,
    DecompositionOutput,
    DescriptionOutput,
    PseudocodeGenerationOutput,
    Understanding,
    VerificationResult,
)

MAX_REFLECTION_TRIES = 2


class Spec2RTLState(TypedDict):
    file_path: str
    parent: list
    children: list
    understanding: Understanding
    decomposition: DecompositionOutput
    descriptions: list[DescriptionOutput]
    pseudocode: PseudocodeGenerationOutput
    generated_code: list[str]
    generated_outputs: list[CodeOuput]
    status: str
    verification: list[VerificationResult]
    reflection: list[CodeOuput]
    iteration: int


def ingest_node(state: Spec2RTLState):
    parent, children = ingest_spec(state["file_path"])
    return {"parent": parent, "children": children, "iteration": 0}


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
    if not state["generated_outputs"]:
        raise ValueError("Cannot verify an empty generated_outputs list")
    verification = [
        verify_code(state["children"], generated_output)
        for generated_output in state["generated_outputs"]
    ]
    return {
        "verification": verification,
        "status": (
            "verified"
            if all(result.valid for result in verification)
            else "verification_failed"
        ),
    }


def reflection_node(state: Spec2RTLState):
    if len(state["generated_outputs"]) != len(state["verification"]):
        raise ValueError(
            "generated_outputs and verification must contain the same number "
            "of items before reflection"
        )

    reflections = [
        reflect_on_verification(
            state["children"],
            generated_output,
            verification,
        )
        for generated_output, verification in zip(
            state["generated_outputs"],
            state["verification"],
        )
    ]

    return {
        "reflection": reflections,
        "generated_outputs": reflections,
        "generated_code": [output.code for output in reflections],
        "iteration": state["iteration"] + 1,
        "status": "revised",
    }


def route_after_verification(state: Spec2RTLState):
    if all(result.valid for result in state["verification"]):
        return END
    if state["iteration"] >= MAX_REFLECTION_TRIES:
        return END
    return "reflect"


def route_after_reflection(state: Spec2RTLState):
    return "verify"


builder = StateGraph(Spec2RTLState)  # pyrefly: ignore[bad-specialization]
builder.add_node("ingest", ingest_node)
builder.add_node("understand", understanding_node)
builder.add_node("decompose", decomposition_node)
builder.add_node("describe", description_node)
builder.add_node("pseudocode", pseudocode_node)
builder.add_node("generate", generation_node)
builder.add_node("verify", verify_node)
builder.add_node("reflect", reflection_node)

builder.add_edge(START, "ingest")
builder.add_edge("ingest", "understand")
builder.add_edge("understand", "decompose")
builder.add_edge("decompose", "describe")
builder.add_edge("describe", "pseudocode")
builder.add_edge("pseudocode", "generate")
builder.add_edge("generate", "verify")
builder.add_conditional_edges(
    "verify",
    route_after_verification,
    {"reflect": "reflect", END: END},
)
builder.add_conditional_edges(
    "reflect",
    route_after_reflection,
    {"verify": "verify", END: END},
)

graph = builder.compile()

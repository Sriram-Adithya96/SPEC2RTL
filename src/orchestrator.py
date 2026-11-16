

from typing import TypedDict, Annotated, Callable, Any

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

from langchain_core.callbacks import get_usage_metadata_callback
from langchain_core.messages.ai import UsageMetadata, add_usage


MAX_REFLECTION_TRIES = 2


# --------------------------------------------------
# 1. TOKEN MERGE FUNCTIONS
# --------------------------------------------------

def merge_agent_tokens(
    existing: dict | None,
    new: dict | None
) -> dict:

    merged = dict(existing or {})

    for agent, usage in (new or {}).items():

        if agent in merged:
            merged[agent] = add_usage(merged[agent], usage)
        else:
            merged[agent] = usage

    return merged


def merge_total_tokens(
    existing: UsageMetadata | None,
    new: UsageMetadata | None
) -> UsageMetadata | None:

    if existing is None:
        return new

    if new is None:
        return existing

    return add_usage(existing, new)


# --------------------------------------------------
# 2. TOKEN TRACKING FUNCTION
# --------------------------------------------------

def run_with_token_tracking(
    agent_name: str,
    agent_function: Callable,
    *args,
    **kwargs
):

    with get_usage_metadata_callback() as callback:

        result = agent_function(*args, **kwargs)

    agent_usage = None

    # Collect usage from all LLM calls made by this agent
    for usage in callback.usage_metadata.values():

        if agent_usage is None:
            agent_usage = usage
        else:
            agent_usage = add_usage(agent_usage, usage)

    token_updates = {}

    if agent_usage is not None:

        token_updates = {
            "agent_tokens": {
                agent_name: agent_usage
            },
            "total_tokens": agent_usage
        }

    return result, token_updates


# --------------------------------------------------
# 3. LANGGRAPH STATE
# --------------------------------------------------

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

    # Individual agent token usage
    agent_tokens: Annotated[
        dict[str, UsageMetadata],
        merge_agent_tokens
    ]

    # Overall pipeline token usage
    total_tokens: Annotated[
        UsageMetadata | None,
        merge_total_tokens
    ]


# --------------------------------------------------
# 4. INGESTION NODE
# --------------------------------------------------

def ingest_node(state: Spec2RTLState):

    parent, children = ingest_spec(state["file_path"])

    return {
        "parent": parent,
        "children": children,
        "iteration": 0
    }


# --------------------------------------------------
# 5. UNDERSTANDING NODE
# --------------------------------------------------

def understanding_node(state: Spec2RTLState):

    result, tokens = run_with_token_tracking(
        "understanding",
        understand_specification,
        state["parent"]
    )

    return {
        "understanding": result,
        **tokens
    }


# --------------------------------------------------
# 6. DECOMPOSITION NODE
# --------------------------------------------------

def decomposition_node(state: Spec2RTLState):

    result, tokens = run_with_token_tracking(
        "decomposer",
        decomposer,
        state["understanding"]
    )

    return {
        "decomposition": result,
        **tokens
    }


# --------------------------------------------------
# 7. DESCRIPTION NODE
# --------------------------------------------------

def description_node(state: Spec2RTLState):

    def describe_all():

        return [
            describe_component(component)
            for component in state["decomposition"].components
        ]

    descriptions, tokens = run_with_token_tracking(
        "description",
        describe_all
    )

    return {
        "descriptions": descriptions,
        **tokens
    }


# --------------------------------------------------
# 8. PSEUDOCODE NODE
# --------------------------------------------------

def pseudocode_node(state: Spec2RTLState):

    specification = "\n\n".join(
        document.page_content
        for document in state["parent"]
    )

    result, tokens = run_with_token_tracking(
        "pseudocode",
        generate_pseudocode,
        specification=specification,
        decomposition=state["decomposition"],
        descriptions=state["descriptions"],
        understanding=state["understanding"]
    )

    return {
        "pseudocode": result,
        **tokens
    }


# --------------------------------------------------
# 9. CODE GENERATION NODE
# --------------------------------------------------

def generation_node(state: Spec2RTLState):

    result, tokens = run_with_token_tracking(
        "code_generation",
        generate_code,
        pseudocode=state["pseudocode"],
        descriptions=state["descriptions"]
    )

    return {
        "generated_code": [result.code],
        "generated_outputs": [result],
        "status": "generated",
        **tokens
    }


# --------------------------------------------------
# 10. VERIFICATION NODE
# --------------------------------------------------

def verify_node(state: Spec2RTLState):

    if not state["generated_outputs"]:

        raise ValueError(
            "Cannot verify an empty generated_outputs list"
        )

    def verify_all():

        return [
            verify_code(
                state["children"],
                generated_output
            )
            for generated_output in state["generated_outputs"]
        ]

    verification, tokens = run_with_token_tracking(
        "verification",
        verify_all
    )

    return {
        "verification": verification,

        "status": (
            "verified"
            if all(result.valid for result in verification)
            else "verification_failed"
        ),

        **tokens
    }


# --------------------------------------------------
# 11. REFLECTION NODE
# --------------------------------------------------

def reflection_node(state: Spec2RTLState):

    if len(state["generated_outputs"]) != len(state["verification"]):

        raise ValueError(
            "generated_outputs and verification must contain "
            "the same number of items before reflection"
        )

    def reflect_all():

        return [
            reflect_on_verification(
                state["children"],
                generated_output,
                verification
            )

            for generated_output, verification in zip(
                state["generated_outputs"],
                state["verification"]
            )
        ]

    reflections, tokens = run_with_token_tracking(
        "reflection",
        reflect_all
    )

    return {
        "reflection": reflections,

        "generated_outputs": reflections,

        "generated_code": [
            output.code
            for output in reflections
        ],

        "iteration": state["iteration"] + 1,

        "status": "revised",

        **tokens
    }


# --------------------------------------------------
# 12. CONDITIONAL ROUTING
# --------------------------------------------------

def route_after_verification(state: Spec2RTLState):

    # If verification passes, stop
    if all(result.valid for result in state["verification"]):

        return END

    # Stop after maximum reflection attempts
    if state["iteration"] >= MAX_REFLECTION_TRIES:

        return END

    # Otherwise, reflect and improve the generated code
    return "reflect"


def route_after_reflection(state: Spec2RTLState):

    return "verify"


# --------------------------------------------------
# 13. BUILD LANGGRAPH
# --------------------------------------------------

builder = StateGraph(Spec2RTLState)

builder.add_node("ingest", ingest_node)
builder.add_node("understand", understanding_node)
builder.add_node("decompose", decomposition_node)
builder.add_node("describe", description_node)
builder.add_node("pseudocode", pseudocode_node)
builder.add_node("generate", generation_node)
builder.add_node("verify", verify_node)
builder.add_node("reflect", reflection_node)


# Define workflow edges

builder.add_edge(START, "ingest")

builder.add_edge("ingest", "understand")
builder.add_edge("understand", "decompose")
builder.add_edge("decompose", "describe")
builder.add_edge("describe", "pseudocode")
builder.add_edge("pseudocode", "generate")
builder.add_edge("generate", "verify")


# Verification routing

builder.add_conditional_edges(
    "verify",
    route_after_verification,
    {
        "reflect": "reflect",
        END: END
    }
)


# Reflection goes back to verification

builder.add_conditional_edges(
    "reflect",
    route_after_reflection,
    {
        "verify": "verify"
    }
)


# Compile graph

graph = builder.compile()


# --------------------------------------------------
# 14. DISPLAY TOKEN USAGE
# --------------------------------------------------

def display_token_usage(state):

    print("\n========== TOKEN USAGE ==========")

    for agent, usage in state.get("agent_tokens", {}).items():

        print(f"\nAgent: {agent}")

        print(
            f"Input Tokens: {usage['input_tokens']}"
        )

        print(
            f"Output Tokens: {usage['output_tokens']}"
        )

        print(
            f"Total Tokens: {usage['total_tokens']}"
        )

    total = state.get("total_tokens")

    print("\n========== TOTAL USAGE ==========")

    if total is not None:

        print(
            f"Input Tokens: {total['input_tokens']}"
        )

        print(
            f"Output Tokens: {total['output_tokens']}"
        )

        print(
            f"Total Tokens: {total['total_tokens']}"
        )

    else:

        print("No token usage metadata available.")

    print("\n=================================")


# --------------------------------------------------
# 15. EXECUTE GRAPH
# --------------------------------------------------

def run_spec2rtl(file_path: str):

    result = graph.invoke({

        "file_path": file_path,

        "agent_tokens": {},

        "total_tokens": None

    })

    display_token_usage(result)

    return result

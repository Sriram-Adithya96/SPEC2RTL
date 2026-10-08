from src.llm.llm import get_llm 
from src.schemas import DescriptionOutput 
llm = get_llm()

reflection_llm = llm.with_structured_output(
    DescriptionOutput
)
def reflect_description(
    specification: str,
    description: DescriptionOutput,
    issues: list[str]
)->DescriptionOutput:

    prompt = f"""
    You are a reflection system in a SPEC2RTL pipeline.

    Your task is to correct a component description that failed
    verification.

    RELEVANT SPECIFICATION:
    {specification}

    CURRENT DESCRIPTION:
    {description.model_dump_json(indent=2)}

    VERIFICATION ISSUES:
    {issues}

    Rules:
    - The specification is the source of truth.
    - Fix ONLY the listed issues.
    - Preserve everything that is already correct.
    - Do not invent signals, behavior, constraints, or functionality.
    - Do not add unrelated functionality.
    - Do not change the component's responsibility.
    - Return the complete corrected DescriptionOutput.
    """

    result = reflection_llm.invoke(prompt)

    return result
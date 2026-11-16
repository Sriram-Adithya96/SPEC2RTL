
from src.llm.llm import get_llm
from src.schemas import PseudocodeGenerationOutput


def main():
    llm = get_llm()

    structured_llm = llm.with_structured_output(
        PseudocodeGenerationOutput
    )

    prompt = """
    Return a valid structured JSON response for a simple
    32-bit hardware adder component.

    Requirements:
    - Return one item in components.
    - component_name and module_name: SimpleAdder.
    - inputs: ["a[31:0]", "b[31:0]"].
    - outputs: ["result[31:0]"].
    - pseudocode: Declare the module and assign result = a + b in a
      combinational block.
    - Include empty assumptions, unresolved_issues, and validation_issues.
    - Set generation_status to "completed" and validation_status to "Passed".
    - Include overall assumptions and unresolved_issues arrays.

    Follow the supplied output schema exactly.
    """

    print("Testing structured pseudocode output...")

    try:
        result = structured_llm.invoke(prompt)

        print("\nSUCCESS")
        print(result.model_dump_json(indent=2))

    except Exception as error:
        print("\nFAILED")
        print(type(error).__name__, str(error))


if __name__ == "__main__":
    main()

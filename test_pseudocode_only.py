
import json
from pathlib import Path

from src.ingestion import ingest_spec
from src.agents.pseudocode import generate_pseudocode
from src.schemas import (
    DecompositionOutput,
    DescriptionOutput,
    VerificationResult,
    Understanding,
)

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"

SPEC_PATH = Path(
    r"C:\Users\srira\OneDrive\Desktop\ps spec2rtl\fake_spec2rtl_spec (1).docx"
)


# --------------------------------------------------
# LOAD SAVED DATA
# --------------------------------------------------

def load_json(filename):
    path = OUTPUT_DIR / filename

    if not path.is_file():
        raise FileNotFoundError(
            f"Missing required saved JSON file: {filename} ({path}). "
            "Run the original pipeline first to generate this file."
        )

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def load_specification():
    if not SPEC_PATH.exists():
        raise FileNotFoundError(
            f"Specification document not found: {SPEC_PATH}"
        )

    docs, _, _ = ingest_spec(str(SPEC_PATH))

    specification = "\n\n".join(
        doc.page_content for doc in docs
    ).strip()

    if not specification:
        raise ValueError("The specification text is empty.")

    return specification


# --------------------------------------------------
# RUN ONLY THE PSEUDOCODE AGENT
# --------------------------------------------------

def main():
    print("Loading saved pipeline outputs...")

    specification = load_specification()

    decomposition = DecompositionOutput.model_validate(
        load_json("decomposition.json")
    )

    descriptions = [
        DescriptionOutput.model_validate(item)
        for item in load_json("descriptions.json")
    ]

    verification_results = [
        VerificationResult.model_validate(item)
        for item in load_json("verification.json")
    ]

    understanding = Understanding.model_validate(load_json("understanding.json"))

    print("Saved data loaded successfully.")
    print("Components:", len(decomposition.components))
    print("Descriptions:", len(descriptions))
    print("Verification results:", len(verification_results))

    if len(decomposition.components) != 7 or len(verification_results) != 7:
        print(
            "Expected 7 components and 7 verification results; found "
            f"{len(decomposition.components)} components and "
            f"{len(verification_results)} verification results. "
            "Stopping before pseudocode generation."
        )
        return

    invalid_components = [
        component.name
        for component, verification in zip(
            decomposition.components,
            verification_results,
        )
        if not verification.valid
    ]
    if invalid_components:
        print("Description verification failed for:")
        for component_name in invalid_components:
            print(f"- {component_name}")
        print("Stopping before pseudocode generation.")
        return

    print("\nRunning Pseudocode Generation Agent...")

    result = generate_pseudocode(
        specification=specification,
        decomposition=decomposition,
        descriptions=descriptions,
        verification_results=verification_results,
        understanding=understanding,
        raw_output_dir=OUTPUT_DIR,
    )

    output_path = OUTPUT_DIR / "pseudocode.json"

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(
            result.model_dump(),
            file,
            indent=4,
            ensure_ascii=False,
        )

    validation_errors = [
        issue
        for issue in result.validation_issues
        if issue.get("severity") == "error"
    ]
    validation_warnings = [
        issue
        for issue in result.validation_issues
        if issue.get("severity") == "warning"
    ]

    print("\nPseudocode generation summary")
    print("=" * 60)
    print("Components:", len(result.components))
    for component in result.components:
        print(
            f"- {component.component_name} "
            f"(module: {component.module_name})"
        )
    print("Generation status:", result.generation_status)
    print("Validation status:", result.validation_status)
    print("Validation errors:", len(validation_errors))
    print("Validation warnings:", len(validation_warnings))
    print("Execution status:", result.execution_status)

    print("\nValidation issues")
    if result.validation_issues:
        for issue in result.validation_issues:
            print(
                f"- [{issue.get('code', 'UNKNOWN')}] "
                f"{issue.get('message', 'No message provided')}"
            )
    else:
        print("- None")

    print("\nAssumptions")
    if result.assumptions:
        for assumption in result.assumptions:
            print(f"- {assumption}")
    else:
        print("- None")

    print("\nUnresolved issues")
    if result.unresolved_issues:
        for issue in result.unresolved_issues:
            print(f"- {issue}")
    else:
        print("- None")

    print("\nGenerated pseudocode saved.")
    print("Saved to:", output_path)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"\nERROR: {type(error).__name__}: {error}")

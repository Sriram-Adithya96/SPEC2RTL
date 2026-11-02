
import argparse
from pathlib import Path
from typing import Sequence

def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Verify generated component code against a PDF or DOCX specification."
    )
    parser.add_argument(
        "specification",
        nargs="?",
        help="Path to the hardware specification",
    )
    args = parser.parse_args(argv)

    specification_path = args.specification
    if specification_path is None:
        specification_path = input("Enter specification PDF/DOCX path: ").strip()
    specification_path = specification_path.strip().strip('"')
    if not specification_path:
        parser.error("a specification file path is required")
    if Path(specification_path).suffix.lower() not in {".pdf", ".docx"}:
        parser.error("specification must be a PDF or DOCX file")

    from src.agents.verification import verify_code
    from src.ingestion import ingest_spec
    from src.schemas import CodeOuput

    documents, _ = ingest_spec(specification_path)

    generated_code = CodeOuput(
        component_name="ALU",
        code="""
def alu_top(Operation, SrcA, SrcB):
    if Operation == 0:
        return SrcA + SrcB
    elif Operation == 1:
        return SrcA - SrcB
    elif Operation == 2:
        return SrcA & SrcB
    else:
        return 0
""",
        assumptions=[],
    )

    result = verify_code(documents, generated_code)

    print("\nVERIFICATION RESULT")
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()

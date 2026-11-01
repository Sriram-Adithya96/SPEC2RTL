from src.agents.reflection import reflect_on_verification
from src.schemas import VerificationResult, DescriptionOutput
from langchain_core.documents import Document


# TEST 1: When verification passes
def test_verification_passed():

    verification = VerificationResult(
        valid=True,
        issues=[],
        suggestions=[],
        reasoning="The description satisfies the specification."
    )

    result = reflect_on_verification(
        source_chunks=[],
        description=None,
        verification=verification
    )

    assert result.needs_revision == False
    assert result.feedback == []

    print("Reflection test passed!")


# TEST 2: When verification fails
def test_verification_failed():

    verification = VerificationResult(
        valid=False,
        issues=["The ALU description is missing addition."],
        suggestions=["Check the addition operation."],
        reasoning="The specification requires addition."
    )

    description = DescriptionOutput(
        module_name="ALU",
        purpose="Performs logical operations",
        inputs=[],
        outputs=[],
        internal_signals=[],
        behavior=["Performs AND operation"]
    )

    source_chunks = [
        Document(
            page_content="The ALU must perform addition and AND operations."
        )
    ]

    result = reflect_on_verification(
        source_chunks=source_chunks,
        description=description,
        verification=verification
    )

    print("Needs revision:", result.needs_revision)
    print("Feedback:", result.feedback)
    print("Reasoning:", result.reasoning)

    assert result.needs_revision == True
    assert len(result.feedback) > 0

    print("Failed verification test passed!")


if __name__ == "__main__":
    test_verification_passed()
    test_verification_failed()
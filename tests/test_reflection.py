
from unittest.mock import patch, MagicMock

from langchain_core.documents import Document

from src.agents.reflection import reflect_on_verification
from src.schemas import CodeOuput, VerificationResult, ReflectionOutput


# TEST 1: When verification passes
def test_verification_passed():

    verification = VerificationResult(
        valid=True,
        issues=[],
        suggestions=[],
        reasoning="Code is correct."
    )

    generated_code = CodeOuput(
        component_name="ALU",
        code="def alu(a, b): return a + b",
        assumptions=[]
    )

    result = reflect_on_verification(
        source_chunks=[],
        generated_code=generated_code,
        verification=verification
    )

    assert result.needs_revision == False
    assert result.feedback == []


# TEST 2: When verification fails
def test_verification_failed():

    verification = VerificationResult(
        valid=False,
        issues=["Addition operation is missing"],
        suggestions=["Add addition"],
        reasoning="The specification requires addition."
    )

    generated_code = CodeOuput(
        component_name="ALU",
        code="def alu(a, b): return a & b",
        assumptions=[]
    )

    expected_reflection = ReflectionOutput(
        needs_revision=True,
        feedback=["Implement the missing addition operation."],
        reasoning="Addition is required by the specification."
    )

    mock_agent = MagicMock()
    mock_agent.invoke.return_value = {
        "structured_response": expected_reflection
    }

    source_chunks = [
        Document(
            page_content="The ALU must perform addition and AND operations."
        )
    ]

    with patch(
        "src.agents.reflection.create_reflection_agent",
        return_value=mock_agent
    ):

        result = reflect_on_verification(
            source_chunks=source_chunks,
            generated_code=generated_code,
            verification=verification
        )

    assert result.needs_revision == True
    assert len(result.feedback) > 0
    mock_agent.invoke.assert_called_once()
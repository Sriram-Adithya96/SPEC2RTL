from unittest.mock import patch, MagicMock

from src.schemas import VerificationResult, ReflectionOutput
from src.agents.workflow import run_reflection_workflow


def test_workflow():

    failed = VerificationResult(
        valid=False,
        issues=["Addition operation is missing"],
        suggestions=["Add addition"],
        reasoning="Addition is required."
    )

    passed = VerificationResult(
        valid=True,
        issues=[],
        suggestions=[],
        reasoning="Code is correct."
    )

    reflection = ReflectionOutput(
        needs_revision=True,
        feedback=["Add the missing addition operation."],
        reasoning="Addition is required."
    )

    description = MagicMock()
    first_code = MagicMock()
    revised_code = MagicMock()

    with patch("src.agents.workflow.describe_component") as describe, \
         patch("src.agents.workflow.generate_code") as generate, \
         patch("src.agents.workflow.verify_code") as verify, \
         patch("src.agents.workflow.reflect_on_verification") as reflect:

        describe.return_value = description
        generate.side_effect = [first_code, revised_code]
        verify.side_effect = [failed, passed]
        reflect.return_value = reflection

        result = run_reflection_workflow(None, [])

        assert result["success"] == True
        assert result["code"] == revised_code
        assert verify.call_count == 2
        assert reflect.call_count == 1
        assert generate.call_count == 2
        assert describe.call_count == 1


def test_max_retries():

    failed = VerificationResult(
        valid=False,
        issues=["Code is still incorrect"],
        suggestions=["Correct the code"],
        reasoning="Verification failed."
    )

    reflection = ReflectionOutput(
        needs_revision=True,
        feedback=["Fix the missing requirements."],
        reasoning="Corrections are required."
    )

    description = MagicMock()
    generated_codes = [MagicMock() for _ in range(4)]

    with patch("src.agents.workflow.describe_component") as describe, \
         patch("src.agents.workflow.generate_code") as generate, \
         patch("src.agents.workflow.verify_code") as verify, \
         patch("src.agents.workflow.reflect_on_verification") as reflect:

        describe.return_value = description
        generate.side_effect = generated_codes
        verify.return_value = failed
        reflect.return_value = reflection

        result = run_reflection_workflow(None, [])

        assert result["success"] == False
        assert verify.call_count == 4
        assert reflect.call_count == 3
        assert generate.call_count == 4
        assert describe.call_count == 1

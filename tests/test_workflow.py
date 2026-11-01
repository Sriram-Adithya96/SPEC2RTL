from unittest.mock import patch
from src.schemas import VerificationResult, ReflectionOutput
from src.agents.workflow import run_reflection_workflow


# TEST 1: Verification fails once, then passes
def test_workflow():

    failed = VerificationResult(
        valid=False,
        issues=["Addition operation is missing"],
        suggestions=["Check addition operation"],
        reasoning="The specification requires addition."
    )

    passed = VerificationResult(
        valid=True,
        issues=[],
        suggestions=[],
        reasoning="Description satisfies the specification."
    )

    reflection = ReflectionOutput(
        needs_revision=True,
        feedback=["Add the missing addition operation."],
        reasoning="Addition is required."
    )

    with patch("src.agents.workflow.describe_component") as describe, \
         patch("src.agents.workflow.verify_description") as verify, \
         patch("src.agents.workflow.reflect_on_verification") as reflect:

        describe.side_effect = ["First description", "Corrected description"]
        verify.side_effect = [failed, passed]
        reflect.return_value = reflection

        result = run_reflection_workflow(
            component=None,
            source_chunks=[]
        )

        assert result["success"] == True
        assert result["description"] == "Corrected description"
        assert verify.call_count == 2
        assert reflect.call_count == 1

        print("Workflow test passed!")


# TEST 2: Verification keeps failing
def test_max_retries():

    failed = VerificationResult(
        valid=False,
        issues=["Description is still incorrect"],
        suggestions=["Correct the description"],
        reasoning="Verification failed."
    )

    reflection = ReflectionOutput(
        needs_revision=True,
        feedback=["Fix the missing requirements."],
        reasoning="Corrections are required."
    )

    with patch("src.agents.workflow.describe_component") as describe, \
         patch("src.agents.workflow.verify_description") as verify, \
         patch("src.agents.workflow.reflect_on_verification") as reflect:

        describe.return_value = "Description"
        verify.return_value = failed
        reflect.return_value = reflection

        result = run_reflection_workflow(
            component=None,
            source_chunks=[]
        )

        assert result["success"] == False
        assert verify.call_count == 4
        assert reflect.call_count == 3
        assert describe.call_count == 4

        print("Maximum retry test passed!")


if __name__ == "__main__":
    test_workflow()
    test_max_retries()
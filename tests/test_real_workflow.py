
from langchain_core.documents import Document

from src.schemas import Component
from src.agents.workflow import run_reflection_workflow


component = Component(
    name="ALU",
    purpose="Performs arithmetic and logical operations",
    inputs=["A", "B", "opcode"],
    outputs=["result"]
)

source_chunks = [
    Document(
        page_content="""
        The ALU performs addition and AND operations.
        It takes inputs A, B, and opcode.
        It produces an output called result.
        """
    )
]


def test_real_workflow():

    result = run_reflection_workflow(
        component,
        source_chunks
    )

    print("\nFinal Result:")
    print("Success:", result["success"])
    print("Description:", result["description"])
    print("Code:", result["code"])
    print("Verification:", result["verification"])

    assert result["success"] == True
    assert result["description"] is not None
    assert result["code"] is not None
    assert result["verification"].valid == True
import unittest
from unittest.mock import patch
from langchain_core.documents import Document
from src.agents.verification import (
    SYSTEM_PROMPT,
    _extract_verification_json,
    check_interface_consistency,
    verify_description,
)
from src.schemas import (
    Component,
    DescriptionOutput,
    Signal,
    StateElement,
    VerificationResult,
)


class VerificationAgentTests(unittest.TestCase):

    def create_description(self):
        """Create a sample description using the actual Pydantic schemas."""
        return DescriptionOutput(
            module_name="Counter",
            purpose="Counts clock cycles.",
            inputs=[
                Signal(
                    name="clk",
                    direction="input",
                    width="1",
                    description="Clock input",
                ),
                Signal(
                    name="rst_n",
                    direction="input",
                    width="1",
                    description="Active-low reset input",
                ),
            ],
            outputs=[
                Signal(
                    name="count",
                    direction="output",
                    width="8",
                    description="8-bit counter output",
                ),
            ],
            state_elements=[
                StateElement(
                    name="count",
                    type="register",
                    width="8",
                    reset_value="0",
                    description="Stores the current counter value.",
                ),
            ],
            constraints=[
                "The clock frequency is 50 MHz.",
            ],
            behavior=[
                "Increment count on each rising clock edge when enable is high.",
                "Clear count when the active-low synchronous reset is asserted.",
                "Wrap from 255 to 0.",
            ],
            spec_references=[
                "The specification defines an 8-bit up-counter.",
                "The specification defines clk, rst_n, and enable inputs.",
            ],
        )

    def test_verification_function_exists(self):
        """Confirm that the verification function is available."""
        self.assertTrue(callable(verify_description))

    def test_verification_prompt_is_static_review_only(self):
        """Check that the prompt describes the verification limitations."""
        self.assertIn(
            "static textual review only",
            SYSTEM_PROMPT.lower(),
        )

    def test_exact_interface_matching_passes(self):
        """Confirm that exact interface matches are accepted."""
        comp = Component(
            name="ALU",
            purpose="Performs arithmetic operations",
            inputs=["operand_a[31:0]", "operand_b[31:0]", "opcode[3:0]"],
            outputs=["result[31:0]", "error"],
        )
        desc = DescriptionOutput(
            module_name="ALU",
            purpose="Performs arithmetic operations",
            inputs=[
                Signal(name="operand_a", direction="input", width="32", description="op a"),
                Signal(name="operand_b", direction="input", width="32", description="op b"),
                Signal(name="opcode", direction="input", width="4", description="opcode"),
            ],
            outputs=[
                Signal(name="result", direction="output", width="32", description="result"),
                Signal(name="error", direction="output", width="1", description="error"),
            ],
            state_elements=[],
            constraints=[],
            behavior=["Executes operations combinationally."],
            spec_references=[],
        )
        is_valid, issues = check_interface_consistency(comp, desc)
        self.assertTrue(is_valid)
        self.assertEqual(issues, [])

    def test_description_with_extra_ports_is_rejected(self):
        """Confirm that descriptions with extra ports (e.g. ALU with top-level ports) are rejected."""
        comp = Component(
            name="ALU",
            purpose="Performs arithmetic operations",
            inputs=["operand_a[31:0]", "operand_b[31:0]", "opcode[3:0]"],
            outputs=["result[31:0]", "error"],
        )
        desc = DescriptionOutput(
            module_name="ALU",
            purpose="Performs arithmetic operations",
            inputs=[
                Signal(name="operand_a", direction="input", width="32", description="op a"),
                Signal(name="operand_b", direction="input", width="32", description="op b"),
                Signal(name="opcode", direction="input", width="4", description="opcode"),
                Signal(name="clk", direction="input", width="1", description="extra clk"),
                Signal(name="rst_n", direction="input", width="1", description="extra rst_n"),
            ],
            outputs=[
                Signal(name="result", direction="output", width="32", description="result"),
                Signal(name="error", direction="output", width="1", description="error"),
                Signal(name="valid", direction="output", width="1", description="extra valid"),
                Signal(name="busy", direction="output", width="1", description="extra busy"),
            ],
            state_elements=[],
            constraints=[],
            behavior=["Executes operations."],
            spec_references=[],
        )
        is_valid, issues = check_interface_consistency(comp, desc)
        self.assertFalse(is_valid)
        self.assertTrue(any("Extra input" in iss for iss in issues))
        self.assertTrue(any("Extra output" in iss for iss in issues))

    def test_description_with_missing_ports_is_rejected(self):
        """Confirm that descriptions missing defined ports are rejected."""
        comp = Component(
            name="ALU",
            purpose="Performs arithmetic operations",
            inputs=["operand_a[31:0]", "operand_b[31:0]", "opcode[3:0]"],
            outputs=["result[31:0]", "error"],
        )
        desc = DescriptionOutput(
            module_name="ALU",
            purpose="Performs arithmetic operations",
            inputs=[
                Signal(name="operand_a", direction="input", width="32", description="op a"),
                # Missing operand_b and opcode
            ],
            outputs=[
                Signal(name="result", direction="output", width="32", description="result"),
                # Missing error
            ],
            state_elements=[],
            constraints=[],
            behavior=["Executes operations."],
            spec_references=[],
        )
        is_valid, issues = check_interface_consistency(comp, desc)
        self.assertFalse(is_valid)
        self.assertTrue(any("Missing input" in iss for iss in issues))
        self.assertTrue(any("Missing output" in iss for iss in issues))

    def test_verification_string_response_is_parsed(self):
        parsed = _extract_verification_json(
            '{"valid":true,"issues":[],"suggestions":[],"reasoning":"ok"}'
        )
        self.assertTrue(parsed["valid"])
        self.assertEqual(parsed["issues"], [])

    def test_verification_content_block_response_is_parsed(self):
        parsed = _extract_verification_json([
            {
                "type": "text",
                "text": '{"valid":true,"issues":[],"suggestions":[],"reasoning":"ok"}',
                "annotations": [],
            }
        ])
        self.assertTrue(parsed["valid"])

    def test_verification_empty_response_is_rejected(self):
        for content in ("", "   \n\t"):
            with self.subTest(content=repr(content)):
                with self.assertRaisesRegex(
                    ValueError,
                    "returned empty response content",
                ):
                    _extract_verification_json(content)

        with self.assertRaisesRegex(
            ValueError,
            "returned empty response content",
        ):
            _extract_verification_json([
                {"type": "text", "text": "   "}
            ])

    def test_verification_malformed_json_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "returned invalid JSON"):
            _extract_verification_json('{"valid": true, "issues": [}')

    @patch("src.agents.verification.get_llm")
    @patch("src.agents.verification.create_agent")
    @patch("src.agents.verification.is_free_openrouter_model", return_value=False)
    def test_verify_description_returns_structured_result(
        self,
        mock_is_free,
        mock_create_agent,
        mock_get_llm,
    ):
        """Test verification using a mocked agent, without an API call."""
        expected = VerificationResult(
            valid=True,
            issues=[],
            suggestions=["Generate pseudocode after verification."],
            reasoning="The component description matches the provided evidence.",
        )

        mock_agent = mock_create_agent.return_value
        mock_agent.invoke.return_value = {
            "structured_response": expected,
        }

        description = self.create_description()
        source_chunks = [
            Document(page_content="The counter increments on each rising clock edge."),
            Document(page_content="The counter output is 8 bits wide."),
            Document(page_content="The reset is active-low and synchronous."),
            Document(page_content="The clock frequency is 50 MHz."),
        ]

        result = verify_description(source_chunks, description)
        self.assertIsInstance(result, VerificationResult)
        self.assertTrue(result.valid)
        mock_create_agent.assert_called_once()
        mock_agent.invoke.assert_called_once()

    @patch("src.agents.verification.get_llm")
    @patch("src.agents.verification.create_verification_agent")
    @patch("src.agents.verification.is_free_openrouter_model", return_value=False)
    def test_verify_description_agent_exception_has_no_fallback_call(
        self,
        mock_is_free,
        mock_create_verification_agent,
        mock_get_llm,
    ):
        mock_agent = mock_create_verification_agent.return_value
        mock_agent.invoke.side_effect = RuntimeError("agent invocation failed")

        description = self.create_description()
        source_chunks = [
            Document(page_content="The counter increments on a rising clock edge."),
        ]

        with self.assertRaisesRegex(RuntimeError, "agent invocation failed"):
            verify_description(source_chunks, description)

        mock_get_llm.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)

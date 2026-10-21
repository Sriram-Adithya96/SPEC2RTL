import unittest
from unittest.mock import patch

from src.agents.verification import (
    SYSTEM_PROMPT,
    create_verification_agent,
    verify_rtl,
)
from src.schemas import VerificationResult


class VerificationAgentTests(unittest.TestCase):
    @patch("src.agents.verification.get_llm")
    @patch("src.agents.verification.create_agent")
    def test_agent_uses_typed_response_without_tools(
        self, mock_create_agent, mock_get_llm
    ):
        create_verification_agent()

        mock_get_llm.assert_called_once_with()
        options = mock_create_agent.call_args.kwargs
        self.assertEqual(options["tools"], [])
        self.assertIs(options["response_format"], VerificationResult)
        self.assertIn("static review only", SYSTEM_PROMPT)
        self.assertIn("simulator", SYSTEM_PROMPT)

    @patch("src.agents.verification.create_verification_agent")
    def test_verify_rtl_returns_structured_review(self, mock_create_agent):
        expected = VerificationResult(
            valid=True,
            issues=[],
            suggestions=["Compile and simulate the RTL."],
            reasoning="Static review only; no simulator was run.",
        )
        mock_agent = mock_create_agent.return_value
        mock_agent.invoke.return_value = {"structured_response": expected}

        result = verify_rtl("An 8-bit counter.", "module counter; endmodule")

        self.assertIs(result, expected)
        prompt = mock_agent.invoke.call_args.args[0]["messages"][0]["content"]
        self.assertIn("An 8-bit counter.", prompt)
        self.assertIn("module counter; endmodule", prompt)

    def test_verify_rtl_rejects_empty_inputs(self):
        with self.assertRaisesRegex(ValueError, "specification"):
            verify_rtl("  ", "module counter; endmodule")
        with self.assertRaisesRegex(ValueError, "rtl_code"):
            verify_rtl("An 8-bit counter.", " ")


if __name__ == "__main__":
    unittest.main()

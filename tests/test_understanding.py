import os
import unittest
from unittest.mock import patch

from src.agents.understanding import (
    SYSTEM_PROMPT,
    create_understanding_agent,
    understand_specification,
)
from src.schemas import Understanding


RUN_LLM_TESTS = (
    os.getenv("SPEC2RTL_RUN_LLM_TESTS") == "1"
    and bool(os.getenv("SPEC2RTL_OPENROUTER_KEY"))
)


class UnderstandingAgentConfigurationTests(unittest.TestCase):
    @patch("src.agents.understanding.get_llm")
    @patch("src.agents.understanding.create_agent")
    def test_agent_uses_typed_response_without_tools(self, mock_create_agent, mock_get_llm):
        create_understanding_agent()

        mock_get_llm.assert_called_once_with()
        mock_create_agent.assert_called_once()
        options = mock_create_agent.call_args.kwargs
        self.assertEqual(options["tools"], [])
        self.assertIs(options["response_format"], Understanding)
        self.assertIn("Do not generate RTL", SYSTEM_PROMPT)
        self.assertIn("Do not silently resolve ambiguity", SYSTEM_PROMPT)
        self.assertIn("NOT SPECIFIED:", SYSTEM_PROMPT)


@unittest.skipUnless(
    RUN_LLM_TESTS,
    "Set SPEC2RTL_RUN_LLM_TESTS=1 and SPEC2RTL_OPENROUTER_KEY to run model integration tests",
)
class UnderstandingAgentTests(unittest.TestCase):
    def test_complete_counter_specification(self):
        result = understand_specification(
            """Implement an 8-bit up-counter. Inputs are clk, active-low synchronous
            reset rst_n, and enable en. Output count[7:0] increments by one on each
            rising edge when en is high, wraps from 255 to 0, and clears to 0 when
            rst_n is low. The clock frequency is 50 MHz."""
        )

        self.assertIsInstance(result, Understanding)
        self.assertTrue(result.system_purpose)
        self.assertTrue(result.functional_requirements)
        self.assertTrue(result.constraints)
        self.assertEqual(result.ambiguities, [])

    def test_missing_information_is_explicit(self):
        result = understand_specification(
            "A counter increments on each active clock edge and has a reset."
        )

        self.assertIsInstance(result, Understanding)
        all_details = [
            result.system_purpose,
            *result.major_components,
            *result.inputs,
            *result.outputs,
            *result.functional_requirements,
            *result.constraints,
            *result.ambiguities,
        ]
        self.assertTrue(
            any("NOT SPECIFIED:" in detail for detail in all_details),
            "Missing details must use the required NOT SPECIFIED format",
        )
        self.assertTrue(result.ambiguities)
        self.assertFalse(
            any("8-bit" in detail or "16-bit" in detail for detail in all_details),
            "The agent must not invent a counter width",
        )

    def test_exact_signal_names_and_widths_are_preserved(self):
        result = understand_specification(
            "A sampling block accepts data_in[11:0] on clk at 50 MHz and emits "
            "data_out[11:0] and valid. Data transfers use SPI mode 0 at 1 MHz."
        )

        self.assertIsInstance(result, Understanding)
        extracted = " ".join(
            [*result.major_components, *result.inputs, *result.outputs, *result.constraints]
        )
        for exact_detail in (
            "data_in[11:0]",
            "data_out[11:0]",
            "clk",
            "valid",
            "50 MHz",
            "SPI mode 0",
            "1 MHz",
        ):
            with self.subTest(detail=exact_detail):
                self.assertIn(exact_detail, extracted)

    def test_ambiguous_specification_is_flagged(self):
        result = understand_specification(
            "The counter output is 8 bits wide and must represent values from 0 to 1023."
        )

        self.assertIsInstance(result, Understanding)
        self.assertTrue(result.ambiguities)


if __name__ == "__main__":
    unittest.main()
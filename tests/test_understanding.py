
import os
import unittest
import json
from unittest.mock import patch

from langchain_core.documents import Document

from src.agents.understanding import (
    SYSTEM_PROMPT,
    create_understanding_agent,
    understand_specification,
    _extract_understanding_json,
    _normalize_understanding_response_content,
)

from src.schemas import Understanding


# Enable integration tests only when explicitly requested
# and an OpenRouter API key is configured.
RUN_LLM_TESTS = (
    os.getenv("SPEC2RTL_RUN_LLM_TESTS") == "1"
    and bool(os.getenv("SPEC2RTL_OPENROUTER_KEY"))
)


class UnderstandingAgentConfigurationTests(unittest.TestCase):

    @patch("src.agents.understanding.get_llm")
    @patch("src.agents.understanding.create_agent")
    def test_agent_uses_typed_response_without_tools(
        self, mock_create_agent, mock_get_llm
    ):
        """Test agent configuration without calling the real LLM."""

        create_understanding_agent()

        mock_get_llm.assert_called_once_with("understanding")
        mock_create_agent.assert_called_once()

        options = mock_create_agent.call_args.kwargs

        self.assertEqual(options["tools"], [])

        if os.getenv(
            "SPEC2RTL_OPENROUTER_UNDERSTANDING_MODEL", ""
        ).endswith(":free"):
            self.assertIsNone(options["response_format"])
        else:
            self.assertIs(
                options["response_format"],
                Understanding
            )

        self.assertIn("Do not generate RTL", SYSTEM_PROMPT)
        self.assertIn(
            "Do not resolve ambiguities or contradictions",
            SYSTEM_PROMPT,
        )
        self.assertIn("NOT SPECIFIED:", SYSTEM_PROMPT)
        normalized_prompt = " ".join(SYSTEM_PROMPT.split())
        self.assertIn(
            "Do not report a reset mode, polarity, or reset effect as "
            "unspecified when the specification states it explicitly.",
            normalized_prompt,
        )


class UnderstandingResponseParsingTests(unittest.TestCase):
    """Test response extraction without making API calls."""

    def test_plain_string_response(self):
        content = '{"system_purpose":"test"}'

        self.assertEqual(
            _extract_understanding_json(content),
            content
        )

    def test_langchain_text_block_response(self):
        content = [
            {
                "type": "text",
                "text": '{"system_purpose":"test","inputs":["clk"]}',
                "annotations": [],
            }
        ]

        self.assertEqual(
            _extract_understanding_json(content),
            '{"system_purpose":"test","inputs":["clk"]}'
        )

    def test_multiple_text_blocks_are_combined(self):
        content = [
            {
                "type": "text",
                "text": '{"system_purpose":"test",'
            },
            {
                "type": "text",
                "text": '"inputs":["clk"]}'
            },
        ]

        self.assertEqual(
            _extract_understanding_json(content),
            '{"system_purpose":"test","inputs":["clk"]}'
        )

    def test_markdown_json_fence_is_removed(self):
        content = '```json\n{"system_purpose":"test"}\n```'

        self.assertEqual(
            _extract_understanding_json(content),
            '{"system_purpose":"test"}'
        )

    def test_empty_response_is_rejected(self):
        contents = [
            "",
            "  ",
            [{"type": "text", "text": "  "}]
        ]

        for content in contents:
            with self.subTest(content=content):
                with self.assertRaisesRegex(
                    ValueError,
                    "empty response content"
                ):
                    _extract_understanding_json(content)

    def test_non_text_response_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "content is not text"
        ):
            _normalize_understanding_response_content(
                {"unexpected": "value"}
            )

    def test_missing_json_object_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "no complete JSON object"
        ):
            _extract_understanding_json(
                "The model did not return JSON."
            )

    def test_malformed_json_is_rejected_by_json_parser(self):
        content = _extract_understanding_json(
            '```json\n{"a": }\n```'
        )

        with self.assertRaises(json.JSONDecodeError):
            json.loads(content)


@unittest.skipUnless(
    RUN_LLM_TESTS,
    (
        "Set SPEC2RTL_RUN_LLM_TESTS=1 and configure "
        "SPEC2RTL_OPENROUTER_KEY to run model integration tests"
    ),
)
class UnderstandingAgentTests(unittest.TestCase):

    def test_complete_counter_specification(self):
        """Test extraction from a detailed counter specification."""

        specification = Document(
            page_content=(
                "Implement an 8-bit up-counter. Inputs are clk, "
                "active-low synchronous reset rst_n, and enable en. "
                "Output count[7:0] increments by one on each rising "
                "edge when en is high, wraps from 255 to 0, and clears "
                "to 0 when rst_n is low. The clock frequency is 50 MHz."
            )
        )

        result = understand_specification([specification])

        self.assertIsInstance(result, Understanding)
        self.assertTrue(result.system_purpose)
        self.assertTrue(result.functional_requirements)
        self.assertTrue(result.constraints)

        self.assertEqual(
            result.ambiguities,
            [],
            "The complete specification should not contain unresolved ambiguities.",
        )

    def test_missing_information_is_explicit(self):
        """Test that missing details are identified without inventing values."""

        specification = Document(
            page_content=(
                "A counter increments on each active clock edge "
                "and has a reset."
            )
        )

        result = understand_specification([specification])

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
            "Missing details must use the required NOT SPECIFIED format.",
        )

        self.assertTrue(
            result.ambiguities,
            "The agent should identify missing or unclear information.",
        )

        self.assertFalse(
            any(
                "8-bit" in detail or "16-bit" in detail
                for detail in all_details
            ),
            "The agent must not invent a counter width.",
        )

    def test_exact_signal_names_and_widths_are_preserved(self):
        """Test preservation of signal names, widths, and constraints."""

        specification = Document(
            page_content=(
                "A sampling block accepts data_in[11:0] on clk at 50 MHz "
                "and emits data_out[11:0] and valid. "
                "Data transfers use SPI mode 0 at 1 MHz."
            )
        )

        result = understand_specification([specification])

        self.assertIsInstance(result, Understanding)

        extracted = " ".join(
            [
                result.system_purpose,
                *result.major_components,
                *result.inputs,
                *result.outputs,
                *result.functional_requirements,
                *result.constraints,
                *result.ambiguities,
            ]
        )

        expected_details = [
            "data_in[11:0]",
            "data_out[11:0]",
            "clk",
            "valid",
            "50 MHz",
            "SPI mode 0",
            "1 MHz",
        ]

        for exact_detail in expected_details:
            with self.subTest(detail=exact_detail):
                self.assertIn(
                    exact_detail,
                    extracted,
                    f"The extracted information should preserve {exact_detail}.",
                )

    def test_ambiguous_specification_is_flagged(self):
        """Test detection of contradictory hardware requirements."""

        specification = Document(
            page_content=(
                "The counter output is 8 bits wide and must represent "
                "values from 0 to 1023."
            )
        )

        result = understand_specification([specification])

        self.assertIsInstance(result, Understanding)

        self.assertTrue(
            result.ambiguities,
            "The agent should flag the conflict between the output width "
            "and the required value range.",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)

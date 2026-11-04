import os
import unittest
from unittest.mock import patch

from src.llm.llm import get_llm, is_free_openrouter_model


FREE_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
MODEL_VARS = [
    "SPEC2RTL_OPENROUTER_MODEL",
    "SPEC2RTL_OPENROUTER_UNDERSTANDING_MODEL",
    "SPEC2RTL_OPENROUTER_DECOMPOSER_MODEL",
    "SPEC2RTL_OPENROUTER_DESCRIPTION_MODEL",
    "SPEC2RTL_OPENROUTER_VERIFICATION_MODEL",
    "SPEC2RTL_OPENROUTER_PSEUDOCODE_MODEL",
]


class TestOpenRouterFreeModelConfiguration(unittest.TestCase):
    def setUp(self):
        self.env_patch = patch.dict(
            os.environ,
            {
                "SPEC2RTL_OPENROUTER_KEY": "test-key",
                "SPEC2RTL_OPENROUTER_MODEL": FREE_MODEL,
            },
            clear=False,
        )
        self.env_patch.start()
        for name in MODEL_VARS[1:]:
            os.environ.pop(name, None)

    def tearDown(self):
        self.env_patch.stop()

    @patch("src.llm.llm.ChatOpenAI")
    def test_free_model_is_accepted(self, chat_openai):
        llm = get_llm("understanding")

        self.assertIs(chat_openai.return_value, llm)
        kwargs = chat_openai.call_args.kwargs
        self.assertEqual(kwargs["model"], FREE_MODEL)
        self.assertNotIn("model_kwargs", kwargs)

    @patch("src.llm.llm.ChatOpenAI")
    def test_paid_model_is_rejected(self, chat_openai):
        os.environ["SPEC2RTL_OPENROUTER_MODEL"] = "anthropic/claude-haiku-5.5"

        with self.assertRaisesRegex(ValueError, "Only OpenRouter free models are allowed"):
            get_llm("understanding")

        chat_openai.assert_not_called()

    @patch("src.llm.llm.ChatOpenAI")
    def test_missing_agent_and_common_model_uses_configured_free_default(self, chat_openai):
        os.environ.pop("SPEC2RTL_OPENROUTER_MODEL", None)

        get_llm("decomposer")

        self.assertEqual(
            chat_openai.call_args.kwargs["model"],
            FREE_MODEL,
        )
        self.assertTrue(is_free_openrouter_model("decomposer"))

    @patch("src.llm.llm.ChatOpenAI")
    def test_automatic_retries_are_disabled(self, chat_openai):
        get_llm()

        self.assertEqual(chat_openai.call_args.kwargs["max_retries"], 0)


if __name__ == "__main__":
    unittest.main()

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


def is_free_openrouter_model(agent_name=None):
    agent_env_names = {
        "understanding": "SPEC2RTL_OPENROUTER_UNDERSTANDING_MODEL",
        "decomposer": "SPEC2RTL_OPENROUTER_DECOMPOSER_MODEL",
        "description": "SPEC2RTL_OPENROUTER_DESCRIPTION_MODEL",
        "verification": "SPEC2RTL_OPENROUTER_VERIFICATION_MODEL",
        "pseudocode": "SPEC2RTL_OPENROUTER_PSEUDOCODE_MODEL",
    }
    model_env_name = agent_env_names.get(agent_name)
    model = os.getenv(model_env_name, "").strip() if model_env_name else ""
    if not model:
        model = os.getenv(
            "SPEC2RTL_OPENROUTER_MODEL",
            "nvidia/nemotron-3-ultra-550b-a55b:free",
        ).strip()
    return model.endswith(":free")


def get_llm(agent_name=None):
    
    api_key = os.getenv("SPEC2RTL_OPENROUTER_KEY")

    if not api_key:
        raise ValueError(
            "SPEC2RTL_OPENROUTER_KEY is missing from your .env file."
        )

    agent_env_names = {
        "understanding": "SPEC2RTL_OPENROUTER_UNDERSTANDING_MODEL",
        "decomposer": "SPEC2RTL_OPENROUTER_DECOMPOSER_MODEL",
        "description": "SPEC2RTL_OPENROUTER_DESCRIPTION_MODEL",
        "verification": "SPEC2RTL_OPENROUTER_VERIFICATION_MODEL",
        "pseudocode": "SPEC2RTL_OPENROUTER_PSEUDOCODE_MODEL",
    }
    model_env_name = agent_env_names.get(agent_name)
    model = (
        os.getenv(model_env_name, "").strip()
        if model_env_name
        else ""
    )
    if not model:
        model = os.getenv(
            "SPEC2RTL_OPENROUTER_MODEL",
            "nvidia/nemotron-3-ultra-550b-a55b:free",
        ).strip()

    if not model:
        raise ValueError(
            "SPEC2RTL_OPENROUTER_MODEL must be a non-empty OpenRouter model id."
        )
    if not model.endswith(":free"):
        raise ValueError(
            "Only OpenRouter free models are allowed. "
            f"Model '{model}' is not a free model because it does not end with ':free'."
        )
    agent_max_tokens_names = {
        "decomposer": "SPEC2RTL_OPENROUTER_DECOMPOSER_MAX_TOKENS",
        "description": "SPEC2RTL_OPENROUTER_DESCRIPTION_MAX_TOKENS",
        "pseudocode": "SPEC2RTL_OPENROUTER_PSEUDOCODE_MAX_TOKENS",
    }
    max_tokens_env_name = agent_max_tokens_names.get(agent_name)
    max_tokens_value = (
        os.getenv(max_tokens_env_name, "").strip()
        if max_tokens_env_name
        else ""
    )
    if not max_tokens_value:
        max_tokens_value = os.getenv(
            "SPEC2RTL_OPENROUTER_MAX_TOKENS",
            "4000",
        ).strip()
    try:
        max_tokens = int(max_tokens_value)
    except ValueError as exc:
        raise ValueError(
            "SPEC2RTL_OPENROUTER_MAX_TOKENS must be a positive integer."
        ) from exc
    if max_tokens <= 0:
        raise ValueError(
            "SPEC2RTL_OPENROUTER_MAX_TOKENS must be a positive integer."
        )
    print("Using model:", model)
    llm_kwargs = {
        "model": model,
        "api_key": api_key,
        "base_url": "https://openrouter.ai/api/v1",
        "temperature": 0,
        "max_tokens": max_tokens,
        "max_retries": 0,
    }
    if model.endswith(":free"):
        if agent_name in {"decomposer", "description"}:
            llm_kwargs["reasoning"] = {"effort": "none"}
    return ChatOpenAI(
        **llm_kwargs,
    )
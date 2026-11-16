import os
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.callbacks import BaseCallbackHandler

load_dotenv()


@dataclass(frozen=True)
class UsageContext:
    tracker: "UsageTracker"
    agent_name: str
    component_name: str | None = None


_usage_context: ContextVar[UsageContext | None] = ContextVar(
    "spec2rtl_usage_context", default=None
)


class UsageTracker:
    """Thread-safe token usage totals for one pipeline run."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._agents: dict[str, dict] = {}

    @staticmethod
    def _empty_totals() -> dict:
        return {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "calls": 0,
            "calls_without_usage": 0,
            "complete": True,
        }

    def record(self, context: UsageContext, usage: dict | None) -> None:
        with self._lock:
            agent = self._agents.setdefault(
                context.agent_name,
                {**self._empty_totals(), "by_component": {}},
            )
            targets = [agent]
            if context.component_name:
                targets.append(agent["by_component"].setdefault(
                    context.component_name, self._empty_totals()
                ))

            valid_usage = usage is not None and all(
                isinstance(usage.get(key), int) and not isinstance(usage.get(key), bool)
                for key in ("prompt_tokens", "completion_tokens", "total_tokens")
            )
            for totals in targets:
                totals["calls"] += 1
                if context.agent_name == "unattributed":
                    totals["complete"] = False
                if not valid_usage:
                    totals["calls_without_usage"] += 1
                    totals["complete"] = False
                    continue
                for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                    totals[key] += usage[key]

    def snapshot(self) -> dict:
        with self._lock:
            snapshot = {
                name: {
                    **{key: value for key, value in totals.items() if key != "by_component"},
                    **(
                        {
                            "by_component": {
                                component: dict(component_totals)
                                for component, component_totals in totals["by_component"].items()
                            }
                        }
                        if totals["by_component"]
                        else {}
                    ),
                }
                for name, totals in self._agents.items()
            }
        if self is not FALLBACK_USAGE_TRACKER:
            fallback = FALLBACK_USAGE_TRACKER.snapshot()
            if "unattributed" in fallback:
                snapshot["unattributed"] = fallback["unattributed"]
        return snapshot


@contextmanager
def usage_scope(
    tracker: UsageTracker,
    agent_name: str,
    component_name: str | None = None,
):
    """Set the agent/component identity for model calls in the current context."""
    token = _usage_context.set(UsageContext(tracker, agent_name, component_name))
    try:
        yield
    finally:
        _usage_context.reset(token)


def _usage_from_result(response) -> dict | None:
    """Read token counts exposed by LangChain from provider response usage."""
    candidates = []
    llm_output = getattr(response, "llm_output", None)
    if isinstance(llm_output, dict):
        candidates.extend((llm_output.get("token_usage"), llm_output.get("usage")))
    for generations in getattr(response, "generations", []) or []:
        for generation in generations or []:
            message = getattr(generation, "message", None)
            if message is None:
                continue
            candidates.append(getattr(message, "usage_metadata", None))
            metadata = getattr(message, "response_metadata", None)
            if isinstance(metadata, dict):
                candidates.extend((metadata.get("token_usage"), metadata.get("usage")))
    aliases = {
        "prompt_tokens": "input_tokens",
        "completion_tokens": "output_tokens",
        "total_tokens": "total_tokens",
    }
    for usage in candidates:
        if not isinstance(usage, dict):
            continue
        normalized = {
            key: usage.get(key, usage.get(alias))
            for key, alias in aliases.items()
        }
        if (
            normalized["total_tokens"] is None
            and isinstance(normalized["prompt_tokens"], int)
            and not isinstance(normalized["prompt_tokens"], bool)
            and isinstance(normalized["completion_tokens"], int)
            and not isinstance(normalized["completion_tokens"], bool)
        ):
            normalized["total_tokens"] = (
                normalized["prompt_tokens"] + normalized["completion_tokens"]
            )
        if any(value is not None for value in normalized.values()):
            return normalized
    return None


class UsageCallbackHandler(BaseCallbackHandler):
    """Collect provider-reported token usage for each LangChain model call."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: dict[object, UsageContext] = {}

    def on_llm_start(self, serialized, prompts, *, run_id, **kwargs) -> None:
        context = _usage_context.get()
        if context is None:
            context = UsageContext(FALLBACK_USAGE_TRACKER, "unattributed")
        with self._lock:
            self._pending[run_id] = context

    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs) -> None:
        context = _usage_context.get()
        if context is None:
            context = UsageContext(FALLBACK_USAGE_TRACKER, "unattributed")
        with self._lock:
            self._pending[run_id] = context

    def on_llm_end(self, response, *, run_id, **kwargs) -> None:
        with self._lock:
            context = self._pending.pop(run_id, None)
        if context is not None:
            context.tracker.record(context, _usage_from_result(response))

    def on_llm_error(self, error, *, run_id, **kwargs) -> None:
        with self._lock:
            context = self._pending.pop(run_id, None)
        if context is not None:
            context.tracker.record(context, None)


FALLBACK_USAGE_TRACKER = UsageTracker()


def is_free_openrouter_model(agent_name=None):
    agent_env_names = {
        "understanding": "SPEC2RTL_OPENROUTER_UNDERSTANDING_MODEL",
        "decomposer": "SPEC2RTL_OPENROUTER_DECOMPOSER_MODEL",
        "description": "SPEC2RTL_OPENROUTER_DESCRIPTION_MODEL",
        "verification": "SPEC2RTL_OPENROUTER_VERIFICATION_MODEL",
        "pseudocode": "SPEC2RTL_OPENROUTER_PSEUDOCODE_MODEL",
        "rtl_generation": "SPEC2RTL_OPENROUTER_RTL_GENERATION_MODEL",
        "reflection": "SPEC2RTL_OPENROUTER_REFLECTION_MODEL",
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
        "rtl_generation": "SPEC2RTL_OPENROUTER_RTL_GENERATION_MODEL",
        "reflection": "SPEC2RTL_OPENROUTER_REFLECTION_MODEL",
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
        "understanding": "SPEC2RTL_OPENROUTER_UNDERSTANDING_MAX_TOKENS",
        "decomposer": "SPEC2RTL_OPENROUTER_DECOMPOSER_MAX_TOKENS",
        "description": "SPEC2RTL_OPENROUTER_DESCRIPTION_MAX_TOKENS",
        "verification": "SPEC2RTL_OPENROUTER_VERIFICATION_MAX_TOKENS",
        "pseudocode": "SPEC2RTL_OPENROUTER_PSEUDOCODE_MAX_TOKENS",
        "rtl_generation": "SPEC2RTL_OPENROUTER_RTL_GENERATION_MAX_TOKENS",
        "reflection": "SPEC2RTL_OPENROUTER_REFLECTION_MAX_TOKENS",
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
    agent_tag = f"[{agent_name.upper()}] " if agent_name else ""
    print(f"{agent_tag}Using model: {model}")

    timeout_str = (
        os.getenv("SPEC2RTL_OPENROUTER_TIMEOUT")
        or os.getenv("SPEC2RTL_LLM_TIMEOUT")
        or "120"
    ).strip()
    try:
        timeout = float(timeout_str)
        if timeout <= 0:
            timeout = 120.0
    except ValueError:
        timeout = 120.0

    retries_str = (
        os.getenv("SPEC2RTL_OPENROUTER_MAX_RETRIES")
        or os.getenv("SPEC2RTL_LLM_MAX_RETRIES")
        or "2"
    ).strip()
    try:
        max_retries = int(retries_str)
        if max_retries < 0 or max_retries > 2:
            max_retries = 2
    except ValueError:
        max_retries = 2

    llm_kwargs = {
        "model": model,
        "api_key": api_key,
        "base_url": "https://openrouter.ai/api/v1",
        "temperature": 0,
        "max_tokens": max_tokens,
        "request_timeout": timeout,
        "max_retries": max_retries,
        "callbacks": [UsageCallbackHandler()],
    }
    if model.endswith(":free"):
        llm_kwargs["reasoning"] = {"effort": "none"}
    return ChatOpenAI(
        **llm_kwargs,
    )

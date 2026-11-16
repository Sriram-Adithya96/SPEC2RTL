from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from src.llm.llm import (
    UsageCallbackHandler,
    UsageTracker,
    _usage_from_result,
    bind_usage_tracker,
    get_llm,
    reset_usage_context,
    usage_scope,
)


def _start_call(callback, context):
    run_id = uuid4()
    with context:
        callback.on_chat_model_start({}, [], run_id=run_id)
    return run_id


def test_callback_accumulates_provider_reported_usage():
    tracker = UsageTracker()
    callback = UsageCallbackHandler()
    run_id = _start_call(
        callback,
        usage_scope(tracker, "description", component_name="ALU"),
    )

    callback.on_llm_end(
        SimpleNamespace(
            llm_output={
                "token_usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 8,
                    "total_tokens": 20,
                }
            },
            generations=[],
        ),
        run_id=run_id,
    )

    snapshot = tracker.snapshot()
    assert snapshot["description"]["total_tokens"] == 20
    assert snapshot["description"]["calls"] == 1
    assert snapshot["description"]["complete"] is True
    assert snapshot["description"]["by_component"]["ALU"]["prompt_tokens"] == 12


def test_get_llm_attaches_the_usage_callback():
    env = {
        "SPEC2RTL_OPENROUTER_KEY": "test-key",
        "SPEC2RTL_OPENROUTER_MODEL": "sample/model:free",
    }
    with patch.dict("os.environ", env, clear=True), patch(
        "src.llm.llm.ChatOpenAI"
    ) as mock_chat_openai:
        get_llm("understanding")

    callback = mock_chat_openai.call_args.kwargs["callbacks"][0]
    assert isinstance(callback, UsageCallbackHandler)


def test_call_without_usage_scope_is_reported_as_unattributed():
    tracker = UsageTracker()
    callback = UsageCallbackHandler()
    before = tracker.snapshot().get("unattributed", {}).copy()
    run_id = uuid4()

    token = bind_usage_tracker(tracker)
    try:
        callback.on_chat_model_start({}, [], run_id=run_id)
        callback.on_llm_end(
            SimpleNamespace(
                llm_output={
                    "token_usage": {
                        "prompt_tokens": 5,
                        "completion_tokens": 3,
                        "total_tokens": 8,
                    }
                },
                generations=[],
            ),
            run_id=run_id,
        )
    finally:
        reset_usage_context(token)

    unattributed = tracker.snapshot()["unattributed"]
    assert unattributed["calls"] == before.get("calls", 0) + 1
    assert unattributed["total_tokens"] == before.get("total_tokens", 0) + 8
    assert unattributed["complete"] is False


def test_call_outside_any_run_is_local_to_its_callback():
    callback = UsageCallbackHandler()
    run_id = uuid4()

    callback.on_chat_model_start({}, [], run_id=run_id)
    callback.on_llm_end(
        SimpleNamespace(
            llm_output=None,
            generations=[],
        ),
        run_id=run_id,
    )

    assert callback.snapshot()["unattributed"]["calls"] == 1


def test_missing_usage_and_failed_call_mark_totals_incomplete():
    tracker = UsageTracker()
    callback = UsageCallbackHandler()
    scope = usage_scope(tracker, "understanding")

    no_usage_id = _start_call(callback, scope)
    callback.on_llm_end(
        SimpleNamespace(llm_output=None, generations=[]),
        run_id=no_usage_id,
    )

    error_id = _start_call(callback, usage_scope(tracker, "understanding"))
    callback.on_llm_error(RuntimeError("provider request failed"), run_id=error_id)

    totals = tracker.snapshot()["understanding"]
    assert totals["calls"] == 2
    assert totals["calls_without_usage"] == 2
    assert totals["complete"] is False
    assert totals["total_tokens"] == 0


def test_retry_calls_add_to_the_same_agent_totals():
    tracker = UsageTracker()
    callback = UsageCallbackHandler()

    failed_id = _start_call(
        callback, usage_scope(tracker, "rtl_generation")
    )
    callback.on_llm_error(RuntimeError("first attempt failed"), run_id=failed_id)

    successful_id = _start_call(
        callback, usage_scope(tracker, "rtl_generation")
    )
    callback.on_llm_end(
        SimpleNamespace(
            llm_output={
                "token_usage": {
                    "prompt_tokens": 4,
                    "completion_tokens": 6,
                    "total_tokens": 10,
                }
            },
            generations=[],
        ),
        run_id=successful_id,
    )

    totals = tracker.snapshot()["rtl_generation"]
    assert totals["calls"] == 2
    assert totals["calls_without_usage"] == 1
    assert totals["total_tokens"] == 10
    assert totals["complete"] is False


def test_missing_total_tokens_is_sum_of_reported_prompt_and_completion():
    response = SimpleNamespace(
        llm_output={
            "token_usage": {
                "prompt_tokens": 14,
                "completion_tokens": 9,
            }
        },
        generations=[],
    )

    assert _usage_from_result(response) == {
        "prompt_tokens": 14,
        "completion_tokens": 9,
        "total_tokens": 23,
    }


def test_snapshot_omits_empty_component_breakdown():
    tracker = UsageTracker()
    callback = UsageCallbackHandler()
    run_id = _start_call(callback, usage_scope(tracker, "understanding"))
    callback.on_llm_end(
        SimpleNamespace(
            llm_output={
                "token_usage": {
                    "prompt_tokens": 2,
                    "completion_tokens": 2,
                    "total_tokens": 4,
                }
            },
            generations=[],
        ),
        run_id=run_id,
    )

    assert "by_component" not in tracker.snapshot()["understanding"]


def test_concurrent_callbacks_keep_agent_contexts_separate():
    tracker = UsageTracker()
    callback = UsageCallbackHandler()

    def record_call(agent_name, tokens):
        run_id = _start_call(callback, usage_scope(tracker, agent_name))
        callback.on_llm_end(
            SimpleNamespace(
                llm_output={
                    "token_usage": {
                        "prompt_tokens": tokens,
                        "completion_tokens": 1,
                        "total_tokens": tokens + 1,
                    }
                },
                generations=[],
            ),
            run_id=run_id,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(record_call, ("understanding", "decomposer"), (3, 7)))

    snapshot = tracker.snapshot()
    assert snapshot["understanding"]["total_tokens"] == 4
    assert snapshot["decomposer"]["total_tokens"] == 8

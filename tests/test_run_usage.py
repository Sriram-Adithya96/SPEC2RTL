import asyncio
import json
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import runs as run_routes
from api.schemas.runs import RunMetadata
from api.services import runner
from src import pipeline
from src.llm.llm import UsageCallbackHandler, UsageContext, UsageTracker


def _usage(prompt, completion):
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": prompt + completion,
    }


def test_build_token_usage_sums_agents_and_preserves_component_shape():
    by_agent = {
        "description": {
            **_usage(10, 4),
            "calls": 2,
            "calls_without_usage": 1,
            "complete": False,
            "by_component": {"ALU": {**_usage(10, 4), "calls": 2,
                                      "calls_without_usage": 1, "complete": False}},
        },
        "rtl_generation": {
            **_usage(6, 3),
            "calls": 1,
            "calls_without_usage": 0,
            "complete": True,
        },
        "unattributed": {
            **_usage(0, 0),
            "calls": 0,
            "calls_without_usage": 0,
            "complete": True,
        },
    }

    result = runner.build_token_usage(by_agent)

    assert result["prompt_tokens"] == 16
    assert result["completion_tokens"] == 7
    assert result["total_tokens"] == 23
    assert result["calls"] == 3
    assert result["calls_without_usage"] == 1
    assert result["complete"] is False
    assert "unattributed" not in result["by_agent"]
    assert "by_component" not in result["by_agent"]["rtl_generation"]


def test_concurrent_pipeline_runs_keep_usage_trackers_isolated(tmp_path, monkeypatch):
    barrier = threading.Barrier(2)
    trackers = {}
    callback_handler = UsageCallbackHandler()

    def blocking_load(spec_path):
        run_name = spec_path.stem
        barrier.wait(timeout=5)
        run_id = uuid4()
        callback_handler.on_chat_model_start({}, [], run_id=run_id)
        callback_handler.on_llm_end(
            SimpleNamespace(
                llm_output={"token_usage": _usage(11 if run_name == "first" else 29, 1)},
                generations=[],
            ),
            run_id=run_id,
        )
        raise RuntimeError("stop after the isolation probe")

    monkeypatch.setattr(pipeline, "_load_specification", blocking_load)

    def execute(name):
        output_dir = tmp_path / name

        def remember(tracker):
            trackers[name] = tracker

        try:
            pipeline.run_pipeline(
                tmp_path / f"{name}.pdf",
                output_dir,
                usage_tracker_callback=remember,
            )
        except RuntimeError as error:
            assert str(error) == "stop after the isolation probe"

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(execute, ("first", "second")))

    first_usage = trackers["first"].snapshot()
    second_usage = trackers["second"].snapshot()
    assert first_usage["unattributed"]["prompt_tokens"] == 11
    assert second_usage["unattributed"]["prompt_tokens"] == 29


def test_runner_persists_partial_and_final_usage(tmp_path, monkeypatch):
    run_root = tmp_path / "runs"
    monkeypatch.setattr(runner, "RUNS_DIR", run_root)
    monkeypatch.setattr(runner, "OUTPUTS", tmp_path / "no-cli-outputs")
    manager = runner.RunManager()
    run_id = "partial-usage"
    metadata = runner.empty_metadata(run_id, "spec.pdf", 10, ".pdf")
    run_dir = run_root / run_id
    run_dir.mkdir(parents=True)
    manager._runs[run_id] = metadata
    manager._write(metadata)
    partial_snapshots = []

    def fake_run_pipeline(
        spec_path, output_dir, *, progress_callback, usage_tracker_callback
    ):
        tracker = UsageTracker()
        usage_tracker_callback(tracker)
        tracker.record(UsageContext(tracker, "description", "ALU"), _usage(10, 3))
        progress_callback({"stage": "description", "status": "completed"})
        partial_snapshots.append(json.loads(manager._metadata_path(run_id).read_text()))
        tracker.record(UsageContext(tracker, "rtl_generation"), _usage(4, 2))
        progress_callback({"stage": "rtl_generation", "status": "completed"})
        return {"overall_status": "completed", "stages": {}}

    monkeypatch.setattr(runner, "run_pipeline", fake_run_pipeline)
    manager._execute(run_id, tmp_path / "spec.pdf", run_dir)

    partial = partial_snapshots[0]["token_usage"]
    final = manager.get_run(run_id)["token_usage"]
    assert partial["total_tokens"] == 13
    assert set(partial["by_agent"]) == {"description"}
    assert final["total_tokens"] == 19
    assert final["calls"] == 2
    assert set(final["by_agent"]) == {"description", "rtl_generation"}
    assert "by_component" not in final["by_agent"]["rtl_generation"]


def test_runner_persists_usage_when_pipeline_fails(tmp_path, monkeypatch):
    run_root = tmp_path / "runs"
    monkeypatch.setattr(runner, "RUNS_DIR", run_root)
    monkeypatch.setattr(runner, "OUTPUTS", tmp_path / "no-cli-outputs")
    manager = runner.RunManager()
    run_id = "failed-usage"
    metadata = runner.empty_metadata(run_id, "spec.pdf", 10, ".pdf")
    run_dir = run_root / run_id
    run_dir.mkdir(parents=True)
    manager._runs[run_id] = metadata
    manager._write(metadata)

    def failing_pipeline(
        spec_path, output_dir, *, progress_callback, usage_tracker_callback
    ):
        tracker = UsageTracker()
        usage_tracker_callback(tracker)
        tracker.record(UsageContext(tracker, "understanding"), _usage(7, 2))
        raise RuntimeError("pipeline failed")

    monkeypatch.setattr(runner, "run_pipeline", failing_pipeline)
    manager._execute(run_id, tmp_path / "spec.pdf", run_dir)

    persisted = json.loads(manager._metadata_path(run_id).read_text())
    assert persisted["status"] == "failed"
    assert persisted["token_usage"]["total_tokens"] == 9


def test_runner_persists_usage_when_pipeline_is_cancelled(tmp_path, monkeypatch):
    run_root = tmp_path / "runs"
    monkeypatch.setattr(runner, "RUNS_DIR", run_root)
    monkeypatch.setattr(runner, "OUTPUTS", tmp_path / "no-cli-outputs")
    manager = runner.RunManager()
    run_id = "cancelled-usage"
    metadata = runner.empty_metadata(run_id, "spec.pdf", 10, ".pdf")
    run_dir = run_root / run_id
    run_dir.mkdir(parents=True)
    manager._runs[run_id] = metadata
    manager._write(metadata)

    def cancelled_pipeline(
        spec_path, output_dir, *, progress_callback, usage_tracker_callback
    ):
        tracker = UsageTracker()
        usage_tracker_callback(tracker)
        tracker.record(UsageContext(tracker, "understanding"), _usage(6, 2))
        raise asyncio.CancelledError("pipeline cancelled")

    monkeypatch.setattr(runner, "run_pipeline", cancelled_pipeline)
    manager._execute(run_id, tmp_path / "spec.pdf", run_dir)

    persisted = json.loads(manager._metadata_path(run_id).read_text())
    assert persisted["token_usage"]["total_tokens"] == 8


def test_old_metadata_without_token_usage_still_loads_and_lists(tmp_path, monkeypatch):
    run_root = tmp_path / "runs"
    monkeypatch.setattr(runner, "RUNS_DIR", run_root)
    monkeypatch.setattr(runner, "OUTPUTS", tmp_path / "no-cli-outputs")
    old_run_dir = run_root / "old-run"
    old_run_dir.mkdir(parents=True)
    old_metadata = runner.empty_metadata("old-run", "old.pdf", 10, ".pdf")
    old_metadata.pop("token_usage", None)
    (old_run_dir / "metadata.json").write_text(
        json.dumps(old_metadata), encoding="utf-8"
    )

    manager = runner.RunManager()
    loaded = manager.get_run("old-run")
    listed = manager.list_runs()[0]
    validated = RunMetadata.model_validate(loaded)

    assert "token_usage" not in loaded
    assert "token_usage" not in listed
    assert validated.token_usage is None


class _HttpManager:
    def __init__(self, metadata):
        self.metadata = metadata
        self.events = queue.Queue()
        self.events.put({"type": "status", "metadata": metadata})

    def list_runs(self):
        return [self.metadata]

    def get_run(self, run_id):
        return self.metadata if run_id == self.metadata["run_id"] else None

    def subscribe(self, run_id):
        return self.events

    def unsubscribe(self, run_id, subscriber):
        pass


def test_actual_http_run_endpoints_return_token_usage(monkeypatch):
    metadata = runner.empty_metadata("http-run", "spec.pdf", 10, ".pdf")
    metadata["status"] = "completed"
    metadata["token_usage"] = runner.build_token_usage({
        "understanding": {
            **_usage(8, 5),
            "calls": 1,
            "calls_without_usage": 0,
            "complete": True,
        }
    })
    fake_manager = _HttpManager(metadata)
    monkeypatch.setattr(run_routes, "manager", fake_manager)
    app = FastAPI()
    app.include_router(run_routes.router, prefix="/api")

    with TestClient(app) as client:
        list_response = client.get("/api/runs")
        detail_response = client.get("/api/runs/http-run")
        events_response = client.get("/api/runs/http-run/events")

    assert list_response.status_code == 200
    assert list_response.json()["runs"][0]["token_usage"]["total_tokens"] == 13
    assert detail_response.status_code == 200
    assert detail_response.json()["token_usage"]["by_agent"]["understanding"][
        "prompt_tokens"
    ] == 8
    assert events_response.status_code == 200
    assert '"token_usage"' in events_response.text

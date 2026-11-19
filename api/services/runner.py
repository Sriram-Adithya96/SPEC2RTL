"""Background pipeline runs and per-execution storage."""

import copy
import json
import queue
import re
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path


AGENT_ORDER = [
    "understanding",
    "decomposer",
    "description",
    "pseudocode",
    "rtl_generation",
    "rtl_verification",
    "reflection",
]


class UsageTracker:
    def snapshot(self) -> dict:
        return {}

ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = ROOT / "outputs"
RUNS_DIR = OUTPUTS / "runs"

AGENT_FILES = {
    "understanding": "understanding.json",
    "decomposer": "decomposition.json",
    "description": "descriptions.json",
    "verification": "rtl_verification.json",
    "pseudocode": "pseudocode.json",
    "rtl_generation": "rtl_generation.json",
    "rtl_verification": "rtl_verification.json",
    "reflection": "reflection.json",
}

DOWNLOADABLE = {
    "input_summary.json",
    "understanding.json",
    "decomposition.json",
    "descriptions.json",
    "verification.json",
    "pseudocode.json",
    "rtl_generation.json",
    "rtl_verification.json",
    "reflection.json",
    "reflection_attempt_1.json",
    "reflection_attempt_2.json",
    "reflection_attempt_3.json",
    "rtl_verification_attempt_1.json",
    "rtl_verification_attempt_2.json",
    "rtl_verification_attempt_3.json",
    "specification.txt",
    "pseudocode_validation.json",
    "integrated_rtl.v",
    "top_level_rtl.v",
    "integrated_rtl.vhd",
    "top_level_rtl.vhd",
    "compilation.log",
    "pipeline_summary.json",
    "run_manifest.json",
    "pseudocode_raw.txt",
    "metadata.json",
}

RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
TOKEN_USAGE_FIELDS = (
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "calls",
    "calls_without_usage",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_token_usage(by_agent: dict[str, dict]) -> dict:
    """Combine per-agent tracker data into the run-level API shape."""
    agents = {
        name: usage
        for name, usage in by_agent.items()
        if usage.get("calls", 0) > 0
    }
    totals = {field: 0 for field in TOKEN_USAGE_FIELDS}
    for usage in agents.values():
        for field in TOKEN_USAGE_FIELDS:
            totals[field] += usage.get(field, 0)
    return {
        **totals,
        "complete": all(usage.get("complete", False) for usage in agents.values()),
        "by_agent": agents,
    }


def empty_metadata(run_id: str, filename: str, file_size: int, file_type: str) -> dict:
    return {
        "run_id": run_id,
        "filename": filename,
        "file_size": file_size,
        "file_type": file_type,
        "started_at": utc_now(),
        "finished_at": None,
        "status": "running",
        "error": None,
        "failed_stage": None,
        "ingestion": "pending",
        "source": "api",
        "agents": {
            name: {
                "status": "pending",
                "started_at": None,
                "finished_at": None,
                "error": None,
                "message": None,
                "components": [],
            }
            for name in AGENT_ORDER
        },
        "summary": None,
    }


def _skip_pending_agents(metadata: dict, after: str | None = None) -> None:
    names = AGENT_ORDER
    start = 0
    if after in names:
        start = names.index(after) + 1
    for name in names[start:]:
        agent = metadata["agents"][name]
        if agent["status"] == "pending":
            agent["status"] = "skipped"


def apply_progress(metadata: dict, event: dict) -> None:
    stage = event.get("stage")
    status = event.get("status")
    now = utc_now()

    if stage == "ingestion":
        metadata["ingestion"] = status or metadata.get("ingestion")
        if status == "failed":
            metadata["error"] = event.get("error")
            metadata["failed_stage"] = "ingestion"
            _skip_pending_agents(metadata)
        return

    if stage not in metadata["agents"]:
        return

    agent = metadata["agents"][stage]
    if event.get("message"):
        agent["message"] = event["message"]
    if event.get("components") is not None:
        agent["components"] = event["components"]
    for field in (
        "component_generation_status",
        "interface_validation_status",
        "integration_status",
        "compilation_status",
    ):
        if event.get(field) is not None:
            agent[field] = event[field]

    if event.get("component") and status != "failed":
        if agent["status"] == "pending":
            agent["status"] = "running"
        if not agent.get("started_at"):
            agent["started_at"] = now
        return

    agent["status"] = status or agent["status"]
    if agent["status"] == "running" and not agent.get("started_at"):
        agent["started_at"] = now
    if agent["status"] in {"completed", "failed", "skipped"}:
        agent["finished_at"] = now
    if stage == "rtl_verification" and "verification" in metadata["agents"]:
        v_agent = metadata["agents"]["verification"]
        v_agent["status"] = agent["status"]
        v_agent["started_at"] = v_agent.get("started_at") or agent.get("started_at")
        v_agent["finished_at"] = agent.get("finished_at")
        if event.get("message"):
            v_agent["message"] = event["message"]
    if agent["status"] == "failed":
        agent["error"] = event.get("error")
        metadata["error"] = event.get("error")
        metadata["failed_stage"] = stage
        _skip_pending_agents(metadata, after=stage)


class RunManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs: dict[str, dict] = {}
        self._subscribers: dict[str, list[queue.Queue]] = {}
        self._spec_paths: dict[str, Path] = {}
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        self._load_existing()
        self._import_cli_snapshot()

    def _metadata_path(self, run_id: str) -> Path:
        return RUNS_DIR / run_id / "metadata.json"

    def _write(self, metadata: dict) -> None:
        path = self._metadata_path(metadata["run_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(metadata, indent=4, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary.replace(path)

    def _remember(self, metadata: dict) -> None:
        self._runs[metadata["run_id"]] = metadata

    def _load_existing(self) -> None:
        if not RUNS_DIR.exists():
            return
        for path in RUNS_DIR.glob("*/metadata.json"):
            try:
                metadata = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if metadata.get("status") == "running":
                metadata["status"] = "failed"
                metadata["finished_at"] = metadata.get("finished_at") or utc_now()
                metadata["error"] = (
                    metadata.get("error")
                    or "Pipeline interrupted because the API server stopped."
                )
                for agent in metadata.get("agents", {}).values():
                    if agent.get("status") == "running":
                        agent["status"] = "failed"
                        agent["error"] = agent.get("error") or metadata["error"]
                    elif agent.get("status") == "pending":
                        agent["status"] = "skipped"
                self._write(metadata)
            if not metadata.get("token_usage"):
                for check_name in ("run_manifest.json", "pipeline_summary.json"):
                    check_file = path.parent / check_name
                    if check_file.is_file():
                        try:
                            cf_data = json.loads(check_file.read_text(encoding="utf-8"))
                            raw_u = cf_data.get("token_usage")
                            if isinstance(raw_u, dict) and raw_u:
                                metadata["token_usage"] = build_token_usage(raw_u)
                                self._write(metadata)
                                break
                        except Exception:
                            pass
            self._remember(metadata)

    def _import_cli_snapshot(self) -> None:
        """Copy the existing CLI artifacts once, without modifying outputs/."""

        run_id = "cli-snapshot"
        if run_id in self._runs or (RUNS_DIR / run_id).exists():
            return
        required = [
            filename
            for agent, filename in AGENT_FILES.items()
            if agent != "rtl_generation"
        ]
        if not all((OUTPUTS / name).is_file() for name in required):
            return

        destination = RUNS_DIR / run_id
        destination.mkdir(parents=True, exist_ok=True)
        optional = [AGENT_FILES["rtl_generation"]]
        for name in required + optional + ["input_summary.json", "pseudocode_raw.txt"]:
            source = OUTPUTS / name
            if source.is_file():
                shutil.copy2(source, destination / name)

        filename = "specification"
        file_size = 0
        summary_path = OUTPUTS / "input_summary.json"
        if summary_path.is_file():
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                raw_name = str(summary.get("input_file") or filename)
                filename = Path(raw_name).name or filename
                candidate = Path(raw_name)
                if candidate.is_file():
                    file_size = candidate.stat().st_size
            except (OSError, json.JSONDecodeError):
                pass
        if not file_size:
            file_size = (OUTPUTS / "understanding.json").stat().st_size

        started = datetime.fromtimestamp(
            (OUTPUTS / "understanding.json").stat().st_mtime,
            timezone.utc,
        ).isoformat()
        metadata = empty_metadata(run_id, filename, file_size, Path(filename).suffix.lower())
        metadata["started_at"] = started
        metadata["finished_at"] = started
        metadata["status"] = "completed"
        metadata["ingestion"] = "completed"
        metadata["source"] = "cli"
        for name in AGENT_ORDER:
            metadata["agents"][name]["status"] = (
                "completed"
                if name != "rtl_generation"
                or (destination / AGENT_FILES[name]).is_file()
                else "skipped"
            )
            metadata["agents"][name]["started_at"] = started
            metadata["agents"][name]["finished_at"] = started
            metadata["agents"][name]["message"] = None
        metadata["summary"] = {
            "input_document": filename,
            "reflection": "skipped",
            "pseudocode": "completed",
        }
        self._write(metadata)
        self._remember(metadata)

    def _enqueue(self, run_id: str, metadata: dict) -> None:
        payload = {"type": "status", "metadata": copy.deepcopy(metadata)}
        for subscriber in self._subscribers.get(run_id, []):
            subscriber.put(payload)

    def _update(self, run_id: str, mutator) -> dict:
        with self._lock:
            metadata = self._runs[run_id]
            mutator(metadata)
            self._enqueue(run_id, metadata)
            snapshot = copy.deepcopy(metadata)
        self._write(snapshot)
        return snapshot

    def create_run(self, filename: str, payload: bytes) -> dict:
        run_id = uuid.uuid4().hex
        suffix = Path(filename).suffix.lower()
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename).name) or f"specification{suffix}"
        run_dir = RUNS_DIR / run_id
        upload_dir = run_dir / "upload"
        upload_dir.mkdir(parents=True, exist_ok=True)
        spec_path = upload_dir / safe_name
        spec_path.write_bytes(payload)

        metadata = empty_metadata(run_id, Path(filename).name, len(payload), suffix)
        with self._lock:
            self._runs[run_id] = metadata
            self._spec_paths[run_id] = spec_path
        self._write(metadata)

        thread = threading.Thread(
            target=self._execute,
            args=(run_id, spec_path, run_dir),
            name=f"spec2rtl-{run_id[:8]}",
            daemon=True,
        )
        thread.start()
        return copy.deepcopy(metadata)

    def _execute(self, run_id: str, spec_path: Path, run_dir: Path) -> None:
        usage_tracker: UsageTracker | None = None

        def persist_usage(metadata: dict) -> None:
            if usage_tracker is not None:
                metadata["token_usage"] = build_token_usage(usage_tracker.snapshot())

        def tracker_ready(tracker: UsageTracker) -> None:
            nonlocal usage_tracker
            usage_tracker = tracker
            self._update(run_id, persist_usage)

        def callback(event: dict) -> None:
            def update_metadata(metadata: dict) -> None:
                apply_progress(metadata, event)
                if (
                    event.get("stage") in metadata["agents"]
                    and event.get("status") in {"completed", "failed", "cancelled"}
                ):
                    persist_usage(metadata)

            self._update(run_id, update_metadata)

        try:
            from src.pipeline import run_pipeline

            summary = run_pipeline(
                spec_path,
                run_dir,
                progress_callback=callback,
                usage_tracker_callback=tracker_ready,
            )
        except BaseException as error:
            message = f"{type(error).__name__}: {error}"
            stage = getattr(error, "pipeline_stage", None)

            def mark_failed(metadata: dict) -> None:
                metadata["status"] = "failed"
                metadata["finished_at"] = utc_now()
                metadata["error"] = metadata.get("error") or message
                if stage and not metadata.get("failed_stage"):
                    metadata["failed_stage"] = stage
                _skip_pending_agents(metadata, after=metadata.get("failed_stage"))
                persist_usage(metadata)

            self._update(run_id, mark_failed)
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise
            return

        def mark_completed(metadata: dict) -> None:
            overall_status = summary.get("overall_status")
            metadata["status"] = (
                "failed" if overall_status == "failed" else "completed"
            )
            metadata["finished_at"] = utc_now()
            metadata["summary"] = summary
            for agent in metadata["agents"].values():
                if agent["status"] == "pending":
                    agent["status"] = "skipped"
                    agent["finished_at"] = metadata["finished_at"]
            persist_usage(metadata)
            if overall_status == "failed" and not metadata.get("error"):
                metadata["error"] = (
                    "One or more pipeline stages failed; inspect the run summary."
                )
                failed_stages = [
                    name
                    for name, status in summary.get("stages", {}).items()
                    if status in {"failed", "blocked"}
                ]
                if failed_stages and not metadata.get("failed_stage"):
                    metadata["failed_stage"] = failed_stages[-1]

        self._update(run_id, mark_completed)

    def list_runs(self) -> list[dict]:
        with self._lock:
            runs = [copy.deepcopy(item) for item in self._runs.values()]
        runs.sort(key=lambda item: item.get("started_at") or "", reverse=True)
        return runs

    def get_run(self, run_id: str) -> dict | None:
        self._validate_id(run_id)
        with self._lock:
            metadata = self._runs.get(run_id)
            return copy.deepcopy(metadata) if metadata else None

    def run_dir(self, run_id: str) -> Path:
        self._validate_id(run_id)
        return RUNS_DIR / run_id

    def subscribe(self, run_id: str) -> queue.Queue:
        self._validate_id(run_id)
        subscriber: queue.Queue = queue.Queue()
        with self._lock:
            metadata = self._runs.get(run_id)
            if metadata is None:
                raise KeyError(run_id)
            self._subscribers.setdefault(run_id, []).append(subscriber)
            subscriber.put({"type": "status", "metadata": copy.deepcopy(metadata)})
        return subscriber

    def unsubscribe(self, run_id: str, subscriber: queue.Queue) -> None:
        with self._lock:
            subscribers = self._subscribers.get(run_id, [])
            if subscriber in subscribers:
                subscribers.remove(subscriber)

    def output_index(self, run_id: str) -> dict:
        directory = self.run_dir(run_id)
        if self.get_run(run_id) is None or not directory.is_dir():
            raise KeyError(run_id)
        files = sorted(
            path.name
            for path in directory.iterdir()
            if path.is_file() and path.name in DOWNLOADABLE
        )
        agents = {
            agent: filename
            for agent, filename in AGENT_FILES.items()
            if (directory / filename).is_file()
        }
        artifacts = [
            name
            for name in (
                "pseudocode_raw.txt",
                "input_summary.json",
                "pseudocode_validation.json",
                "compilation.log",
                "pipeline_summary.json",
                "run_manifest.json",
                "metadata.json",
            )
            if name in files
        ]
        return {"files": files, "agents": agents, "artifacts": artifacts}

    def output_file(self, run_id: str, filename: str) -> Path:
        if filename not in DOWNLOADABLE:
            raise FileNotFoundError(filename)
        path = self.run_dir(run_id) / filename
        if self.get_run(run_id) is None or not path.is_file():
            raise FileNotFoundError(filename)
        return path

    @staticmethod
    def _validate_id(run_id: str) -> None:
        if not RUN_ID_PATTERN.fullmatch(run_id or ""):
            raise KeyError(run_id)


manager = RunManager()

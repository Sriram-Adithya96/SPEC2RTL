"""Background pipeline runs and per-execution storage."""

import copy
import json
import os
import queue
import re
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.pipeline import AGENT_ORDER, run_pipeline
from src.llm.llm import UsageTracker
from api.database import get_artifacts_collection, get_runs_collection

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
    "specification.txt",
    "pseudocode_validation.json",
    "integrated_rtl.v",
    "top_level_rtl.v",
    "compilation.log",
    "pipeline_summary.json",
    "run_manifest.json",
    "pseudocode_raw.txt",
    "metadata.json",
}


def is_downloadable(filename: str) -> bool:
    if filename in DOWNLOADABLE:
        return True
    if (filename.startswith("reflection_attempt_") or filename.startswith("rtl_verification_attempt_")) and filename.endswith(".json"):
        return True
    return False

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


def get_agent_model(agent_name: str | None = None) -> str:
    """Return the configured LLM model string for the specified agent."""
    mode = os.getenv("SPEC2RTL_MODE", "free").strip().lower()
    if mode == "paid":
        return os.getenv("SPEC2RTL_PAID_OPENROUTER_MODEL", "").strip() or "deepseek/deepseek-v4.1-flash-1017"

    agent_env_names = {
        "understanding": "SPEC2RTL_OPENROUTER_UNDERSTANDING_MODEL",
        "decomposer": "SPEC2RTL_OPENROUTER_DECOMPOSER_MODEL",
        "description": "SPEC2RTL_OPENROUTER_DESCRIPTION_MODEL",
        "verification": "SPEC2RTL_OPENROUTER_VERIFICATION_MODEL",
        "pseudocode": "SPEC2RTL_OPENROUTER_PSEUDOCODE_MODEL",
        "rtl_generation": "SPEC2RTL_OPENROUTER_RTL_GENERATION_MODEL",
        "rtl_verification": "SPEC2RTL_OPENROUTER_VERIFICATION_MODEL",
        "reflection": "SPEC2RTL_OPENROUTER_REFLECTION_MODEL",
    }
    model_env_name = agent_env_names.get(agent_name)
    model = os.getenv(model_env_name, "").strip() if model_env_name else ""
    if not model:
        model = os.getenv("SPEC2RTL_OPENROUTER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free").strip()
    return model


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
                "model": get_agent_model(name),
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
        self._cancel_events: dict[str, threading.Event] = {}
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        self._load_existing()
        self._import_cli_snapshot()

    def _metadata_path(self, run_id: str) -> Path:
        return RUNS_DIR / run_id / "metadata.json"

    def _write_local(self, metadata: dict) -> None:
        path = self._metadata_path(metadata["run_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(metadata, indent=4, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary.replace(path)

    def _write_db(self, metadata: dict) -> None:
        try:
            col = get_runs_collection()
            if col is not None:
                doc = copy.deepcopy(metadata)
                doc.pop("_id", None)
                col.replace_one({"run_id": doc["run_id"]}, doc, upsert=True)
        except Exception as exc:
            print(f"[RunManager Warning] Failed to persist run to MongoDB: {exc}")

    def _write(self, metadata: dict) -> None:
        self._write_local(metadata)
        self._write_db(metadata)

    def _remember(self, metadata: dict) -> None:
        self._runs[metadata["run_id"]] = metadata

    def _persist_artifacts_to_db(self, run_id: str, run_dir: Path) -> None:
        try:
            col = get_artifacts_collection()
            if col is None or not run_dir.is_dir():
                return
            for file_path in run_dir.iterdir():
                if file_path.is_file() and is_downloadable(file_path.name):
                    try:
                        content_bytes = file_path.read_bytes()
                        if len(content_bytes) > 10 * 1024 * 1024:
                            continue
                        try:
                            text_val = content_bytes.decode("utf-8")
                            is_binary = False
                        except UnicodeDecodeError:
                            text_val = None
                            is_binary = True
                        doc = {
                            "run_id": run_id,
                            "filename": file_path.name,
                            "is_binary": is_binary,
                            "text": text_val,
                            "bytes": content_bytes if is_binary else None,
                        }
                        col.replace_one(
                            {"run_id": run_id, "filename": file_path.name},
                            doc,
                            upsert=True,
                        )
                    except Exception:
                        pass
        except Exception as exc:
            print(f"[RunManager Warning] Failed to persist artifacts to MongoDB: {exc}")

    def _load_existing(self) -> None:
        if RUNS_DIR.exists():
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
                for agent_name, agent in metadata.get("agents", {}).items():
                    if not agent.get("model"):
                        agent["model"] = get_agent_model(agent_name)
                self._remember(metadata)
                # Sync local run and its artifacts to MongoDB Atlas if connected
                self._write_db(metadata)
                self._persist_artifacts_to_db(metadata["run_id"], path.parent)

        # Also load past runs from MongoDB Atlas (crucial when Render restarts with an empty disk)
        try:
            col = get_runs_collection()
            if col is not None:
                for doc in col.find():
                    doc.pop("_id", None)
                    run_id = doc.get("run_id")
                    if not run_id:
                        continue
                    if doc.get("status") == "running":
                        doc["status"] = "failed"
                        doc["finished_at"] = doc.get("finished_at") or utc_now()
                        doc["error"] = (
                            doc.get("error")
                            or "Pipeline interrupted because the API server stopped."
                        )
                        for agent in doc.get("agents", {}).values():
                            if agent.get("status") == "running":
                                agent["status"] = "failed"
                                agent["error"] = agent.get("error") or doc["error"]
                            elif agent.get("status") == "pending":
                                agent["status"] = "skipped"
                        try:
                            col.replace_one({"run_id": run_id}, doc, upsert=True)
                        except Exception:
                            pass
                    for agent_name, agent in doc.get("agents", {}).items():
                        if not agent.get("model"):
                            agent["model"] = get_agent_model(agent_name)
                    if run_id not in self._runs:
                        self._remember(doc)
                        try:
                            self._write_local(doc)
                        except Exception:
                            pass
        except Exception as exc:
            print(f"[RunManager Warning] Failed to load runs from MongoDB: {exc}")

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

    def create_run(self, filename: str, payload: bytes, user_id: str | None = None) -> dict:
        run_id = uuid.uuid4().hex
        suffix = Path(filename).suffix.lower()
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename).name) or f"specification{suffix}"
        run_dir = RUNS_DIR / run_id
        upload_dir = run_dir / "upload"
        upload_dir.mkdir(parents=True, exist_ok=True)
        spec_path = upload_dir / safe_name
        spec_path.write_bytes(payload)

        cancel_event = threading.Event()
        metadata = empty_metadata(run_id, Path(filename).name, len(payload), suffix)
        if user_id:
            metadata["user_id"] = user_id
        with self._lock:
            self._runs[run_id] = metadata
            self._spec_paths[run_id] = spec_path
            self._cancel_events[run_id] = cancel_event
        self._write(metadata)

        thread = threading.Thread(
            target=self._execute,
            args=(run_id, spec_path, run_dir, cancel_event),
            name=f"spec2rtl-{run_id[:8]}",
            daemon=True,
        )
        thread.start()
        return copy.deepcopy(metadata)

    def _execute(self, run_id: str, spec_path: Path, run_dir: Path, cancel_event: threading.Event) -> None:
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
            summary = run_pipeline(
                spec_path,
                run_dir,
                progress_callback=callback,
                usage_tracker_callback=tracker_ready,
                cancel_event=cancel_event,
            )
        except BaseException as error:
            message = f"{type(error).__name__}: {error}"
            stage = getattr(error, "pipeline_stage", None)
            is_cancelled = cancel_event.is_set() or "cancelled" in message.lower()

            def mark_failed(metadata: dict) -> None:
                metadata["status"] = "cancelled" if is_cancelled else "failed"
                metadata["finished_at"] = utc_now()
                metadata["error"] = "Pipeline cancelled by user." if is_cancelled else (metadata.get("error") or message)
                if stage and not metadata.get("failed_stage"):
                    metadata["failed_stage"] = stage
                _skip_pending_agents(metadata, after=metadata.get("failed_stage"))
                persist_usage(metadata)

            self._update(run_id, mark_failed)
            self._persist_artifacts_to_db(run_id, run_dir)
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
        self._persist_artifacts_to_db(run_id, run_dir)

    def list_runs(self, user_id: str | None = None) -> list[dict]:
        with self._lock:
            runs = [copy.deepcopy(item) for item in self._runs.values()]
        if user_id is not None:
            # Only return runs belonging to this user
            runs = [r for r in runs if r.get("user_id") == user_id]
        runs.sort(key=lambda item: item.get("started_at") or "", reverse=True)
        return runs

    def get_run(self, run_id: str) -> dict | None:
        self._validate_id(run_id)
        with self._lock:
            metadata = self._runs.get(run_id)
            return copy.deepcopy(metadata) if metadata else None

    def cancel_run(self, run_id: str) -> dict:
        self._validate_id(run_id)
        with self._lock:
            metadata = self._runs.get(run_id)
            if metadata is None:
                raise KeyError(run_id)
            if metadata.get("status") != "running":
                return copy.deepcopy(metadata)
            event = self._cancel_events.get(run_id)
            if event:
                event.set()
            metadata["status"] = "cancelled"
            metadata["finished_at"] = utc_now()
            metadata["error"] = "Pipeline cancelled by user."
            for agent in metadata.get("agents", {}).values():
                if agent.get("status") == "running":
                    agent["status"] = "cancelled"
                    agent["finished_at"] = utc_now()
                    agent["message"] = "Cancelled by user"
                elif agent.get("status") == "pending":
                    agent["status"] = "skipped"
            self._enqueue(run_id, metadata)
            snapshot = copy.deepcopy(metadata)
        self._write(snapshot)
        return snapshot

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
        self._validate_id(run_id)
        if self.get_run(run_id) is None:
            raise KeyError(run_id)
        directory = self.run_dir(run_id)
        directory.mkdir(parents=True, exist_ok=True)
        # Restore artifacts from MongoDB if directory is missing files (e.g. after Render restart)
        try:
            col = get_artifacts_collection()
            if col is not None:
                for doc in col.find({"run_id": run_id}):
                    fname = doc.get("filename")
                    if fname:
                        fpath = directory / fname
                        if not fpath.is_file():
                            fpath.parent.mkdir(parents=True, exist_ok=True)
                            if doc.get("is_binary") and doc.get("bytes"):
                                fpath.write_bytes(doc["bytes"])
                            elif doc.get("text") is not None:
                                fpath.write_text(doc["text"], encoding="utf-8")
        except Exception as exc:
            print(f"[RunManager Warning] Failed to restore artifacts for index: {exc}")

        files = sorted(
            path.name
            for path in directory.iterdir()
            if path.is_file() and is_downloadable(path.name)
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
        self._validate_id(run_id)
        if not is_downloadable(filename):
            raise FileNotFoundError(filename)
        path = self.run_dir(run_id) / filename
        if path.is_file():
            return path
        # If missing on disk (e.g. Render container wiped), restore from MongoDB
        try:
            col = get_artifacts_collection()
            if col is not None:
                doc = col.find_one({"run_id": run_id, "filename": filename})
                if doc:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    if doc.get("is_binary") and doc.get("bytes"):
                        path.write_bytes(doc["bytes"])
                    elif doc.get("text") is not None:
                        path.write_text(doc["text"], encoding="utf-8")
                    return path
        except Exception as exc:
            print(f"[RunManager Warning] Failed to restore artifact {filename} from MongoDB: {exc}")

        if self.get_run(run_id) is None or not path.is_file():
            raise FileNotFoundError(filename)
        return path

    @staticmethod
    def _validate_id(run_id: str) -> None:
        if not RUN_ID_PATTERN.fullmatch(run_id or ""):
            raise KeyError(run_id)


manager = RunManager()

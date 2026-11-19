"""Adapter exposing the existing LangGraph workflow to the run API."""

import json
from pathlib import Path
from typing import Callable

from src.orchestrator import graph

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
    """Small usage adapter for token counts produced by the LangGraph nodes."""

    def __init__(self) -> None:
        self._by_agent: dict[str, dict] = {}

    def set_usage(self, usage: dict) -> None:
        self._by_agent = usage

    def snapshot(self) -> dict:
        return self._by_agent


def _jsonable(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "dict"):
        return value.dict()
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def _write_json(directory: Path, filename: str, value) -> None:
    (directory / filename).write_text(
        json.dumps(_jsonable(value), indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def run_pipeline(
    file_path: str | Path,
    output_dir: str | Path,
    progress_callback: Callable[[dict], None] | None = None,
    usage_tracker_callback: Callable[[UsageTracker], None] | None = None,
) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tracker = UsageTracker()
    if usage_tracker_callback:
        usage_tracker_callback(tracker)

    state = {"file_path": str(file_path), "agent_tokens": {}, "total_tokens": None}
    specification_path = Path(file_path)
    stage_map = {
        "understand": ("understanding", "understanding.json"),
        "decompose": ("decomposer", "decomposition.json"),
        "describe": ("description", "descriptions.json"),
        "pseudocode": ("pseudocode", "pseudocode.json"),
        "generate": ("rtl_generation", "rtl_generation.json"),
        "verify": ("rtl_verification", "rtl_verification.json"),
        "reflect": ("reflection", "reflection.json"),
    }
    stage_status: dict[str, str] = {}
    verification_attempt = 0
    reflection_attempt = 0
    try:
        if progress_callback:
            progress_callback({"stage": "ingestion", "status": "running"})
        for update in graph.stream(state, stream_mode="updates"):
            for node, result in update.items():
                state.update(result)
                state["agent_tokens"] = {
                    **state.get("agent_tokens", {}),
                    **result.get("agent_tokens", {}),
                }
                if node == "ingest" and progress_callback:
                    progress_callback({"stage": "ingestion", "status": "completed"})
                mapped = stage_map.get(node)
                if mapped:
                    name, filename = mapped
                    value_key = {
                        "understand": "understanding",
                        "decompose": "decomposition",
                        "describe": "descriptions",
                        "pseudocode": "pseudocode",
                        "generate": "generated_outputs",
                        "verify": "verification",
                        "reflect": "reflection",
                    }[node]
                    _write_json(output_dir, filename, state.get(value_key))
                    if node == "verify":
                        verification_attempt += 1
                        _write_json(
                            output_dir,
                            f"rtl_verification_attempt_{verification_attempt}.json",
                            state.get(value_key),
                        )
                    elif node == "reflect":
                        reflection_attempt += 1
                        _write_json(
                            output_dir,
                            f"reflection_attempt_{reflection_attempt}.json",
                            state.get(value_key),
                        )
                    elif node == "generate":
                        generated = state.get("generated_outputs") or []
                        code = getattr(generated[0], "code", None) if generated else None
                        if isinstance(code, str) and code.strip():
                            lowered = code.lower()
                            if "library ieee" in lowered or "entity " in lowered:
                                extension = ".vhd"
                            elif "module " in lowered:
                                extension = ".v"
                            else:
                                extension = None
                            if extension:
                                for artifact in ("top_level_rtl", "integrated_rtl"):
                                    (output_dir / f"{artifact}{extension}").write_text(
                                        code, encoding="utf-8"
                                    )
                    stage_status[name] = "completed"
                    if progress_callback:
                        progress_callback({"stage": name, "status": "completed"})
    except Exception as error:
        current = (
            "ingestion"
            if "parent" not in state
            else next((name for name in AGENT_ORDER if name not in stage_status), "rtl_verification")
        )
        stage_status[current] = "failed"
        if progress_callback:
            progress_callback({"stage": current, "status": "failed", "error": str(error)})
        raise

    usage = {}
    for agent, counts in state.get("agent_tokens", {}).items():
        prompt_tokens = counts.get("input_tokens", counts.get("prompt_tokens", 0))
        completion_tokens = counts.get("output_tokens", counts.get("completion_tokens", 0))
        usage[agent] = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": counts.get(
                "total_tokens", prompt_tokens + completion_tokens
            ),
            "calls": 1,
            "calls_without_usage": 0,
            "complete": True,
        }
    tracker.set_usage(usage)
    source_text = "\n\n".join(
        getattr(document, "page_content", str(document))
        for document in state.get("parent", [])
    )
    (output_dir / "specification.txt").write_text(source_text, encoding="utf-8")
    _write_json(
        output_dir,
        "input_summary.json",
        {"input_file": specification_path.name},
    )

    summary = {
        "overall_status": "completed",
        "stages": stage_status,
        "verification_passed": all(
            item.get("valid", False) if isinstance(item, dict) else getattr(item, "valid", False)
            for item in state.get("verification", [])
        ),
    }
    _write_json(output_dir, "pipeline_summary.json", summary)
    return summary

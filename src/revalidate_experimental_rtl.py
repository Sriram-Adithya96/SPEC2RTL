"""Revalidate saved experimental RTL responses without invoking an LLM."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import uuid

from src.agents.rtl_generation import (
    _integrate_component_rtl,
    extract_json,
    validate_rtl_output,
)
from src.schemas import (
    ComponentRTLModuleOutput,
    DecompositionOutput,
    PseudocodeGenerationOutput,
    Understanding,
)


EXPERIMENTAL_LABEL = "EXPERIMENTAL — NOT PRODUCTION VERIFIED"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "experimental-runs"


def _new_output_directory(output_root: Path) -> tuple[str, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    while True:
        run_id = (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            + "-"
            + uuid.uuid4().hex[:12]
        )
        output_dir = output_root / f"revalidation-{run_id}"
        try:
            output_dir.mkdir()
        except FileExistsError:
            continue
        return run_id, output_dir


def _load_model(path: Path, model_type):
    return model_type.model_validate(
        json.loads(path.read_text(encoding="utf-8"))
    )


def _safe_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")
    return safe or "component"


def _source_raw_path(source_run: Path, record: dict) -> Path:
    raw_reference = record.get("raw_response_path")
    if not isinstance(raw_reference, str) or not raw_reference:
        raise ValueError("The source manifest has no raw response path.")
    raw_path = (source_run / raw_reference).resolve()
    if source_run.resolve() not in raw_path.parents:
        raise ValueError("The raw response path must remain inside the source run.")
    return raw_path


def _validate_saved_response(
    raw_content: str,
    component,
    component_pseudocode,
) -> tuple[ComponentRTLModuleOutput, dict]:
    if component_pseudocode.inputs != component.inputs:
        raise ValueError(
            "Saved pseudocode inputs do not match the decomposition interface."
        )
    if component_pseudocode.outputs != component.outputs:
        raise ValueError(
            "Saved pseudocode outputs do not match the decomposition interface."
        )
    data = json.loads(extract_json(raw_content))
    for field in ("module_name", "language", "rtl_code"):
        if not isinstance(data.get(field), str):
            raise ValueError(f"RTL response {field} must be a string.")
    if data["module_name"] != component_pseudocode.module_name:
        raise ValueError(
            f"Expected module '{component_pseudocode.module_name}', "
            f"but received '{data['module_name']}'."
        )
    if data["language"] != "Verilog":
        raise ValueError("RTL response language must be 'Verilog'.")
    if not isinstance(data.get("assumptions"), list) or not all(
        isinstance(item, str) for item in data["assumptions"]
    ):
        raise ValueError("RTL response assumptions must be an array of strings.")
    if data["assumptions"] != component_pseudocode.assumptions:
        raise ValueError(
            "RTL assumptions do not exactly match the saved component pseudocode."
        )
    if not isinstance(data.get("unresolved_issues"), list) or not all(
        isinstance(item, str) for item in data["unresolved_issues"]
    ):
        raise ValueError(
            "RTL response unresolved_issues must be an array of strings."
        )

    module = ComponentRTLModuleOutput(
        component_name=component.name,
        module_name=data["module_name"],
        inputs=component.inputs,
        outputs=component.outputs,
        rtl_code=data["rtl_code"],
    )
    validate_rtl_output(
        module,
        expected_module_name=component_pseudocode.module_name,
        expected_inputs=component.inputs,
        expected_outputs=component.outputs,
    )
    module.generation_status = "completed"
    return module, {
        "language": data["language"],
        "assumptions": data["assumptions"],
        "unresolved_issues": data["unresolved_issues"],
    }


def revalidate_saved_run(
    source_run_dir: str | Path,
    artifacts_dir: str | Path,
    *,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
) -> dict:
    """Revalidate saved responses and integrate only if every component passes."""

    source_run = Path(source_run_dir).resolve()
    artifacts = Path(artifacts_dir)
    source_manifest_path = source_run / "manifest.json"
    if not source_manifest_path.is_file():
        raise FileNotFoundError(
            f"Experimental run manifest not found: {source_manifest_path}"
        )
    source_manifest = json.loads(
        source_manifest_path.read_text(encoding="utf-8")
    )
    if not isinstance(source_manifest.get("components"), list):
        raise ValueError("The source manifest has no valid components array.")

    understanding = _load_model(
        artifacts / "understanding.json",
        Understanding,
    )
    decomposition = _load_model(
        artifacts / "decomposition.json",
        DecompositionOutput,
    )
    pseudocode = _load_model(
        artifacts / "pseudocode.json",
        PseudocodeGenerationOutput,
    )

    run_id, output_dir = _new_output_directory(Path(output_root))
    raw_output_dir = output_dir / "raw"
    component_output_dir = output_dir / "components"
    raw_output_dir.mkdir()
    component_output_dir.mkdir()

    source_records: dict[str, list[dict]] = {}
    for record in source_manifest["components"]:
        if isinstance(record, dict) and isinstance(
            record.get("component_name"), str
        ):
            source_records.setdefault(record["component_name"], []).append(record)
    pseudocode_records = {}
    for record in pseudocode.components:
        pseudocode_records.setdefault(record.component_name, []).append(record)

    result = {
        "label": EXPERIMENTAL_LABEL,
        "production_verified": False,
        "revalidation_id": run_id,
        "source_run_directory": str(source_run),
        "source_manifest": str(source_manifest_path),
        "output_directory": str(output_dir.resolve()),
        "pseudocode": pseudocode.model_dump(),
        "generation_status": "failed",
        "components": [],
        "integration": {
            "label": EXPERIMENTAL_LABEL,
            "status": "not_attempted",
            "errors": [],
            "top_module_name": None,
            "component_instances": [],
            "top_level_rtl_path": None,
            "integrated_rtl_path": None,
        },
    }

    validated_modules = []
    for index, component in enumerate(decomposition.components, start=1):
        record = {
            "label": EXPERIMENTAL_LABEL,
            "component_name": component.name,
            "generation_status": "failed",
            "validation_status": "failed",
            "validation_errors": [],
            "rtl_response_unresolved_issues": [],
            "rtl_code": "",
            "raw_response_path": None,
            "rtl_path": None,
        }
        result["components"].append(record)

        component_records = source_records.get(component.name, [])
        if len(component_records) != 1:
            record["validation_errors"].append(
                f"Expected exactly one source manifest record; "
                f"found {len(component_records)}."
            )
            continue
        pseudo_records = pseudocode_records.get(component.name, [])
        if len(pseudo_records) != 1:
            record["validation_errors"].append(
                f"Expected exactly one pseudocode record; "
                f"found {len(pseudo_records)}."
            )
            continue

        try:
            source_raw_path = _source_raw_path(
                source_run,
                component_records[0],
            )
            raw_content = source_raw_path.read_text(encoding="utf-8")
            copied_raw_path = raw_output_dir / (
                f"{index:03d}-{_safe_name(component.name)}.txt"
            )
            copied_raw_path.write_text(raw_content, encoding="utf-8")
            record["source_raw_response_path"] = str(source_raw_path)
            record["raw_response_path"] = str(
                copied_raw_path.relative_to(output_dir)
            )
            module, response_metadata = _validate_saved_response(
                raw_content,
                component,
                pseudo_records[0],
            )
            rtl_path = component_output_dir / (
                f"{index:03d}-{_safe_name(module.module_name)}.v"
            )
            rtl_path.write_text(
                f"// {EXPERIMENTAL_LABEL}\n{module.rtl_code}\n",
                encoding="utf-8",
            )
            record.update({
                "module_name": module.module_name,
                "inputs": list(component.inputs),
                "outputs": list(component.outputs),
                "generation_status": "revalidated",
                "validation_status": "passed",
                "validation_errors": [],
                "assumptions": response_metadata["assumptions"],
                "rtl_response_unresolved_issues": (
                    response_metadata["unresolved_issues"]
                ),
                "rtl_code": module.rtl_code,
                "rtl_path": str(rtl_path.relative_to(output_dir)),
            })
            validated_modules.append(module)
        except Exception as error:
            record["validation_errors"].append(
                f"{type(error).__name__}: {error}"
            )
            record["validation_status"] = "failed"

    all_components_passed = (
        bool(decomposition.components)
        and len(validated_modules) == len(decomposition.components)
        and all(
            item["validation_status"] == "passed"
            for item in result["components"]
        )
    )
    result["generation_status"] = (
        "completed" if all_components_passed else "failed"
    )

    if not all_components_passed:
        result["integration"]["errors"].append(
            "Integration was skipped because one or more component RTL "
            "responses did not pass revalidation."
        )
    else:
        try:
            top_name, top_rtl, instances, integrated_rtl = (
                _integrate_component_rtl(
                    decomposition.components,
                    validated_modules,
                    decomposition,
                    understanding,
                )
            )
            top_path = output_dir / "top_level_rtl.v"
            integrated_path = output_dir / "integrated_rtl.v"
            top_path.write_text(
                f"// {EXPERIMENTAL_LABEL}\n{top_rtl}\n",
                encoding="utf-8",
            )
            integrated_path.write_text(
                f"// {EXPERIMENTAL_LABEL}\n{integrated_rtl}\n",
                encoding="utf-8",
            )
            result["integration"].update({
                "status": "completed",
                "top_module_name": top_name,
                "component_instances": [
                    item.model_dump() for item in instances
                ],
                "top_level_rtl_path": str(top_path.relative_to(output_dir)),
                "integrated_rtl_path": str(
                    integrated_path.relative_to(output_dir)
                ),
            })
        except Exception as error:
            result["integration"]["status"] = "failed"
            result["integration"]["errors"].append(
                f"{type(error).__name__}: {error}"
            )

    manifest_path = output_dir / "revalidation_manifest.json"
    manifest_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(f"{EXPERIMENTAL_LABEL}: {output_dir}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Revalidate saved experimental RTL responses offline. "
            "No RTL generation or LLM calls are performed."
        )
    )
    parser.add_argument(
        "--source-run",
        type=Path,
        required=True,
        help="Existing experimental run directory containing manifest.json and raw/.",
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        required=True,
        help="Diagnostic run directory containing understanding, decomposition, and pseudocode JSON.",
    )
    args = parser.parse_args()
    revalidate_saved_run(args.source_run, args.artifacts_dir)


if __name__ == "__main__":
    main()

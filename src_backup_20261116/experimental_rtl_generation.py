"""Experimental RTL generation that does not alter production pipeline gates."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import uuid

from src.agents.rtl_generation import (
    _generate_component_rtl,
    _integrate_component_rtl,
    get_llm,
)
from src.ingestion import ingest_spec
from src.schemas import (
    ComponentPseudocodeOutput,
    DecompositionOutput,
    DescriptionOutput,
    PseudocodeGenerationOutput,
    Understanding,
)


EXPERIMENTAL_LABEL = (
    "EXPERIMENTAL — PSEUDOCODE VALIDATION NOT PASSED — "
    "NOT PRODUCTION VERIFIED"
)
UNVERIFIED_LABEL = "EXPERIMENTAL — NOT PRODUCTION VERIFIED"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "experimental-runs"


def _new_run_directory(output_root: Path) -> tuple[str, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    while True:
        run_id = (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            + "-"
            + uuid.uuid4().hex[:12]
        )
        run_dir = output_root / run_id
        try:
            run_dir.mkdir()
        except FileExistsError:
            continue
        return run_id, run_dir


def _safe_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")
    return safe or "component"


def _component_source_record(
    component: ComponentPseudocodeOutput,
) -> dict:
    return {
        "generation_status": component.generation_status,
        "validation_status": component.validation_status,
        "validation_issues": component.model_dump()["validation_issues"],
        "unresolved_issues": list(component.unresolved_issues),
        "assumptions": list(component.assumptions),
    }


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def run_experimental_rtl_generation(
    specification: str,
    decomposition: DecompositionOutput,
    understanding: Understanding,
    descriptions: list[DescriptionOutput],
    pseudocode: PseudocodeGenerationOutput,
    *,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    specification_path: str | Path | None = None,
    reflection_feedback: object = None,
) -> dict:
    """Generate component RTL drafts and attempt integration in a unique directory."""

    run_id, run_dir = _new_run_directory(Path(output_root))
    raw_dir = run_dir / "raw"
    component_dir = run_dir / "components"
    raw_dir.mkdir()
    component_dir.mkdir()
    run_label = (
        EXPERIMENTAL_LABEL
        if pseudocode.validation_status not in {"Passed", "Warnings"}
        else UNVERIFIED_LABEL
    )

    pseudocode_by_name: dict[str, list[ComponentPseudocodeOutput]] = {}
    for item in pseudocode.components:
        pseudocode_by_name.setdefault(item.component_name, []).append(item)
    descriptions_by_name: dict[str, list[DescriptionOutput]] = {}
    for item in descriptions:
        descriptions_by_name.setdefault(item.module_name, []).append(item)

    manifest = {
        "label": run_label,
        "production_verified": False,
        "run_id": run_id,
        "specification_path": (
            str(Path(specification_path).resolve())
            if specification_path is not None
            else None
        ),
        "generation_status": "failed",
        "pseudocode": {
            "generation_status": pseudocode.generation_status,
            "validation_status": pseudocode.validation_status,
            "validation_issues": pseudocode.model_dump()["validation_issues"],
            "unresolved_issues": list(pseudocode.unresolved_issues),
            "execution_status": pseudocode.execution_status,
            "execution_errors": list(pseudocode.execution_errors),
        },
        "compilation": {
            "status": "not_run",
            "errors": [],
        },
        "components": [],
        "integration": {
            "label": run_label,
            "status": "not_attempted",
            "errors": [],
            "top_module_name": None,
            "component_instances": [],
            "top_level_rtl": "",
            "integrated_rtl": "",
            "rtl_path": None,
        },
    }

    generation_candidates = []
    for index, decomposed in enumerate(decomposition.components, start=1):
        matches = pseudocode_by_name.get(decomposed.name, [])
        description_matches = descriptions_by_name.get(decomposed.name, [])
        source_records = [_component_source_record(item) for item in matches]
        record = {
            "label": run_label,
            "component_name": decomposed.name,
            "module_name": matches[0].module_name if len(matches) == 1 else "",
            "inputs": list(decomposed.inputs),
            "outputs": list(decomposed.outputs),
            "source_pseudocode": source_records,
            "source_description": (
                description_matches[0].model_dump()
                if len(description_matches) == 1
                else None
            ),
            "generation_status": "failed",
            "interface_validation_status": "not_run",
            "interface_validation_errors": [],
            "rtl_structural_validation": "not_run",
            "generation_error": None,
            "rtl_response_unresolved_issues": [],
            "rtl_code": "",
            "raw_response_path": None,
            "rtl_path": None,
        }
        manifest["components"].append(record)
        if len(matches) != 1:
            record["generation_error"] = (
                f"Expected exactly one pseudocode result for component "
                f"'{decomposed.name}', found {len(matches)}."
            )
            continue
        if len(description_matches) != 1:
            record["generation_error"] = (
                f"Expected exactly one component description for "
                f"'{decomposed.name}', found {len(description_matches)}."
            )
            continue
        if (
            matches[0].inputs != decomposed.inputs
            or matches[0].outputs != decomposed.outputs
        ):
            record["generation_error"] = (
                f"Saved pseudocode interface for '{decomposed.name}' does not "
                "match the decomposition."
            )
            continue
        generation_candidates.append(
            (index, decomposed, description_matches[0], matches[0], record)
        )

    llm = None
    if generation_candidates:
        try:
            llm = get_llm("rtl_generation")
        except Exception as error:
            message = f"{type(error).__name__}: {error}"
            for (
                _index,
                _component,
                _description,
                _pseudocode,
                record,
            ) in generation_candidates:
                record["generation_error"] = message

    component_modules = []
    for (
        index,
        component,
        component_description,
        component_pseudocode,
        record,
    ) in generation_candidates:
        if llm is None:
            continue
        status_details = {}
        try:
            module, response_unresolved = _generate_component_rtl(
                specification,
                component,
                component_pseudocode,
                llm,
                raw_dir,
                experimental=True,
                raw_output_name=(
                    f"{index:03d}-{component_pseudocode.module_name}"
                ),
                component_description=component_description,
                status_details=status_details,
                reflection_feedback=reflection_feedback,
            )
        except Exception as error:
            record["generation_error"] = (
                f"{type(error).__name__}: {error}"
            )
            continue

        failure_stage = status_details.get("failure_stage", "generation")
        generated = failure_stage in {"interface_validation", "completed"}
        record.update({
            "module_name": module.module_name,
            "generation_status": (
                "completed" if generated else "failed"
            ),
            "interface_validation_status": (
                "passed"
                if failure_stage == "completed"
                else (
                    "failed"
                    if failure_stage == "interface_validation"
                    else "not_run"
                )
            ),
            "rtl_structural_validation": (
                "passed"
                if failure_stage == "completed"
                else (
                    "failed"
                    if failure_stage == "interface_validation"
                    else "not_run"
                )
            ),
            "generation_error": (
                None if generated else module.generation_error
            ),
            "interface_validation_errors": (
                [module.generation_error]
                if failure_stage == "interface_validation"
                and module.generation_error
                else []
            ),
            "rtl_response_unresolved_issues": response_unresolved,
            "rtl_code": module.rtl_code,
        })

        raw_name = _safe_name(
            f"{index:03d}-{component_pseudocode.module_name}"
        )
        raw_path = raw_dir / f"rtl_generation_raw_{raw_name}.txt"
        if raw_path.is_file():
            record["raw_response_path"] = str(raw_path.relative_to(run_dir))
        if module.rtl_code:
            rtl_path = component_dir / (
                f"{index:03d}-{_safe_name(component_pseudocode.module_name)}.v"
            )
            rtl_path.write_text(
                f"// {run_label}\n{module.rtl_code}\n",
                encoding="utf-8",
            )
            record["rtl_path"] = str(rtl_path.relative_to(run_dir))
        if failure_stage == "completed":
            component_modules.append(module)

    if not decomposition.components:
        manifest["integration"]["status"] = "failed"
        manifest["integration"]["errors"].append(
            "The decomposition contains no components."
        )
    elif len(component_modules) != len(decomposition.components):
        manifest["integration"]["status"] = "not_attempted"
        manifest["integration"]["errors"].append(
            "Integration requires a structurally valid RTL module for every "
            "decomposed component."
        )
    else:
        try:
            top_name, top_rtl, instances, integrated_rtl = (
                _integrate_component_rtl(
                    decomposition.components,
                    component_modules,
                    decomposition,
                    understanding,
                )
            )
            top_path = run_dir / "top_level_rtl.v"
            integrated_path = run_dir / "integrated_rtl.v"
            top_path.write_text(
                f"// {run_label}\n{top_rtl}\n",
                encoding="utf-8",
            )
            integrated_path.write_text(
                f"// {run_label}\n{integrated_rtl}\n",
                encoding="utf-8",
            )
            manifest["integration"].update({
                "status": "completed",
                "top_module_name": top_name,
                "component_instances": [
                    item.model_dump() for item in instances
                ],
                "top_level_rtl": top_rtl,
                "integrated_rtl": integrated_rtl,
                "rtl_path": str(integrated_path.relative_to(run_dir)),
            })
        except Exception as error:
            manifest["integration"]["status"] = "failed"
            manifest["integration"]["errors"].append(
                f"{type(error).__name__}: {error}"
            )

    manifest["generation_status"] = (
        "completed"
        if manifest["components"]
        and all(
            item["generation_status"] == "completed"
            and item["interface_validation_status"] == "passed"
            for item in manifest["components"]
        )
        else "failed"
    )
    pseudocode_diagnostics = {
        "label": run_label,
        "generation_status": pseudocode.generation_status,
        "validation_status": pseudocode.validation_status,
        "validation_issues": pseudocode.model_dump()["validation_issues"],
        "unresolved_issues": list(pseudocode.unresolved_issues),
        "components": [
            {
                "component_name": item.component_name,
                "generation_status": item.generation_status,
                "validation_status": item.validation_status,
                "validation_issues": item.model_dump()["validation_issues"],
                "unresolved_issues": list(item.unresolved_issues),
            }
            for item in pseudocode.components
        ],
    }
    _write_json(run_dir / "pseudocode_validation.json", pseudocode_diagnostics)

    if manifest["generation_status"] != "completed":
        if any(
            item["interface_validation_status"] == "failed"
            for item in manifest["components"]
        ):
            overall_status = "component_interface_validation_failed"
        else:
            overall_status = "component_generation_failed"
    elif manifest["integration"]["status"] != "completed":
        overall_status = "integration_failed"
    else:
        overall_status = "completed_unverified"

    summary = {
        "label": run_label,
        "pseudocode_validation_status": pseudocode.validation_status,
        "component_count": len(decomposition.components),
        "components_generated": sum(
            item["generation_status"] == "completed"
            for item in manifest["components"]
        ),
        "components_interface_validated": sum(
            item["interface_validation_status"] == "passed"
            for item in manifest["components"]
        ),
        "integration_status": manifest["integration"]["status"],
        "compilation_status": manifest["compilation"]["status"],
        "overall_experimental_status": overall_status,
        "production_verified": False,
    }
    manifest["summary"] = summary
    manifest["run_directory"] = str(run_dir.resolve())
    _write_json(run_dir / "generation_summary.json", summary)
    _write_json(run_dir / "manifest.json", manifest)
    print(f"{run_label}: {run_dir}")
    return manifest


def _load_specification(spec_path: Path) -> str:
    if not spec_path.is_file():
        raise FileNotFoundError(f"Specification document not found: {spec_path}")
    docs, _parents, _children = ingest_spec(str(spec_path))
    specification = "\n\n".join(doc.page_content for doc in docs).strip()
    if not specification:
        raise ValueError("The extracted specification is empty.")
    return specification


def _load_artifacts(artifacts_dir: Path):
    understanding = Understanding.model_validate(
        json.loads((artifacts_dir / "understanding.json").read_text(
            encoding="utf-8"
        ))
    )
    decomposition = DecompositionOutput.model_validate(
        json.loads((artifacts_dir / "decomposition.json").read_text(
            encoding="utf-8"
        ))
    )
    descriptions_payload = json.loads(
        (artifacts_dir / "descriptions.json").read_text(encoding="utf-8")
    )
    if not isinstance(descriptions_payload, list):
        raise ValueError("descriptions.json must contain an array.")
    descriptions = [
        DescriptionOutput.model_validate(item)
        for item in descriptions_payload
    ]
    pseudocode = PseudocodeGenerationOutput.model_validate(
        json.loads((artifacts_dir / "pseudocode.json").read_text(
            encoding="utf-8"
        ))
    )
    return understanding, decomposition, descriptions, pseudocode


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate experimental RTL from existing SPEC2RTL artifacts. "
            "This does not run or modify the production pipeline."
        )
    )
    parser.add_argument(
        "--spec",
        type=Path,
        required=True,
        help="Hardware specification document (PDF or DOCX).",
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=PROJECT_ROOT / "outputs",
        help=(
            "Directory containing understanding.json, decomposition.json, "
            "descriptions.json, and pseudocode.json."
        ),
    )
    args = parser.parse_args()

    understanding, decomposition, descriptions, pseudocode = _load_artifacts(
        args.artifacts_dir
    )
    run_experimental_rtl_generation(
        _load_specification(args.spec),
        decomposition,
        understanding,
        descriptions,
        pseudocode,
        specification_path=args.spec,
    )


if __name__ == "__main__":
    main()

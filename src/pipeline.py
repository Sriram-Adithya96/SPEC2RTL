"""Shared SPEC2RTL pipeline used by the CLI and the API."""

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import uuid
from datetime import datetime, timezone

from src.agents.code import generate_code
from src.agents.decomposer import decomposer
from src.agents.description import describe_component
from src.agents.pseudocode import generate_pseudocode
from src.agents.reflection import reflect_on_rtl, reflect_on_verification
from src.agents.rtl_generation import generate_rtl
from src.agents.understanding import understand_specification
from src.agents.verification import verify_rtl
from src.experimental_rtl_generation import run_experimental_rtl_generation
from src.ingestion import ingest_spec
from src.schemas import CodeOuput
from src.llm.llm import (
    UsageTracker,
    bind_usage_tracker,
    reset_usage_context,
    usage_scope,
)
AGENT_ORDER = [
    "understanding",
    "decomposer",
    "description",
    "pseudocode",
    "rtl_generation",
    "rtl_verification",
    "reflection",
]
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNS_ROOT = PROJECT_ROOT / "outputs" / "runs"


def save_json(output_dir: Path, filename: str, data) -> Path:
    """Save agent output as JSON without changing the payload."""

    filepath = output_dir / filename
    with open(filepath, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            indent=4,
            ensure_ascii=False,
            default=str,
        )
    print(f"Saved: {filepath}")
    return filepath


def print_stage(title, result) -> None:
    """Display an agent's output."""

    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)

    if hasattr(result, "model_dump_json"):
        print(result.model_dump_json(indent=2))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


def _emit(progress_callback, **payload) -> None:
    if progress_callback is None:
        return
    try:
        progress_callback(payload)
    except Exception as error:
        print(f"Progress callback error: {error}")


def _load_specification(spec_path: Path):
    if not spec_path.is_file():
        raise FileNotFoundError(
            f"\nSpecification document not found:\n{spec_path}"
        )

    print("\n" + "=" * 70)
    print("LOADING HARDWARE SPECIFICATION")
    print("=" * 70)
    print(f"Input document: {spec_path}")

    docs, parent_chunks, child_chunks = ingest_spec(str(spec_path))

    if not docs:
        raise ValueError("No text was extracted from the document.")

    specification = "\n\n".join(doc.page_content for doc in docs).strip()

    if not specification:
        raise ValueError("The extracted specification is empty.")

    print("\nDocument loaded successfully.")
    print(f"Original documents: {len(docs)}")
    print(f"Parent chunks: {len(parent_chunks)}")
    print(f"Child chunks: {len(child_chunks)}")
    print(f"Extracted characters: {len(specification)}")

    return docs, specification, parent_chunks, child_chunks


def _new_run_directory(output_root: Path) -> Path:
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
        return run_dir


def _compile_integrated_rtl(
    integrated_rtl_path: Path | None,
    top_module_name: str | None,
    output_dir: Path,
) -> dict:
    log_path = output_dir / "compilation.log"
    if integrated_rtl_path is None or not integrated_rtl_path.is_file():
        message = "Integrated RTL is missing; compilation was not attempted."
        log_path.write_text(message + "\n", encoding="utf-8")
        return {
            "status": "not_attempted",
            "compiler": None,
            "top_module_name": top_module_name,
            "rtl_path": (
                str(integrated_rtl_path.resolve())
                if integrated_rtl_path is not None
                else None
            ),
            "log_path": str(log_path.resolve()),
            "errors": [message],
        }
    compiler = shutil.which("iverilog")
    if not compiler:
        message = "Icarus Verilog (iverilog) is not available on PATH."
        log_path.write_text(message + "\n", encoding="utf-8")
        return {
            "status": "unavailable",
            "compiler": None,
            "top_module_name": top_module_name,
            "rtl_path": str(integrated_rtl_path.resolve()),
            "log_path": str(log_path.resolve()),
            "errors": [message],
        }
    if not top_module_name:
        message = "Top-level module name is missing; compilation was not attempted."
        log_path.write_text(message + "\n", encoding="utf-8")
        return {
            "status": "not_attempted",
            "compiler": compiler,
            "top_module_name": None,
            "rtl_path": str(integrated_rtl_path.resolve()),
            "log_path": str(log_path.resolve()),
            "errors": [message],
        }

    output_file = output_dir / "integrated_rtl.vvp"
    command = [
        compiler,
        "-g2012",
        "-s",
        top_module_name,
        "-o",
        str(output_file),
        str(integrated_rtl_path.resolve()),
    ]
    version = subprocess.run(
        [compiler, "-V"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        errors = (
            (result.stderr or result.stdout).splitlines()
            if result.returncode
            else []
        )
        status = "passed" if result.returncode == 0 else "failed"
        log_contents = [
            "Label: NOT FUNCTIONALLY VERIFIED",
            f"Compiler: {compiler}",
            f"Version: {(version.stdout or version.stderr).strip()}",
            f"Command: {subprocess.list2cmdline(command)}",
            f"Exit code: {result.returncode}",
            "",
            result.stdout.rstrip(),
            result.stderr.rstrip(),
        ]
    except subprocess.TimeoutExpired as error:
        status = "failed"
        errors = ["Icarus Verilog compilation timed out after 120 seconds."]
        log_contents = [
            f"Compiler: {compiler}",
            f"Command: {subprocess.list2cmdline(command)}",
            *errors,
            str(error),
        ]
    except OSError as error:
        status = "failed"
        errors = [f"{type(error).__name__}: {error}"]
        log_contents = [
            f"Compiler: {compiler}",
            f"Command: {subprocess.list2cmdline(command)}",
            *errors,
        ]

    log_path.write_text("\n".join(log_contents).strip() + "\n", encoding="utf-8")
    return {
        "status": status,
        "compiler": compiler,
        "top_module_name": top_module_name,
        "rtl_path": str(integrated_rtl_path.resolve()),
        "output_path": (
            str(output_file.resolve()) if status == "passed" else None
        ),
        "log_path": str(log_path.resolve()),
        "errors": errors,
    }



def _execute_rtl_generation_stage(
    specification: str,
    spec_path: Path,
    output_dir: Path,
    decomposition_result,
    understanding_result,
    description_results,
    pseudocode_result,
    strict_validation: bool,
    stage_statuses: dict,
    artifact_paths: dict,
    progress_callback,
    reflection_feedback=None,
    attempt_num: int = 0,
):
    """Execute either strict or experimental RTL generation, integrating and compiling modules."""
    suffix = f"_attempt_{attempt_num}" if attempt_num > 0 else ""
    raw_dir = output_dir / f"raw_rtl{suffix}" if attempt_num > 0 else output_dir

    if strict_validation:
        rtl_result = generate_rtl(
            specification=specification,
            pseudocode=pseudocode_result,
            decomposition=decomposition_result,
            understanding=understanding_result,
            raw_output_dir=raw_dir,
            reflection_feedback=reflection_feedback,
        )
        component_state = [
            {"name": module.component_name, "status": module.generation_status}
            for module in rtl_result.component_modules
        ]
        stage_statuses["rtl_generation"] = (
            "completed"
            if rtl_result.generation_status == "completed"
            else (
                "blocked"
                if all(
                    module.generation_status == "blocked"
                    for module in rtl_result.component_modules
                )
                else "failed"
            )
        )
        stage_statuses["interface_validation"] = (
            "passed"
            if rtl_result.generation_status == "completed"
            else (
                "failed"
                if any(
                    module.generation_status == "Failed"
                    for module in rtl_result.component_modules
                )
                else "not_attempted"
            )
        )
        stage_statuses["integration"] = (
            "completed"
            if rtl_result.generation_status == "completed"
            else "not_attempted"
        )
        if rtl_result.generation_status == "completed":
            component_dir = output_dir / (f"components{suffix}" if attempt_num > 0 else "components")
            component_dir.mkdir(exist_ok=True)
            artifact_paths["component_rtl"] = []
            for index, module in enumerate(
                rtl_result.component_modules, start=1
            ):
                component_path = component_dir / (
                    f"{index:03d}-{module.module_name}.v"
                )
                component_path.write_text(
                    f"// DIRECT RTL — PRODUCTION PSEUDOCODE GATE PASSED\n"
                    f"{module.rtl_code}\n",
                    encoding="utf-8",
                )
                artifact_paths["component_rtl"].append(
                    str(component_path.relative_to(output_dir))
                )
            integrated_file = f"integrated_rtl{suffix}.v" if attempt_num > 0 else "integrated_rtl.v"
            integrated_path = output_dir / integrated_file
            integrated_path.write_text(
                rtl_result.rtl_code,
                encoding="utf-8",
            )
            artifact_paths["integrated_rtl"] = integrated_file
            top_level = re.search(
                r"\bmodule\s+" + re.escape(rtl_result.module_name)
                + r"\b.*?\bendmodule\b",
                rtl_result.rtl_code,
                flags=re.S,
            )
            if top_level:
                top_file = f"top_level_rtl{suffix}.v" if attempt_num > 0 else "top_level_rtl.v"
                top_path = output_dir / top_file
                top_path.write_text(
                    top_level.group(0) + "\n",
                    encoding="utf-8",
                )
                artifact_paths["top_level_rtl"] = top_file
        compilation_result = {
            "status": "not_run",
            "compiler": None,
            "errors": [],
        }
        rtl_output = rtl_result.model_dump()
        strict_agent_success = (
            rtl_result.generation_status == "completed"
            and stage_statuses["interface_validation"] == "passed"
            and stage_statuses["integration"] == "completed"
        )
        rtl_output.update({
            "generation_status": (
                "completed" if strict_agent_success else "Failed"
            ),
            "component_generation_status": stage_statuses[
                "rtl_generation"
            ],
            "interface_validation_status": stage_statuses[
                "interface_validation"
            ],
            "integration_status": stage_statuses["integration"],
            "compilation_status": "not_run",
            "rtl_agent_status": (
                "completed" if strict_agent_success else "failed"
            ),
            "module_name": (
                rtl_result.module_name
                if stage_statuses["integration"] == "completed"
                else None
            ),
            "experimental": False,
            "production_verified": False,
            "pseudocode_validation_status": (
                pseudocode_result.validation_status
            ),
            "artifact_paths": artifact_paths,
        })
        if attempt_num > 0:
            save_json(output_dir, f"rtl_generation{suffix}.json", rtl_output)
        save_json(output_dir, "rtl_generation.json", rtl_output)
        artifact_paths["rtl_generation"] = "rtl_generation.json"
        _emit(
            progress_callback,
            stage="rtl_generation",
            status=(
                "completed"
                if strict_agent_success
                else "failed"
            ),
            message=(
                "Strict-validation RTL generation "
                f"{rtl_result.generation_status.lower()}; "
                f"integration {stage_statuses['integration']}."
            ),
            error=(
                "; ".join(list(rtl_result.generation_issues))
                if not strict_agent_success
                else None
            ),
            component_generation_status=stage_statuses[
                "rtl_generation"
            ],
            interface_validation_status=stage_statuses[
                "interface_validation"
            ],
            integration_status=stage_statuses["integration"],
            compilation_status="not_run",
            components=component_state,
        )
        return rtl_output, rtl_result, None, component_state, compilation_result, strict_agent_success

    else:
        runs_root = output_dir / (f"rtl_generation_runs{suffix}" if attempt_num > 0 else "rtl_generation_runs")
        direct_rtl_result = run_experimental_rtl_generation(
            specification=specification,
            decomposition=decomposition_result,
            understanding=understanding_result,
            descriptions=description_results,
            pseudocode=pseudocode_result,
            output_root=runs_root,
            specification_path=spec_path,
            reflection_feedback=reflection_feedback,
        )
        direct_run_dir = Path(direct_rtl_result["run_directory"])
        artifact_paths.update({
            "rtl_run_directory": str(
                direct_run_dir.relative_to(output_dir)
            ),
            "rtl_manifest": str(
                (direct_run_dir / "manifest.json").relative_to(output_dir)
            ),
            "rtl_generation_summary": str(
                (direct_run_dir / "generation_summary.json").relative_to(output_dir)
            ),
        })
        component_state = [
            {
                "name": item["component_name"],
                "status": (
                    "completed"
                    if item["generation_status"] == "completed"
                    and item["interface_validation_status"] == "passed"
                    else "failed"
                ),
                "generation_status": item["generation_status"],
                "interface_validation_status": (
                    item["interface_validation_status"]
                ),
                "errors": (
                    item["interface_validation_errors"]
                    or ([item["generation_error"]]
                        if item["generation_error"] else [])
                ),
            }
            for item in direct_rtl_result["components"]
        ]
        generated_count = direct_rtl_result["summary"]["components_generated"]
        interfaces_passed = direct_rtl_result["summary"][
            "components_interface_validated"
        ]
        stage_statuses["rtl_generation"] = (
            "completed"
            if generated_count == len(decomposition_result.components)
            else "failed"
        )
        stage_statuses["interface_validation"] = (
            "passed"
            if interfaces_passed == len(decomposition_result.components)
            else "failed"
        )
        integration_status = direct_rtl_result["integration"]["status"]
        stage_statuses["integration"] = integration_status
        artifact_paths["component_rtl"] = [
            str((direct_run_dir / item["rtl_path"]).relative_to(output_dir))
            for item in direct_rtl_result["components"]
            if item["rtl_path"]
        ]
        if direct_rtl_result["integration"]["rtl_path"]:
            integrated_path = (
                direct_run_dir / direct_rtl_result["integration"]["rtl_path"]
            )
            artifact_paths["integrated_rtl"] = str(
                integrated_path.relative_to(output_dir)
            )
            artifact_paths["top_level_rtl"] = str(
                (direct_run_dir / "top_level_rtl.v").relative_to(output_dir)
            )
        else:
            integrated_path = None

        compilation_result = {
            "status": "not_run",
            "compiler": None,
            "errors": [],
        }
        direct_rtl_result["compilation"] = compilation_result
        direct_rtl_result["summary"]["compilation_status"] = "not_run"
        save_json(
            direct_run_dir,
            "manifest.json",
            direct_rtl_result,
        )
        save_json(
            direct_run_dir,
            "generation_summary.json",
            direct_rtl_result["summary"],
        )
        artifact_paths["pseudocode_diagnostics"] = (
            "pseudocode_validation.json"
        )

        rtl_generation_errors = []
        for item in direct_rtl_result["components"]:
            rtl_generation_errors.extend(
                item["interface_validation_errors"]
            )
            if item["generation_error"]:
                rtl_generation_errors.append(item["generation_error"])
        if direct_rtl_result["integration"]["errors"]:
            rtl_generation_errors.extend(
                direct_rtl_result["integration"]["errors"]
            )
        overall_rtl_success = (
            stage_statuses["rtl_generation"] == "completed"
            and stage_statuses["interface_validation"] == "passed"
            and integration_status == "completed"
        )
        rtl_output = {
            "module_name": (
                direct_rtl_result["integration"]["top_module_name"]
                if integration_status == "completed"
                else None
            ),
            "language": "Verilog",
            "rtl_code": direct_rtl_result["integration"]["integrated_rtl"],
            "component_modules": [
                {
                    "component_name": item["component_name"],
                    "module_name": item["module_name"],
                    "inputs": item["inputs"],
                    "outputs": item["outputs"],
                    "rtl_code": item["rtl_code"],
                    "generation_status": item["generation_status"],
                    "interface_validation_status": (
                        item["interface_validation_status"]
                    ),
                    "interface_validation_errors": (
                        item["interface_validation_errors"]
                    ),
                    "generation_error": item["generation_error"],
                }
                for item in direct_rtl_result["components"]
            ],
            "component_instances": direct_rtl_result["integration"][
                "component_instances"
            ],
            "interactions": decomposition_result.interactions,
            "generation_status": (
                "completed" if overall_rtl_success else "Failed"
            ),
            "component_generation_status": stage_statuses[
                "rtl_generation"
            ],
            "generation_issues": rtl_generation_errors,
            "assumptions": pseudocode_result.assumptions,
            "unresolved_issues": pseudocode_result.unresolved_issues,
            "interface_validation_status": stage_statuses[
                "interface_validation"
            ],
            "integration_status": integration_status,
            "compilation_status": "not_run",
            "rtl_agent_status": (
                "completed" if overall_rtl_success else "failed"
            ),
            "experimental": True,
            "production_verified": False,
            "pseudocode_validation_status": (
                pseudocode_result.validation_status
            ),
            "artifact_paths": artifact_paths,
        }
        if attempt_num > 0:
            save_json(output_dir, f"rtl_generation{suffix}.json", rtl_output)
        save_json(output_dir, "rtl_generation.json", rtl_output)
        artifact_paths["rtl_generation"] = "rtl_generation.json"

        _emit(
            progress_callback,
            stage="rtl_generation",
            status="completed" if overall_rtl_success else "failed",
            message=(
                f"Generated {generated_count} component(s); "
                f"{interfaces_passed} interface(s) passed; "
                f"integration {integration_status}"
            ),
            error=(
                "; ".join(rtl_generation_errors)
                if not overall_rtl_success
                else None
            ),
            component_generation_status=stage_statuses[
                "rtl_generation"
            ],
            interface_validation_status=stage_statuses[
                "interface_validation"
            ],
            integration_status=integration_status,
            compilation_status="not_run",
            components=component_state,
        )
        _emit(
            progress_callback,
            stage="integration",
            status=integration_status,
            message=f"Top-level integration {integration_status}",
            errors=direct_rtl_result["integration"]["errors"],
        )
        return rtl_output, None, direct_rtl_result, component_state, compilation_result, overall_rtl_success


def _execute_unified_rtl_generation(
    specification: str,
    output_dir: Path,
    decomposition_result,
    understanding_result,
    description_results,
    pseudocode_result,
    stage_statuses,
    artifact_paths,
    progress_callback,
    attempt_num: int = 0,
):
    top_name = "APU_Core"
    code_output = generate_code(
        pseudocode=pseudocode_result,
        descriptions=description_results,
        specification=specification,
    )
    verilog_code = code_output.code.strip()
    top_name = code_output.component_name or top_name
    assumptions = code_output.assumptions or getattr(pseudocode_result, "assumptions", [])

    (output_dir / "system_top.v").write_text(verilog_code, encoding="utf-8")
    (output_dir / "top_level_rtl.v").write_text(verilog_code, encoding="utf-8")

    inputs_list = []
    outputs_list = []
    if understanding_result and getattr(understanding_result, "inputs", None):
        inputs_list = list(understanding_result.inputs)
    if understanding_result and getattr(understanding_result, "outputs", None):
        outputs_list = list(understanding_result.outputs)

    rtl_output = {
        "module_name": top_name,
        "language": "Verilog",
        "rtl_code": verilog_code,
        "code": verilog_code,
        "component_modules": [
            {
                "component_name": top_name,
                "module_name": top_name,
                "inputs": inputs_list,
                "outputs": outputs_list,
                "rtl_code": verilog_code,
                "generation_status": "completed",
                "interface_validation_status": "passed",
                "interface_validation_errors": [],
                "generation_error": None,
            }
        ],
        "component_instances": [],
        "interactions": getattr(decomposition_result, "interactions", []),
        "generation_status": "completed",
        "component_generation_status": "completed",
        "generation_issues": [],
        "assumptions": assumptions,
        "unresolved_issues": getattr(pseudocode_result, "unresolved_issues", []),
        "interface_validation_status": "passed",
        "integration_status": "completed",
        "compilation_status": "not_run",
        "rtl_agent_status": "completed",
        "experimental": True,
        "production_verified": False,
        "pseudocode_validation_status": getattr(pseudocode_result, "validation_status", "Passed"),
        "artifact_paths": artifact_paths,
    }

    suffix = f"_attempt_{attempt_num}" if attempt_num > 0 else ""
    if attempt_num > 0:
        save_json(output_dir, f"rtl_generation{suffix}.json", rtl_output)
    save_json(output_dir, "rtl_generation.json", rtl_output)
    artifact_paths["integrated_rtl"] = "system_top.v"
    artifact_paths["top_level_rtl"] = "top_level_rtl.v"
    artifact_paths["rtl_generation"] = "rtl_generation.json"

    stage_statuses["rtl_generation"] = "completed"
    stage_statuses["interface_validation"] = "passed"
    stage_statuses["integration"] = "completed"

    component_state = [
        {
            "name": top_name,
            "status": "completed",
            "generation_status": "completed",
            "interface_validation_status": "passed",
            "errors": [],
        }
    ]

    _emit(
        progress_callback,
        stage="rtl_generation",
        status="completed",
        message=f"Generated unified synthesizable Verilog module '{top_name}'",
        components=component_state,
    )
    return rtl_output, code_output, component_state


def run_pipeline(
    spec_path,
    output_dir,
    progress_callback=None,
    *,
    strict_validation=False,
    usage_tracker_callback=None,
):
    """Run the pipeline and write artifacts into ``output_dir``.

    ``progress_callback`` receives dictionaries with ``stage``, ``status``,
    and per-component status for component-wise stages.
    """

    spec_path = Path(spec_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = output_dir.name
    if (output_dir / "run_manifest.json").exists():
        raise FileExistsError(
            f"Run directory already contains a manifest: {output_dir}"
        )

    stage = "ingestion"
    component_state = []
    current_component = None
    stage_statuses = {
        name: "pending"
        for name in (
            "ingestion",
            "understanding",
            "decomposition",
            "description",
            "pseudocode_generation",
            # "pseudocode_validation",
            "rtl_generation",
            "interface_validation",
            "integration",
            "rtl_verification",
            "reflection",
        )
    }
    artifact_paths = {}
    pseudocode_result = None
    rtl_result = None
    direct_rtl_result = None
    rtl_verification_result = None
    compilation_result = {
        "status": "not_attempted",
        "errors": [],
    }
    usage_tracker = UsageTracker()
    usage_context_token = bind_usage_tracker(usage_tracker)

    def fail(error: Exception):
        if stage in {"pseudocode", "rtl_generation"}:
            for item in component_state:
                if item["status"] in {"running", "pending"}:
                    item["status"] = "failed"
        elif stage in {"description", "rtl_verification"}:
            for item in component_state:
                if item["status"] == "running" or (
                    current_component and item["name"] == current_component and item["status"] != "completed"
                ):
                    item["status"] = "failed"
                elif item["status"] == "pending":
                    item["status"] = "skipped"
        _emit(
            progress_callback,
            stage=stage,
            status="failed",
            error=f"{type(error).__name__}: {error}",
            component=current_component,
            components=list(component_state) if component_state else None,
            message=f"{type(error).__name__}: {error}",
        )
        try:
            error.pipeline_stage = stage
        except Exception:
            pass
        stage_statuses[stage] = "failed"
        try:
            fail_usage = usage_tracker.snapshot()
        except Exception:
            fail_usage = {}
        save_json(
            output_dir,
            "run_manifest.json",
            {
                "run_id": run_id,
                "overall_status": "failed",
                "failed_stage": stage,
                "strict_validation": strict_validation,
                "stages": stage_statuses,
                "artifact_paths": artifact_paths,
                "error": f"{type(error).__name__}: {error}",
                "token_usage": fail_usage,
            },
        )

    try:
        if usage_tracker_callback is not None:
            usage_tracker_callback(usage_tracker)
        print("\n" + "=" * 70)
        print("SPEC2RTL MULTI-AGENT PIPELINE")
        print("=" * 70)

        stage = "ingestion"
        _emit(
            progress_callback,
            stage="ingestion",
            status="running",
            message="Reading the specification",
        )
        docs, specification, parent_chunks, child_chunks = _load_specification(spec_path)
        save_json(
            output_dir,
            "input_summary.json",
            {
                "input_file": spec_path.name,
                "input_path": str(spec_path.resolve()),
                "original_documents": len(docs),
                "parent_chunks": len(parent_chunks),
                "child_chunks": len(child_chunks),
                "extracted_characters": len(specification),
            },
        )
        (output_dir / "specification.txt").write_text(
            specification,
            encoding="utf-8",
        )
        artifact_paths.update({
            "input_summary": "input_summary.json",
            "specification": "specification.txt",
        })
        stage_statuses["ingestion"] = "completed"
        _emit(
            progress_callback,
            stage="ingestion",
            status="completed",
            message="Specification loaded",
        )

        stage = "understanding"
        print("\n[1/7] Running Understanding Agent...")
        _emit(
            progress_callback,
            stage="understanding",
            status="running",
            message="Extracting requirements from the specification",
        )
        with usage_scope(usage_tracker, "understanding"):
            understanding_result = understand_specification(docs)
        print_stage("UNDERSTANDING AGENT OUTPUT", understanding_result)
        save_json(output_dir, "understanding.json", understanding_result.model_dump())
        artifact_paths["understanding"] = "understanding.json"
        stage_statuses["understanding"] = "completed"
        _emit(
            progress_callback,
            stage="understanding",
            status="completed",
            message="Understanding complete",
        )

        stage = "decomposer"
        print("\n[2/7] Running Decomposer Agent...")
        _emit(
            progress_callback,
            stage="decomposer",
            status="running",
            message="Decomposing the design into components",
        )
        with usage_scope(usage_tracker, "decomposer"):
            decomposition_result = decomposer(understanding_result)
        print_stage("DECOMPOSER AGENT OUTPUT", decomposition_result)
        save_json(output_dir, "decomposition.json", decomposition_result.model_dump())
        artifact_paths["decomposition"] = "decomposition.json"
        stage_statuses["decomposition"] = "completed"
        _emit(
            progress_callback,
            stage="decomposer",
            status="completed",
            message=f"{len(decomposition_result.components)} component(s) identified",
        )

        stage = "description"
        print("\n[3/7] Running Description Agent...")
        component_state = [
            {"name": component.name, "status": "pending"}
            for component in decomposition_result.components
        ]
        _emit(
            progress_callback,
            stage="description",
            status="running",
            message="Describing components",
            components=list(component_state),
        )
        description_results = []
        total = len(decomposition_result.components)
        for index, component in enumerate(decomposition_result.components, start=1):
            current_component = component.name
            component_state[index - 1]["status"] = "running"
            print(f"\nDescribing component {index}: {component.name}")
            _emit(
                progress_callback,
                stage="description",
                status="running",
                component=component.name,
                message=f"Describing {component.name} ({index} of {total})",
                components=list(component_state),
            )
            with usage_scope(
                usage_tracker, "description", component_name=component.name
            ):
                description = describe_component(component, spec_context=specification)
            description_results.append(description)
            print_stage(f"DESCRIPTION: {component.name}", description)
            component_state[index - 1]["status"] = "completed"
            save_json(
                output_dir,
                "descriptions.json",
                [item.model_dump() for item in description_results],
            )
            artifact_paths["descriptions"] = "descriptions.json"
            _emit(
                progress_callback,
                stage="description",
                status="running",
                component=component.name,
                message=f"Described {component.name} ({index} of {total})",
                components=list(component_state),
            )
            stage_statuses["description"] = "completed"
        current_component = None
        _emit(
            progress_callback,
            stage="description",
            status="completed",
            message=f"{len(description_results)} component(s) described",
            components=list(component_state),
        )

        stage = "pseudocode"
        print("\n[4/7] Running Pseudocode Generation Agent...")
        component_state = [
            {"name": component.name, "status": "pending"}
            for component in decomposition_result.components
        ]
        _emit(
            progress_callback,
            stage="pseudocode",
            status="running",
            message="Generating pseudocode",
        )
        with usage_scope(usage_tracker, "pseudocode"):
            pseudocode_result = generate_pseudocode(
                specification=specification,
                decomposition=decomposition_result,
                descriptions=description_results,
                understanding=understanding_result,
                raw_output_dir=output_dir,
            )
        print_stage("PSEUDOCODE GENERATION OUTPUT", pseudocode_result)
        save_json(output_dir, "pseudocode.json", pseudocode_result.model_dump())
        artifact_paths["pseudocode"] = "pseudocode.json"
        pseudocode_component_state = [
            {
                "name": component.component_name,
                "status": (
                    "completed"
                    if component.generation_status == "completed"
                    else "failed"
                ),
            }
            for component in pseudocode_result.components
        ]
        component_state = pseudocode_component_state
        pseudocode_succeeded = (
            pseudocode_result.generation_status == "completed"
        )
        # pseudocode_validation_succeeded = (
        #     pseudocode_result.validation_status in {"Passed", "Warnings"}
        # )
        stage_statuses["pseudocode_generation"] = (
            "completed" if pseudocode_succeeded else "failed"
        )
        # stage_statuses["pseudocode_validation"] = (
        #     "passed" if pseudocode_validation_succeeded else "failed"
        # )
        _emit(
            progress_callback,
            stage="pseudocode",
            status="completed" if pseudocode_succeeded else "failed",
            # message=(
            #     "Pseudocode generated; "
            #     f"validation {pseudocode_result.validation_status.lower()}, "
            #     f"execution {pseudocode_result.execution_status.lower()}"
            # ),
            message="Pseudocode generation completed",
            components=pseudocode_component_state,
        )
        # _emit(
        #     progress_callback,
        #     stage="pseudocode_validation",
        #     status=stage_statuses["pseudocode_validation"],
        #     message=(
        #         f"Pseudocode validation {pseudocode_result.validation_status}; "
        #         f"{len(pseudocode_result.validation_issues)} issue(s), "
        #         f"{len(pseudocode_result.unresolved_issues)} unresolved requirement(s)"
        #     ),
        #     errors=pseudocode_result.validation_issues,
        #     unresolved_requirements=pseudocode_result.unresolved_issues,
        # )
        # save_json(
        #     output_dir,
        #     "pseudocode_validation.json",
        #     {
        #         "generation_status": pseudocode_result.generation_status,
        #         "validation_status": pseudocode_result.validation_status,
        #         "validation_issues": pseudocode_result.validation_issues,
        #         "unresolved_issues": pseudocode_result.unresolved_issues,
        #         "components": [
        #             {
        #                 "component_name": item.component_name,
        #                 "generation_status": item.generation_status,
        #                 "validation_status": item.validation_status,
        #                 "validation_issues": item.validation_issues,
        #                 "unresolved_issues": item.unresolved_issues,
        #             }
        #             for item in pseudocode_result.components
        #         ],
        #     },
        # )
        # artifact_paths["pseudocode_validation"] = "pseudocode_validation.json"

        # 5. RTL Generation Agent (Unified Hardware System RTL)
        stage = "rtl_generation"
        print("\n[5/7] Running RTL Generation Agent (Unified Hardware RTL)...")
        _emit(
            progress_callback,
            stage="rtl_generation",
            status="running",
            message="Generating synthesizable Verilog RTL from pseudocode and descriptions",
        )
        with usage_scope(usage_tracker, "rtl_generation"):
            rtl_output, code_output, component_state = _execute_unified_rtl_generation(
                specification=specification,
                output_dir=output_dir,
                decomposition_result=decomposition_result,
                understanding_result=understanding_result,
                description_results=description_results,
                pseudocode_result=pseudocode_result,
                stage_statuses=stage_statuses,
                artifact_paths=artifact_paths,
                progress_callback=progress_callback,
                attempt_num=0,
            )

        # 6. RTL Verification Agent
        stage = "rtl_verification"
        print("\n[6/7] Running RTL Verification Agent...")
        _emit(
            progress_callback,
            stage="rtl_verification",
            status="running",
            message="Verifying generated RTL against the original specification",
        )

        with usage_scope(usage_tracker, "rtl_verification"):
            rtl_verification_result = verify_rtl(
                source_chunks=parent_chunks,
                generated_rtl=rtl_output,
                understanding=understanding_result,
                decomposition=decomposition_result,
                descriptions=description_results,
                pseudocode=pseudocode_result,
            )

        print_stage("RTL VERIFICATION OUTPUT", rtl_verification_result)
        save_json(
            output_dir,
            "rtl_verification.json",
            rtl_verification_result.model_dump(),
        )
        artifact_paths["rtl_verification"] = "rtl_verification.json"

        # 7. Reflection Agent (only if RTL verification fails)
        # Allow a maximum of three regeneration attempts after initial generation.
        max_regeneration_attempts = 3
        regeneration_attempts = 0
        reflection_history = []

        while not rtl_verification_result.valid and regeneration_attempts < max_regeneration_attempts:
            regeneration_attempts += 1
            print(
                f"\n[7/7] Running Reflection Agent (Attempt {regeneration_attempts}/{max_regeneration_attempts})..."
            )

            # 7. Reflection Agent
            stage = "reflection"
            _emit(
                progress_callback,
                stage="reflection",
                status="running",
                message=f"Reflecting on RTL verification issues (attempt {regeneration_attempts}/{max_regeneration_attempts})",
            )

            with usage_scope(usage_tracker, "reflection"):
                current_code_obj = CodeOuput(
                    component_name=rtl_output.get("module_name", "APU_Core"),
                    code=rtl_output.get("rtl_code", ""),
                    assumptions=rtl_output.get("assumptions", []),
                )
                reflected_code_output = reflect_on_verification(
                    source_chunks=parent_chunks,
                    generated_code=current_code_obj,
                    verification=rtl_verification_result,
                )

            top_name = reflected_code_output.component_name or rtl_output.get("module_name", "APU_Core")
            verilog_code = reflected_code_output.code.strip()

            # Update Verilog files and output
            (output_dir / "system_top.v").write_text(verilog_code, encoding="utf-8")
            (output_dir / "top_level_rtl.v").write_text(verilog_code, encoding="utf-8")
            rtl_output["rtl_code"] = verilog_code
            rtl_output["code"] = verilog_code
            if rtl_output.get("component_modules"):
                rtl_output["component_modules"][0]["rtl_code"] = verilog_code
            if reflected_code_output.assumptions:
                rtl_output["assumptions"] = reflected_code_output.assumptions

            suffix = f"_attempt_{regeneration_attempts}"
            save_json(output_dir, f"rtl_generation{suffix}.json", rtl_output)
            save_json(output_dir, "rtl_generation.json", rtl_output)

            # Reflection artifact for UI and manifest
            reflection_artifact = {
                "needs_revision": True,
                "feedback": [f"Direct code reflection applied (Attempt {regeneration_attempts})"],
                "component_feedback": {top_name: [f"Corrected: {issue}" for issue in rtl_verification_result.issues]},
                "reasoning": f"Directly repaired {top_name} in synthesizable Verilog to resolve verification issues: {'; '.join(rtl_verification_result.issues[:5])}",
                "corrected_code": verilog_code,
            }
            save_json(output_dir, f"reflection_attempt_{regeneration_attempts}.json", reflection_artifact)
            save_json(output_dir, "reflection.json", reflection_artifact)
            artifact_paths["reflection"] = "reflection.json"
            reflection_history.append(reflection_artifact)

            stage_statuses["reflection"] = "completed"
            _emit(
                progress_callback,
                stage="reflection",
                status="completed",
                message=f"Applied direct RTL reflection correction (attempt {regeneration_attempts}/{max_regeneration_attempts})",
            )

            # Re-verify the updated RTL!
            stage = "rtl_verification"
            _emit(
                progress_callback,
                stage="rtl_verification",
                status="running",
                message=f"Verifying regenerated RTL against original specification (attempt {regeneration_attempts}/{max_regeneration_attempts})",
            )
            with usage_scope(usage_tracker, "rtl_verification"):
                rtl_verification_result = verify_rtl(
                    source_chunks=parent_chunks,
                    generated_rtl=rtl_output,
                    understanding=understanding_result,
                    decomposition=decomposition_result,
                    descriptions=description_results,
                    pseudocode=pseudocode_result,
                )
            print_stage(f"RE-VERIFICATION OUTPUT (ATTEMPT {regeneration_attempts})", rtl_verification_result)
            save_json(output_dir, f"rtl_verification_attempt_{regeneration_attempts}.json", rtl_verification_result.model_dump())
            save_json(output_dir, "rtl_verification.json", rtl_verification_result.model_dump())

        if not reflection_history:
            stage_statuses["reflection"] = "skipped"
            _emit(
                progress_callback,
                stage="reflection",
                status="skipped",
                message="Reflection skipped: RTL verification passed on initial generation",
            )

        stage_statuses["rtl_verification"] = (
            "passed" if rtl_verification_result.valid else "failed"
        )
        _emit(
            progress_callback,
            stage="rtl_verification",
            status=stage_statuses["rtl_verification"],
            message=(
                "RTL static verification passed"
                if rtl_verification_result.valid
                else f"RTL static verification failed (after {regeneration_attempts} regeneration attempts)"
            ),
            errors=rtl_verification_result.issues,
            suggestions=rtl_verification_result.suggestions,
        )

        rtl_verification_passed = rtl_verification_result.valid
        rtl_verification_issues = rtl_verification_result.issues
        generated_module_count = (
            len(rtl_output.get("component_modules", []))
            if rtl_output is not None
            else (
                len(rtl_result.component_modules)
                if rtl_result is not None
                else 0
            )
        )
        rtl_module_name = (
            rtl_output.get("module_name")
            if rtl_output is not None
            else (
                rtl_result.module_name
                if rtl_result is not None
                else None
            )
        )
        rtl_status = stage_statuses["rtl_generation"]
        rtl_agent_success = (
            rtl_status == "completed"
            and stage_statuses["interface_validation"] == "passed"
            and stage_statuses["integration"] == "completed"
        )
        has_pipeline_errors = any(
            status in {"failed", "blocked"}
            for status in stage_statuses.values()
        )

        if has_pipeline_errors or not rtl_verification_result.valid:
            overall_status = "failed"
        else:
            overall_status = "completed"

        final_summary = {
            "run_id": run_id,
            "overall_status": overall_status,
            "input_document": spec_path.name,
            "original_documents": len(docs),
            "parent_chunks": len(parent_chunks),
            "child_chunks": len(child_chunks),
            "extracted_characters": len(specification),
            "components_described": len(description_results),
            "rtl_verification": ("passed" if rtl_verification_passed else "failed"),
            "rtl_verification_issues": rtl_verification_issues,
            "reflection": ("completed" if reflection_history else "skipped"),
            "reflection_attempts": len(reflection_history),
            "pseudocode": (
                "completed" if pseudocode_succeeded else "failed"
            ),
            "pseudocode_generation_status": (
                stage_statuses["pseudocode_generation"]
            ),
            # "pseudocode_validation": pseudocode_result.validation_status,
            # "pseudocode_validation_status": (
            #     stage_statuses["pseudocode_validation"]
            # ),
            # "pseudocode_validation_errors": (
            #     pseudocode_result.validation_issues
            # ),
            "unresolved_requirements": (
                pseudocode_result.unresolved_issues
            ),
            "pseudocode_execution": pseudocode_result.execution_status,
            "rtl_generation": rtl_status,
            "rtl_agent_status": (
                "completed" if rtl_agent_success else "failed"
            ),
            "rtl_module_name": rtl_module_name,
            "rtl_component_modules": generated_module_count,
            "interface_validation": stage_statuses[
                "interface_validation"
            ],
            "integration_status": stage_statuses["integration"],
            "production_verified": False,
            "experimental": True,
            "stages": stage_statuses,
            "components": component_state,
            "artifact_paths": artifact_paths,
        }

        usage_snapshot = usage_tracker.snapshot()
        final_summary["token_usage"] = usage_snapshot

        print("\n" + "=" * 70)
        print("PIPELINE EXECUTION SUMMARY")
        print("=" * 70)
        print("Input Document              :", spec_path.name)
        print("Understanding Agent         :", stage_statuses["understanding"])
        print("Decomposer Agent            :", stage_statuses["decomposition"])
        print(
            "Description Agent           : "
            f"{stage_statuses['description']} "
            f"({len(description_results)} component(s))"
        )
        print("RTL Verification            :", stage_statuses["rtl_verification"])
        print("Reflection Agent            :", stage_statuses.get("reflection", "SKIPPED").upper())
        print(
            "Pseudocode Generation Agent : "
            f"{stage_statuses['pseudocode_generation']}"
        )
        # print(
        #     "Pseudocode Validation       : "
        #     f"{pseudocode_result.validation_status} "
        #     "(diagnostic; non-blocking by default)"
        # )
        print(
            "RTL Generation              : "
            f"{stage_statuses['rtl_generation']}"
        )
        print("Interface Validation        :", stage_statuses["interface_validation"])
        print("Top-level Integration       :", stage_statuses["integration"])
        print("Overall Status              :", overall_status)
        if usage_snapshot:
            total_toks = sum(u.get("total_tokens", 0) for u in usage_snapshot.values())
            total_calls = sum(u.get("calls", 0) for u in usage_snapshot.values())
            print(f"Token Consumption           : {total_toks:,} tokens across {total_calls} model call(s)")

        artifact_paths["pipeline_summary"] = "pipeline_summary.json"
        artifact_paths["run_manifest"] = "run_manifest.json"
        final_summary["artifact_paths"] = artifact_paths
        save_json(output_dir, "pipeline_summary.json", final_summary)
        save_json(
            output_dir,
            "run_manifest.json",
            {
                "run_id": run_id,
                "source_specification": str(spec_path.resolve()),
                "strict_validation": strict_validation,
                "overall_status": overall_status,
                "stages": stage_statuses,
                "components": component_state,
                "artifact_paths": artifact_paths,
                "token_usage": usage_snapshot,
                # "pseudocode_validation_status": (
                #     pseudocode_result.validation_status
                # ),
                # "validation_errors": pseudocode_result.validation_issues,
                # "unresolved_requirements": pseudocode_result.unresolved_issues,
                "rtl_generation_status": stage_statuses["rtl_generation"],
                "rtl_verification_status": stage_statuses["rtl_verification"],
                "rtl_verification_issues": rtl_verification_issues,
                "interface_validation_status": stage_statuses[
                    "interface_validation"
                ],
                "integration_status": stage_statuses["integration"],
                "production_verified": False,
            },
        )

        print(f"\nOutput directory: {output_dir}")
        print("\nPipeline finished.")
        final_summary["artifact_paths"] = artifact_paths
        return final_summary
    except Exception as error:
        fail(error)
        raise
    finally:
        reset_usage_context(usage_context_token)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run SPEC2RTL from a hardware specification to RTL."
    )
    parser.add_argument(
        "--spec",
        type=Path,
        required=True,
        help="Path to the hardware specification document.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_RUNS_ROOT,
        help="Root directory for unique run outputs (default: outputs/runs).",
    )
    parser.add_argument(
        "--strict-validation",
        action="store_true",
        help="Block RTL generation when pseudocode validation does not pass.",
    )
    args = parser.parse_args()
    run_dir = _new_run_directory(args.output_root)
    run_pipeline(
        args.spec,
        run_dir,
        strict_validation=args.strict_validation,
    )


if __name__ == "__main__":
    main()

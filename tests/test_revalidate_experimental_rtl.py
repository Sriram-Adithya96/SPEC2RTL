import json
from pathlib import Path

from src import revalidate_experimental_rtl
from src.agents import rtl_generation


EXPERIMENTAL_LABEL = "EXPERIMENTAL — NOT PRODUCTION VERIFIED"


def _json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def _rtl_response(module, inputs, outputs, *, wrong_width=False):
    ports = []
    for direction, signal in [
        *(("input", item) for item in inputs),
        *(("output", item) for item in outputs),
    ]:
        name, _, width = signal.partition("[")
        width = f"[{width}" if width else ""
        if wrong_width and direction == "input" and name == "stream_in":
            width = "[6:0]"
        ports.append(f"{direction} wire {width} {name}".strip())
    return json.dumps({
        "module_name": module,
        "language": "Verilog",
        "rtl_code": f"module {module} ({', '.join(ports)});\nendmodule\n",
        "assumptions": [],
        "unresolved_issues": [f"Draft uncertainty for {module}."],
    })


def _source_run(tmp_path, *, wrong_width_component=None):
    source_run = tmp_path / "source-run"
    raw_dir = source_run / "raw"
    raw_dir.mkdir(parents=True)
    component_data = [
        ("PacketScanner", ["stream_in"], ["byte_out"]),
        ("FrameMarker", ["byte_in"], ["frame_out"]),
    ]
    manifest_components = []
    for index, (name, inputs, outputs) in enumerate(component_data, start=1):
        filename = f"rtl_generation_raw_{index:03d}-{name}.txt"
        (raw_dir / filename).write_text(
            _rtl_response(
                name,
                inputs,
                outputs,
                wrong_width=name == wrong_width_component,
            ),
            encoding="utf-8",
        )
        manifest_components.append({
            "component_name": name,
            "module_name": name,
            "raw_response_path": f"raw/{filename}",
            "generation_status": "Failed",
        })
    _json(source_run / "manifest.json", {
        "label": EXPERIMENTAL_LABEL,
        "production_verified": False,
        "components": manifest_components,
    })
    return source_run


def _artifacts(tmp_path):
    artifacts = tmp_path / "diagnostic"
    components = [
        {
            "name": "PacketScanner",
            "purpose": "Scans a stream.",
            "inputs": ["stream_in"],
            "outputs": ["byte_out"],
        },
        {
            "name": "FrameMarker",
            "purpose": "Marks a frame.",
            "inputs": ["byte_in"],
            "outputs": ["frame_out"],
        },
    ]
    _json(artifacts / "understanding.json", {
        "system_purpose": "Processes a stream.",
        "major_components": ["PacketScanner", "FrameMarker"],
        "inputs": ["stream_in"],
        "outputs": ["frame_out"],
        "functional_requirements": ["Pass through the stream."],
        "constraints": [],
        "ambiguities": [],
    })
    _json(artifacts / "decomposition.json", {
        "components": components,
        "interactions": [
            "PacketScanner byte_out -> FrameMarker byte_in",
        ],
        "implementation_plan": [],
    })
    validation_issue = {
        "severity": "error",
        "code": "UNRESOLVED_TEST",
        "message": "Example validation error retained for audit.",
    }
    component_pseudocode = [
        {
            "component_name": item["name"],
            "module_name": item["name"],
            "inputs": item["inputs"],
            "outputs": item["outputs"],
            "pseudocode": [f"MODULE {item['name']}", "END MODULE"],
            "assumptions": [],
            "unresolved_issues": [f"Unresolved {item['name']} behavior."],
            "generation_status": "completed",
            "validation_status": "Failed",
            "validation_issues": [validation_issue],
        }
        for item in components
    ]
    _json(artifacts / "pseudocode.json", {
        "components": component_pseudocode,
        "assumptions": [],
        "unresolved_issues": ["Unresolved system behavior."],
        "generation_status": "completed",
        "validation_status": "Failed",
        "validation_issues": [validation_issue],
        "execution_status": "not_attempted",
        "execution_output": "Not run.",
        "execution_errors": [],
    })
    return artifacts, validation_issue


def test_revalidates_saved_responses_without_llm_and_preserves_source(
    tmp_path, monkeypatch
):
    source_run = _source_run(tmp_path)
    artifacts, validation_issue = _artifacts(tmp_path)
    source_before = {
        path: path.read_bytes()
        for path in source_run.rglob("*")
        if path.is_file()
    }
    monkeypatch.setattr(
        rtl_generation,
        "get_llm",
        lambda _agent: (_ for _ in ()).throw(
            AssertionError("Revalidation must not request an LLM.")
        ),
    )

    result = revalidate_experimental_rtl.revalidate_saved_run(
        source_run,
        artifacts,
        output_root=tmp_path / "experimental-runs",
    )

    assert result["label"] == EXPERIMENTAL_LABEL
    assert result["production_verified"] is False
    assert result["generation_status"] == "completed"
    assert result["integration"]["status"] == "completed"
    assert [item["validation_status"] for item in result["components"]] == [
        "passed",
        "passed",
    ]
    assert result["components"][0]["rtl_response_unresolved_issues"] == [
        "Draft uncertainty for PacketScanner."
    ]
    assert result["pseudocode"]["validation_issues"] == [validation_issue]
    assert result["pseudocode"]["unresolved_issues"] == [
        "Unresolved system behavior."
    ]
    output_dir = Path(result["output_directory"])
    assert output_dir.name.startswith("revalidation-")
    assert (output_dir / "revalidation_manifest.json").is_file()
    assert all(
        (output_dir / component["rtl_path"]).is_file()
        and (output_dir / component["raw_response_path"]).is_file()
        for component in result["components"]
    )
    assert all(path.read_bytes() == data for path, data in source_before.items())


def test_keeps_successful_components_and_skips_integration_on_component_failure(
    tmp_path,
):
    source_run = _source_run(
        tmp_path,
        wrong_width_component="PacketScanner",
    )
    artifacts, _validation_issue = _artifacts(tmp_path)

    result = revalidate_experimental_rtl.revalidate_saved_run(
        source_run,
        artifacts,
        output_root=tmp_path / "experimental-runs",
    )

    assert result["generation_status"] == "failed"
    assert result["integration"]["status"] == "not_attempted"
    assert "skipped" in result["integration"]["errors"][0]
    failed, passed = result["components"]
    assert failed["validation_status"] == "failed"
    assert failed["validation_errors"]
    assert passed["validation_status"] == "passed"
    assert passed["rtl_path"]
    output_dir = Path(result["output_directory"])
    assert (output_dir / passed["rtl_path"]).is_file()

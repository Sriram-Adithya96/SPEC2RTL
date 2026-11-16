import json
from pathlib import Path
from types import SimpleNamespace

from src import experimental_rtl_generation
from src.agents import rtl_generation
from src.schemas import (
    Component,
    ComponentPseudocodeOutput,
    DecompositionOutput,
    DescriptionOutput,
    PseudocodeGenerationOutput,
    Understanding,
)


def _fixtures(interactions=None):
    components = [
        Component(
            name="PacketScanner",
            purpose="Scans an incoming packet stream.",
            inputs=["stream_in"],
            outputs=["byte_out"],
        ),
        Component(
            name="FrameMarker",
            purpose="Marks the end of a frame.",
            inputs=["byte_in"],
            outputs=["frame_out"],
        ),
    ]
    decomposition = DecompositionOutput(
        components=components,
        interactions=(
            interactions
            if interactions is not None
            else ["PacketScanner byte_out -> FrameMarker byte_in"]
        ),
        implementation_plan=[],
    )
    understanding = Understanding(
        system_purpose="Processes a packet stream.",
        major_components=["PacketScanner", "FrameMarker"],
        inputs=["stream_in"],
        outputs=["frame_out"],
        functional_requirements=["Propagate the packet stream."],
        constraints=[],
        ambiguities=[],
    )
    descriptions = [
        DescriptionOutput(
            module_name=component.name,
            purpose=component.purpose,
            inputs=[],
            outputs=[],
            state_elements=[],
            constraints=[],
            behavior=[f"Behavior context for {component.name}."],
            spec_references=[],
        )
        for component in components
    ]
    issue = {
        "severity": "error",
        "code": "AMBIGUOUS_BEHAVIOR",
        "message": "The treatment of a partial frame is unspecified.",
    }
    component_pseudocode = [
        ComponentPseudocodeOutput(
            component_name=component.name,
            module_name=component.name,
            inputs=component.inputs,
            outputs=component.outputs,
            pseudocode=[f"MODULE {component.name}", "END MODULE"],
            assumptions=[],
            unresolved_issues=[f"Unresolved behavior for {component.name}."],
            generation_status="completed",
            validation_status="Failed",
            validation_issues=[issue],
        )
        for component in components
    ]
    pseudocode = PseudocodeGenerationOutput(
        components=component_pseudocode,
        generation_status="completed",
        validation_status="Failed",
        validation_issues=[issue],
        unresolved_issues=["The frame boundary behavior is unclear."],
    )
    return decomposition, understanding, descriptions, pseudocode, issue


def _rtl_response(module_name, inputs, outputs, unresolved_issues=None):
    ports = inputs + outputs
    lines = [
        f"module {module_name} ({', '.join(ports)});",
        *(f"input {name};" for name in inputs),
        *(f"output {name};" for name in outputs),
    ]
    if inputs and outputs:
        lines.append(f"assign {outputs[0]} = {inputs[0]};")
    lines.append("endmodule")
    return json.dumps({
        "module_name": module_name,
        "language": "Verilog",
        "rtl_code": "\n".join(lines),
        "assumptions": [],
        "unresolved_issues": unresolved_issues or [],
    })


class _FakeLLM:
    def __init__(self, response_by_module):
        self.response_by_module = response_by_module
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        module_name = next(
            name for name in self.response_by_module if f"'{name}'" in prompt
        )
        return SimpleNamespace(
            content=self.response_by_module[module_name]
        )


def _fake_responses(unresolved_by_module=None):
    unresolved_by_module = unresolved_by_module or {}
    return {
        "PacketScanner": _rtl_response(
            "PacketScanner",
            ["stream_in"],
            ["byte_out"],
            unresolved_by_module.get("PacketScanner"),
        ),
        "FrameMarker": _rtl_response(
            "FrameMarker",
            ["byte_in"],
            ["frame_out"],
            unresolved_by_module.get("FrameMarker"),
        ),
    }


def test_generates_dynamic_components_with_failed_pseudocode_and_isolates_outputs(
    tmp_path, monkeypatch
):
    decomposition, understanding, descriptions, pseudocode, issue = _fixtures()
    fake_llm = _FakeLLM(_fake_responses({
        "PacketScanner": ["RTL draft cannot resolve frame treatment."],
    }))
    monkeypatch.setattr(
        experimental_rtl_generation,
        "get_llm",
        lambda _agent: fake_llm,
    )
    output_root = tmp_path / "outputs" / "experimental-runs"
    production_file = tmp_path / "outputs" / "rtl_generation.json"
    production_file.parent.mkdir(parents=True)
    production_file.write_text("production artifact", encoding="utf-8")

    result = experimental_rtl_generation.run_experimental_rtl_generation(
        "Generic packet-processing specification.",
        decomposition,
        understanding,
        descriptions,
        pseudocode,
        output_root=output_root,
    )

    assert result["label"] == (
        "EXPERIMENTAL — PSEUDOCODE VALIDATION NOT PASSED — "
        "NOT PRODUCTION VERIFIED"
    )
    assert result["production_verified"] is False
    assert result["pseudocode"]["validation_issues"] == [issue]
    assert result["pseudocode"]["unresolved_issues"] == [
        "The frame boundary behavior is unclear."
    ]
    assert [item["component_name"] for item in result["components"]] == [
        "PacketScanner",
        "FrameMarker",
    ]
    assert all(
        item["generation_status"] == "completed"
        for item in result["components"]
    )
    assert all(
        item["source_pseudocode"][0]["validation_issues"] == [issue]
        and item["source_pseudocode"][0]["unresolved_issues"]
        for item in result["components"]
    )
    assert result["components"][0]["rtl_response_unresolved_issues"] == [
        "RTL draft cannot resolve frame treatment."
    ]
    assert result["integration"]["status"] == "completed"
    assert len(fake_llm.prompts) == 2
    assert all("NOT VALIDATED" in prompt for prompt in fake_llm.prompts)
    assert all(
        "report any unresolved source requirements" in prompt
        for prompt in fake_llm.prompts
    )
    assert all(
        "COMPONENT DESCRIPTION (SUPPORTING CONTEXT)" in prompt
        and "Behavior context for" in prompt
        and "SUPPLIED COMPONENT PSEUDOCODE (NOT VALIDATED)" in prompt
        for prompt in fake_llm.prompts
    )
    assert all(
        item["rtl_path"]
        and (Path(result["run_directory"]) / item["rtl_path"]).is_file()
        for item in result["components"]
    )
    run_directory = Path(result["run_directory"])
    assert (run_directory / "manifest.json").is_file()
    assert (run_directory / "pseudocode_validation.json").is_file()
    assert (run_directory / "generation_summary.json").is_file()
    assert result["summary"]["pseudocode_validation_status"] == "Failed"
    assert result["summary"]["components_generated"] == 2
    assert result["summary"]["components_interface_validated"] == 2
    assert result["summary"]["compilation_status"] == "not_run"
    assert result["summary"]["overall_experimental_status"] == (
        "completed_unverified"
    )
    assert all(
        item["raw_response_path"]
        and (run_directory / item["raw_response_path"]).is_file()
        for item in result["components"]
    )
    assert all(
        run_directory in path.parents
        for path in run_directory.rglob("*")
        if path.is_file()
    )
    assert production_file.read_text(encoding="utf-8") == "production artifact"


def test_integration_failure_keeps_generated_component_rtl(
    tmp_path, monkeypatch
):
    decomposition, understanding, descriptions, pseudocode, _issue = _fixtures(
        interactions=["MissingSource result -> FrameMarker byte_in"]
    )
    fake_llm = _FakeLLM(_fake_responses())
    monkeypatch.setattr(
        experimental_rtl_generation,
        "get_llm",
        lambda _agent: fake_llm,
    )

    result = experimental_rtl_generation.run_experimental_rtl_generation(
        "An arbitrary hardware specification.",
        decomposition,
        understanding,
        descriptions,
        pseudocode,
        output_root=tmp_path / "experimental-runs",
    )

    assert result["generation_status"] == "completed"
    assert result["integration"]["status"] == "failed"
    assert result["integration"]["errors"]
    assert all(item["rtl_code"] for item in result["components"])
    assert all(
        (Path(result["run_directory"]) / item["rtl_path"]).is_file()
        for item in result["components"]
    )


def test_reports_component_rtl_generation_failure(
    tmp_path, monkeypatch
):
    decomposition, understanding, descriptions, pseudocode, _issue = _fixtures()
    responses = _fake_responses()
    responses["PacketScanner"] = "not valid JSON"
    monkeypatch.setattr(
        experimental_rtl_generation,
        "get_llm",
        lambda _agent: _FakeLLM(responses),
    )

    result = experimental_rtl_generation.run_experimental_rtl_generation(
        "Specification.",
        decomposition,
        understanding,
        descriptions,
        pseudocode,
        output_root=tmp_path / "experimental-runs",
    )

    failed, generated = result["components"]
    assert result["generation_status"] == "failed"
    assert failed["generation_status"] == "failed"
    assert failed["generation_error"]
    assert failed["interface_validation_status"] == "not_run"
    assert generated["generation_status"] == "completed"
    assert generated["interface_validation_status"] == "passed"
    assert result["integration"]["status"] == "not_attempted"
    assert (
        result["summary"]["overall_experimental_status"]
        == "component_generation_failed"
    )


def test_reports_interface_validation_failure_separately(
    tmp_path, monkeypatch
):
    decomposition, understanding, descriptions, pseudocode, _issue = _fixtures()
    responses = _fake_responses()
    responses["PacketScanner"] = _rtl_response(
        "PacketScanner",
        [],
        ["byte_out"],
    )
    monkeypatch.setattr(
        experimental_rtl_generation,
        "get_llm",
        lambda _agent: _FakeLLM(responses),
    )

    result = experimental_rtl_generation.run_experimental_rtl_generation(
        "Specification.",
        decomposition,
        understanding,
        descriptions,
        pseudocode,
        output_root=tmp_path / "experimental-runs",
    )

    failed, passed = result["components"]
    assert failed["generation_status"] == "completed"
    assert failed["interface_validation_status"] == "failed"
    assert failed["interface_validation_errors"]
    assert failed["rtl_path"]
    assert (Path(result["run_directory"]) / failed["rtl_path"]).is_file()
    assert passed["interface_validation_status"] == "passed"
    assert result["integration"]["status"] == "not_attempted"
    assert (
        result["summary"]["overall_experimental_status"]
        == "component_interface_validation_failed"
    )


def test_each_invocation_uses_a_new_run_directory(tmp_path, monkeypatch):
    decomposition, understanding, descriptions, pseudocode, _issue = _fixtures()
    monkeypatch.setattr(
        experimental_rtl_generation,
        "get_llm",
        lambda _agent: _FakeLLM(_fake_responses()),
    )

    first = experimental_rtl_generation.run_experimental_rtl_generation(
        "Specification.",
        decomposition,
        understanding,
        descriptions,
        pseudocode,
        output_root=tmp_path / "experimental-runs",
    )
    second = experimental_rtl_generation.run_experimental_rtl_generation(
        "Specification.",
        decomposition,
        understanding,
        descriptions,
        pseudocode,
        output_root=tmp_path / "experimental-runs",
    )

    assert first["run_id"] != second["run_id"]
    assert Path(first["run_directory"]) != Path(second["run_directory"])


def test_production_validation_gate_still_blocks_invalid_pseudocode(
    monkeypatch, tmp_path
):
    decomposition, understanding, _descriptions, pseudocode, _issue = _fixtures()
    llm_calls = []
    monkeypatch.setattr(
        rtl_generation,
        "get_llm",
        lambda _agent: llm_calls.append(_agent),
    )

    result = rtl_generation.generate_rtl(
        "Generic specification.",
        pseudocode,
        decomposition=decomposition,
        understanding=understanding,
        raw_output_dir=tmp_path,
    )

    assert result.generation_status == "Failed"
    assert result.component_modules
    assert all(
        module.generation_status == "blocked"
        for module in result.component_modules
    )
    assert llm_calls == []


def test_loads_all_saved_artifacts_including_descriptions(tmp_path):
    decomposition, understanding, descriptions, pseudocode, _issue = _fixtures()
    (tmp_path / "understanding.json").write_text(
        json.dumps(understanding.model_dump()),
        encoding="utf-8",
    )
    (tmp_path / "decomposition.json").write_text(
        json.dumps(decomposition.model_dump()),
        encoding="utf-8",
    )
    (tmp_path / "descriptions.json").write_text(
        json.dumps([item.model_dump() for item in descriptions]),
        encoding="utf-8",
    )
    (tmp_path / "pseudocode.json").write_text(
        json.dumps(pseudocode.model_dump()),
        encoding="utf-8",
    )

    loaded_understanding, loaded_decomposition, loaded_descriptions, loaded_pseudocode = (
        experimental_rtl_generation._load_artifacts(tmp_path)
    )

    assert loaded_understanding == understanding
    assert loaded_decomposition == decomposition
    assert loaded_descriptions == descriptions
    assert loaded_pseudocode == pseudocode

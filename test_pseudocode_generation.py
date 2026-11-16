import json
import re
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.agents.decomposer import decomposer
from src.agents.description import align_interface_with_decomposer
from src.agents.pseudocode import (
    _component_ambiguities,
    _decomposition_interaction_issues,
    _observable_datapath_default_issues,
    generate_pseudocode,
)
from src.agents.rtl_generation import (
    _build_top_level_rtl,
    generate_rtl,
)
from src.pipeline import run_pipeline
from src.schemas import (
    Component,
    ComponentPseudocodeOutput,
    ComponentRTLModuleOutput,
    DecompositionOutput,
    DescriptionOutput,
    RTLGenerationOutput,
    Signal,
    PseudocodeGenerationOutput,
    Understanding,
    VerificationResult,
)


class TestPseudocodeGeneration(unittest.TestCase):
    def _pipeline_inputs(self):
        specification = "A pass-through design with input source and output result."
        understanding = Understanding(
            system_purpose="A pass-through design.",
            major_components=["passer"],
            inputs=["source"],
            outputs=["result"],
            functional_requirements=[],
            constraints=[],
            ambiguities=[],
        )
        decomposition = DecompositionOutput(
            components=[
                Component(
                    name="passer",
                    purpose="Pass the input through.",
                    inputs=["source"],
                    outputs=["result"],
                )
            ],
            interactions=[],
            implementation_plan=[],
        )
        description = DescriptionOutput(
            module_name="passer",
            purpose="Pass the input through.",
            inputs=[
                Signal(
                    name="source",
                    direction="input",
                    width="1",
                    description="Input signal.",
                )
            ],
            outputs=[
                Signal(
                    name="result",
                    direction="output",
                    width="1",
                    description="Output signal.",
                )
            ],
            state_elements=[],
            constraints=[],
            behavior=[],
            spec_references=[],
        )
        pseudocode = PseudocodeGenerationOutput(
            components=[
                ComponentPseudocodeOutput(
                    component_name="passer",
                    module_name="passer",
                    inputs=["source"],
                    outputs=["result"],
                    pseudocode=["MODULE passer", "END MODULE"],
                    assumptions=[],
                    unresolved_issues=[],
                    validation_status="Passed",
                )
            ],
            validation_status="Passed",
        )
        return specification, understanding, decomposition, description, pseudocode

    def _patch_pipeline(self, progress_events, rtl_result):
        (
            specification,
            understanding,
            decomposition,
            description,
            pseudocode,
        ) = self._pipeline_inputs()
        rtl_calls = []

        def fake_experimental_rtl(**kwargs):
            rtl_calls.append(kwargs)
            run_dir = Path(kwargs["output_root"]) / "synthetic-run"
            run_dir.mkdir(parents=True, exist_ok=True)
            completed = rtl_result.generation_status == "completed"
            component_records = [
                {
                    "component_name": module.component_name,
                    "module_name": module.module_name,
                    "inputs": module.inputs,
                    "outputs": module.outputs,
                    "rtl_code": module.rtl_code,
                    "generation_status": (
                        "completed" if completed else "failed"
                    ),
                    "interface_validation_status": (
                        "passed" if completed else "not_run"
                    ),
                    "interface_validation_errors": [],
                    "generation_error": module.generation_error,
                    "rtl_path": None,
                    "raw_response_path": None,
                }
                for module in rtl_result.component_modules
            ]
            integrated_rtl = rtl_result.rtl_code if completed else ""
            if completed:
                (run_dir / "integrated_rtl.v").write_text(
                    integrated_rtl,
                    encoding="utf-8",
                )
                (run_dir / "top_level_rtl.v").write_text(
                    "module system_top (source, result); endmodule\n",
                    encoding="utf-8",
                )
            integration = {
                "status": "completed" if completed else "not_attempted",
                "errors": [] if completed else rtl_result.generation_issues,
                "top_module_name": rtl_result.module_name if completed else None,
                "component_instances": [],
                "integrated_rtl": integrated_rtl,
                "rtl_path": "integrated_rtl.v" if completed else None,
            }
            return {
                "run_id": "synthetic-run",
                "run_directory": str(run_dir),
                "generation_status": "completed" if completed else "failed",
                "components": component_records,
                "integration": integration,
                "summary": {
                    "components_generated": len(component_records) if completed else 0,
                    "components_interface_validated": (
                        len(component_records) if completed else 0
                    ),
                },
            }

        patches = ExitStack()
        patches.enter_context(patch(
            "src.pipeline._load_specification",
            return_value=(
                [SimpleNamespace(page_content=specification)],
                specification,
                [],
                [],
            ),
        ))
        patches.enter_context(patch(
            "src.pipeline.understand_specification",
            return_value=understanding,
        ))
        patches.enter_context(patch(
            "src.pipeline.decomposer",
            return_value=decomposition,
        ))
        patches.enter_context(patch(
            "src.pipeline.describe_component",
            return_value=description,
        ))
        patches.enter_context(patch(
            "src.pipeline.verify_description",
            return_value=VerificationResult(
                valid=True,
                issues=[],
                suggestions=[],
                reasoning="The fixture is internally consistent.",
            ),
        ))
        patches.enter_context(patch(
            "src.pipeline.generate_pseudocode",
            return_value=pseudocode,
        ))
        patches.enter_context(patch(
            "src.pipeline.run_experimental_rtl_generation",
            side_effect=fake_experimental_rtl,
        ))
        patches.enter_context(patch(
            "src.pipeline._compile_integrated_rtl",
            return_value={
                "status": "passed",
                "compiler": "iverilog",
                "errors": [],
                "log_path": "compilation.log",
            },
        ))
        return patches, rtl_calls

    def test_pipeline_passes_component_context_and_saves_integrated_results(self):
        _specification, _understanding, decomposition, _description, _pseudo = (
            self._pipeline_inputs()
        )
        rtl_result = RTLGenerationOutput(
            module_name="system_top",
            rtl_code=(
                "module passer (source, result); endmodule\n"
                "module system_top (source, result); endmodule"
            ),
            component_modules=[
                ComponentRTLModuleOutput(
                    component_name="passer",
                    module_name="passer",
                    inputs=["source"],
                    outputs=["result"],
                    rtl_code="module passer (source, result); endmodule",
                    generation_status="completed",
                )
            ],
            generation_status="completed",
        )
        progress_events = []
        patches, rtl_calls = self._patch_pipeline(progress_events, rtl_result)

        with tempfile.TemporaryDirectory() as output_dir, patches:
            summary = run_pipeline(
                "spec.docx",
                output_dir,
                progress_callback=progress_events.append,
            )

            self.assertEqual(len(rtl_calls), 1)
            self.assertEqual(rtl_calls[0]["decomposition"], decomposition)
            self.assertIsNotNone(rtl_calls[0]["understanding"])
            saved_pseudocode = json.loads(
                (Path(output_dir) / "pseudocode.json").read_text(
                    encoding="utf-8"
                )
            )
            saved_rtl = json.loads(
                (Path(output_dir) / "rtl_generation.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(saved_pseudocode["components"][0]["component_name"], "passer")
            self.assertEqual(saved_rtl["generation_status"], "completed")
            self.assertEqual(summary["rtl_component_modules"], 1)
            self.assertEqual(summary["stages"]["integration"], "completed")
            self.assertEqual(
                [event["status"] for event in progress_events if event["stage"] == "rtl_generation"],
                ["running", "completed"],
            )

    def test_pipeline_does_not_report_partial_rtl_as_complete(self):
        rtl_result = RTLGenerationOutput(
            module_name="system_top",
            generation_status="Failed",
            generation_issues=["Component RTL generation failed."],
            component_modules=[
                ComponentRTLModuleOutput(
                    component_name="passer",
                    module_name="passer",
                    inputs=["source"],
                    outputs=["result"],
                    generation_status="Failed",
                    generation_error="Invalid module declaration.",
                )
            ],
        )
        progress_events = []
        patches, _rtl_calls = self._patch_pipeline(progress_events, rtl_result)

        with tempfile.TemporaryDirectory() as output_dir, patches:
            summary = run_pipeline(
                "spec.docx",
                output_dir,
                progress_callback=progress_events.append,
            )

            saved_rtl = json.loads(
                (Path(output_dir) / "rtl_generation.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(saved_rtl["generation_status"], "Failed")
            self.assertEqual(summary["stages"]["rtl_generation"], "failed")
            self.assertTrue(any(
                event["stage"] == "rtl_generation"
                and event["status"] == "failed"
                for event in progress_events
            ))

    def test_validation_failure_keeps_generated_pseudocode_and_raw_response(self):
        response_content = json.dumps(
            {
                "component_name": "demo",
                "module_name": "demo",
                "inputs": ["a[7:0]"],
                "outputs": [],
                "pseudocode": [
                    "```text",
                    "  MODULE demo  ",
                    "  UNRESOLVED CLOCK : clock edge - edge is not specified",
                    "  END BLOCK ",
                    "  END MODULE ",
                    "```",
                ],
                "assumptions": [],
                "unresolved_issues": [],
            }
        )
        fake_llm = SimpleNamespace(
            invoke=lambda _prompt: SimpleNamespace(content=response_content)
        )

        with tempfile.TemporaryDirectory() as output_dir:
            with patch(
                "src.agents.pseudocode_to_python.convert_pseudocode",
                side_effect=AssertionError("legacy converter must not run"),
            ) as converter:
                with patch("src.agents.pseudocode.get_llm", return_value=fake_llm):
                    result = generate_pseudocode(
                        specification="A small demonstration specification.",
                        decomposition=DecompositionOutput(
                            components=[
                                Component(
                                    name="demo",
                                    purpose="",
                                    inputs=["a[7:0]"],
                                    outputs=[],
                                )
                            ],
                            interactions=[],
                            implementation_plan=[],
                        ),
                        descriptions=[],
                        raw_output_dir=output_dir,
                    )
                converter.assert_not_called()

            self.assertEqual(result.generation_status, "completed")
            self.assertEqual(result.validation_status, "Failed")
            self.assertEqual(
                result.components[0].pseudocode,
                [
                    "  MODULE demo",
                    "  UNRESOLVED CLOCK : clock edge - edge is not specified",
                    "  END BLOCK",
                    "  END MODULE",
                ],
            )
            self.assertTrue(result.validation_issues)
            self.assertIn(
                "UNRESOLVED_REQUIREMENT_BLOCKS_RTL",
                {issue["code"] for issue in result.validation_issues},
            )
            self.assertEqual(result.execution_status, "Not attempted")
            self.assertFalse(result.execution_errors)
            self.assertFalse(
                any("converter" in error.lower() for error in result.execution_errors)
            )
            self.assertEqual(
                (Path(output_dir) / "pseudocode_raw.txt").read_text(
                    encoding="utf-8"
                ),
                response_content,
            )

    def test_invalid_pseudocode_still_blocks_rtl_generation(self):
        pseudocode = PseudocodeGenerationOutput(
            components=[],
            validation_status="Failed",
        )

        with patch("src.agents.rtl_generation.get_llm") as llm:
            result = generate_rtl("A hardware specification.", pseudocode)

        llm.assert_not_called()
        self.assertEqual(result.generation_status, "Failed")
        self.assertEqual(result.rtl_code, "")
        self.assertTrue(result.generation_issues)

    def test_component_rtl_is_integrated_through_decomposition_interactions(self):
        decomposition = DecompositionOutput(
            components=[
                Component(
                    name="first",
                    purpose="Forward the input.",
                    inputs=["first_in[7:0]"],
                    outputs=["first_out[7:0]"],
                ),
                Component(
                    name="second",
                    purpose="Forward the intermediate value.",
                    inputs=["second_in[7:0]"],
                    outputs=["result[7:0]"],
                ),
            ],
            interactions=[
                "source -> first first_in",
                "first first_out -> second second_in",
            ],
            implementation_plan=[],
        )
        understanding = Understanding(
            system_purpose="A two-stage pass-through design.",
            major_components=["first", "second"],
            inputs=["source[7:0]"],
            outputs=["result[7:0]"],
            functional_requirements=[],
            constraints=[],
            ambiguities=[],
        )
        pseudocode = PseudocodeGenerationOutput(
            components=[
                ComponentPseudocodeOutput(
                    component_name="first",
                    module_name="first",
                    inputs=["first_in[7:0]"],
                    outputs=["first_out[7:0]"],
                    pseudocode=["MODULE first", "END MODULE"],
                    assumptions=[],
                    unresolved_issues=[],
                    validation_status="Passed",
                ),
                ComponentPseudocodeOutput(
                    component_name="second",
                    module_name="second",
                    inputs=["second_in[7:0]"],
                    outputs=["result[7:0]"],
                    pseudocode=["MODULE second", "END MODULE"],
                    assumptions=[],
                    unresolved_issues=[],
                    validation_status="Passed",
                ),
            ],
            validation_status="Passed",
        )
        rtl_responses = iter([
            json.dumps({
                "module_name": "first",
                "language": "Verilog",
                "assumptions": [],
                "unresolved_issues": [],
                "rtl_code": (
                    "module first (first_in, first_out);\n"
                    "input [7:0] first_in;\n"
                    "output [7:0] first_out;\n"
                    "assign first_out = first_in;\n"
                    "endmodule"
                ),
            }),
            json.dumps({
                "module_name": "second",
                "language": "Verilog",
                "assumptions": [],
                "unresolved_issues": [],
                "rtl_code": (
                    "module second (second_in, result);\n"
                    "input [7:0] second_in;\n"
                    "output [7:0] result;\n"
                    "assign result = second_in;\n"
                    "endmodule"
                ),
            }),
        ])
        fake_llm = SimpleNamespace(
            invoke=lambda _prompt: SimpleNamespace(content=next(rtl_responses))
        )

        with patch("src.agents.rtl_generation.get_llm", return_value=fake_llm):
            result = generate_rtl(
                "A two-stage pass-through design.",
                pseudocode,
                decomposition=decomposition,
                understanding=understanding,
            )

        self.assertEqual(result.generation_status, "completed")
        self.assertEqual(
            [module.module_name for module in result.component_modules],
            ["first", "second"],
        )
        self.assertEqual(
            [instance.component_name for instance in result.component_instances],
            ["first", "second"],
        )
        self.assertEqual(result.interactions, decomposition.interactions)
        self.assertIn(".first_in(source)", result.rtl_code)
        self.assertIn("wire [7:0] net_first_first_out;", result.rtl_code)
        self.assertIn(".first_out(net_first_first_out)", result.rtl_code)
        self.assertIn(".second_in(net_first_first_out)", result.rtl_code)
        self.assertIn(".result(result)", result.rtl_code)
        top_level_rtl = result.rtl_code.split("module system_top", 1)[1]
        self.assertNotRegex(top_level_rtl, r"\b(?:always|assign)\b")
        self.assertEqual(
            re.findall(
                r"\bmodule\s+([A-Za-z_][A-Za-z0-9_]*)",
                result.rtl_code,
            ),
            ["first", "second", "system_top"],
        )

    def test_top_level_integration_preserves_source_slice_and_busy_output(self):
        components = [
            Component(
                name="source_stage",
                purpose="Forward the bus and busy status.",
                inputs=["source[31:0]"],
                outputs=["data[31:0]", "busy"],
            ),
            Component(
                name="sink_stage",
                purpose="Consume the low five bits.",
                inputs=["data_in[4:0]"],
                outputs=["result[4:0]"],
            ),
        ]
        decomposition = DecompositionOutput(
            components=components,
            interactions=[
                "source[31:0] -> source_stage source[31:0]",
                "source_stage data[4:0] -> sink_stage data_in[4:0]",
            ],
            implementation_plan=[],
        )
        understanding = Understanding(
            system_purpose="Forward a selected bus and busy status.",
            major_components=["source_stage", "sink_stage"],
            inputs=["source[31:0]"],
            outputs=["result[4:0]", "busy"],
            functional_requirements=[],
            constraints=[],
            ambiguities=[],
        )
        modules = [
            ComponentRTLModuleOutput(
                component_name=component.name,
                module_name=component.name,
                inputs=component.inputs,
                outputs=component.outputs,
                rtl_code="",
                generation_status="completed",
            )
            for component in components
        ]

        _, top_rtl, instances = _build_top_level_rtl(
            components,
            modules,
            decomposition,
            understanding,
        )

        self.assertIn(".data_in(net_source_stage_data[4:0])", top_rtl)
        self.assertIn(".busy(busy)", top_rtl)
        self.assertEqual(
            instances[1].port_connections["data_in"],
            "net_source_stage_data[4:0]",
        )

    def test_top_level_integration_rejects_out_of_range_source_slice(self):
        component = Component(
            name="source_stage",
            purpose="Produce a bus.",
            inputs=[],
            outputs=["data[31:0]"],
        )
        sink = Component(
            name="sink_stage",
            purpose="Consume a five-bit bus.",
            inputs=["data_in[4:0]"],
            outputs=["result[4:0]"],
        )
        decomposition = DecompositionOutput(
            components=[component, sink],
            interactions=[
                "source_stage data[32:0] -> sink_stage data_in[4:0]"
            ],
            implementation_plan=[],
        )
        understanding = Understanding(
            system_purpose="Test a source range.",
            major_components=["source_stage", "sink_stage"],
            inputs=[],
            outputs=["result[4:0]"],
            functional_requirements=[],
            constraints=[],
            ambiguities=[],
        )
        modules = [
            ComponentRTLModuleOutput(
                component_name=item.name,
                module_name=item.name,
                inputs=item.inputs,
                outputs=item.outputs,
            )
            for item in [component, sink]
        ]

        with self.assertRaisesRegex(ValueError, "outside the declared range"):
            _build_top_level_rtl(components=[component, sink],
                                 component_modules=modules,
                                 decomposition=decomposition,
                                 understanding=understanding)

    def test_top_level_integration_rejects_mismatched_slice_width(self):
        component = Component(
            name="source_stage",
            purpose="Produce a bus.",
            inputs=[],
            outputs=["data[31:0]"],
        )
        sink = Component(
            name="sink_stage",
            purpose="Consume a six-bit bus.",
            inputs=["data_in[5:0]"],
            outputs=["result[5:0]"],
        )
        decomposition = DecompositionOutput(
            components=[component, sink],
            interactions=[
                "source_stage data[4:0] -> sink_stage data_in[5:0]"
            ],
            implementation_plan=[],
        )
        understanding = Understanding(
            system_purpose="Test selected range width.",
            major_components=["source_stage", "sink_stage"],
            inputs=[],
            outputs=["result[5:0]"],
            functional_requirements=[],
            constraints=[],
            ambiguities=[],
        )
        modules = [
            ComponentRTLModuleOutput(
                component_name=item.name,
                module_name=item.name,
                inputs=item.inputs,
                outputs=item.outputs,
            )
            for item in [component, sink]
        ]

        with self.assertRaisesRegex(ValueError, "mismatched signal width"):
            _build_top_level_rtl(
                [component, sink], modules, decomposition, understanding
            )

    def test_invalid_interaction_keeps_component_diagnostics_but_blocks_top(self):
        decomposition = DecompositionOutput(
            components=[
                Component(
                    name="passer",
                    purpose="Pass the input through.",
                    inputs=["source"],
                    outputs=["result"],
                )
            ],
            interactions=["not a valid connection"],
            implementation_plan=[],
        )
        understanding = Understanding(
            system_purpose="A pass-through design.",
            major_components=["passer"],
            inputs=["source"],
            outputs=["result"],
            functional_requirements=[],
            constraints=[],
            ambiguities=[],
        )
        pseudocode = PseudocodeGenerationOutput(
            components=[
                ComponentPseudocodeOutput(
                    component_name="passer",
                    module_name="passer",
                    inputs=["source"],
                    outputs=["result"],
                    pseudocode=["MODULE passer", "END MODULE"],
                    assumptions=[],
                    unresolved_issues=[],
                    validation_status="Passed",
                )
            ],
            validation_status="Passed",
        )
        fake_llm = SimpleNamespace(
            invoke=lambda _prompt: SimpleNamespace(content=json.dumps({
                "module_name": "passer",
                "language": "Verilog",
                "assumptions": [],
                "unresolved_issues": [],
                "rtl_code": (
                    "module passer (source, result);\n"
                    "input source;\n"
                    "output result;\n"
                    "assign result = source;\n"
                    "endmodule"
                ),
            }))
        )

        with patch("src.agents.rtl_generation.get_llm", return_value=fake_llm):
            result = generate_rtl(
                "A pass-through design.",
                pseudocode,
                decomposition=decomposition,
                understanding=understanding,
            )

        self.assertEqual(result.generation_status, "Failed")
        self.assertEqual(result.rtl_code, "")
        self.assertEqual(
            result.component_modules[0].generation_status,
            "completed",
        )
        self.assertIn("Interaction", result.generation_issues[0])

    def test_generates_and_validates_each_decomposed_component(self):
        component_names = ("InputStage", "OutputStage")
        response_contents = [
            json.dumps({
                "component_name": name,
                "module_name": name,
                "inputs": [f"{name}_in"],
                "outputs": [f"{name}_out"],
                "pseudocode": [
                    f"MODULE {name}",
                    f"INPUT {name}_in",
                    f"OUTPUT {name}_out",
                    "BLOCK COMBINATIONAL",
                    f"  ASSIGN {name}_out = {name}_in",
                    "END BLOCK",
                    "END MODULE",
                ],
                "assumptions": [],
                "unresolved_issues": [],
            })
            for name in component_names
        ]
        responses = iter(response_contents)
        invocation_count = 0

        def fake_invoke(_prompt):
            nonlocal invocation_count
            invocation_count += 1
            return SimpleNamespace(content=next(responses))

        fake_llm = SimpleNamespace(
            invoke=fake_invoke
        )
        decomposition = DecompositionOutput(
            components=[
                Component(
                    name=name,
                    purpose="Pass the input through.",
                    inputs=[f"{name}_in"],
                    outputs=[f"{name}_out"],
                )
                for name in component_names
            ],
            interactions=[],
            implementation_plan=[],
        )
        understanding = Understanding(
            system_purpose="Each named component passes a top-level input through.",
            major_components=list(component_names),
            inputs=[f"{name}_in" for name in component_names],
            outputs=[],
            functional_requirements=[],
            constraints=[],
            ambiguities=[],
        )

        with tempfile.TemporaryDirectory() as output_dir:
            with patch("src.agents.pseudocode.get_llm", return_value=fake_llm):
                result = generate_pseudocode(
                    specification="Each named component passes its input to its output.",
                    decomposition=decomposition,
                    descriptions=[],
                    understanding=understanding,
                    raw_output_dir=output_dir,
                )
            raw_files = {
                path.name for path in Path(output_dir).glob("pseudocode_raw_*.txt")
            }

        self.assertEqual(
            [component.component_name for component in result.components],
            list(component_names),
        )
        self.assertEqual(invocation_count, len(component_names))
        self.assertEqual(
            raw_files,
            {f"pseudocode_raw_{name}.txt" for name in component_names},
        )
        self.assertEqual(
            [component.validation_status for component in result.components],
            ["Passed", "Passed"],
        )
        self.assertEqual(result.validation_status, "Passed")

    def test_description_interface_mismatch_is_reported_without_rewriting_ports(self):
        response_content = json.dumps({
            "component_name": "passer",
            "module_name": "passer",
            "inputs": ["source"],
            "outputs": ["result"],
            "pseudocode": [
                "MODULE passer",
                "INPUT source",
                "OUTPUT result",
                "BLOCK COMBINATIONAL",
                "  ASSIGN result = source",
                "END BLOCK",
                "END MODULE",
            ],
            "assumptions": [],
            "unresolved_issues": [],
        })
        fake_llm = SimpleNamespace(
            invoke=lambda _prompt: SimpleNamespace(content=response_content)
        )
        specification, understanding, decomposition, description, _ = (
            self._pipeline_inputs()
        )
        description.inputs[0].width = "8"

        with tempfile.TemporaryDirectory() as output_dir:
            with patch("src.agents.pseudocode.get_llm", return_value=fake_llm):
                result = generate_pseudocode(
                    specification=specification,
                    decomposition=decomposition,
                    descriptions=[description],
                    understanding=understanding,
                    raw_output_dir=output_dir,
                )

        component = result.components[0]
        self.assertEqual(component.inputs, ["source"])
        self.assertEqual(component.validation_status, "Failed")
        self.assertIn(
            "COMPONENT_DESCRIPTION_INTERFACE_MISMATCH",
            {issue["code"] for issue in component.validation_issues},
        )

    def test_mismatched_decomposition_interaction_fails_aggregate_validation(self):
        names = ("source_stage", "sink_stage")
        response_contents = [
            json.dumps({
                "component_name": name,
                "module_name": name,
                "inputs": inputs,
                "outputs": outputs,
                "pseudocode": [
                    f"MODULE {name}",
                    *(f"INPUT {signal}" for signal in inputs),
                    *(f"OUTPUT {signal}" for signal in outputs),
                    "BLOCK COMBINATIONAL",
                    *(
                        f"  ASSIGN {signal.split('[')[0]} = "
                        f"{inputs[0].split('[')[0]}"
                        for signal in outputs
                    ),
                    "END BLOCK",
                    "END MODULE",
                ],
                "assumptions": [],
                "unresolved_issues": [],
            })
            for name, inputs, outputs in (
                ("source_stage", ["source"], ["data[7:0]"]),
                ("sink_stage", ["data_in[3:0]"], ["result"]),
            )
        ]
        responses = iter(response_contents)
        fake_llm = SimpleNamespace(
            invoke=lambda _prompt: SimpleNamespace(content=next(responses))
        )
        decomposition = DecompositionOutput(
            components=[
                Component(
                    name="source_stage",
                    purpose="Forward its input.",
                    inputs=["source"],
                    outputs=["data[7:0]"],
                ),
                Component(
                    name="sink_stage",
                    purpose="Forward its input.",
                    inputs=["data_in[3:0]"],
                    outputs=["result"],
                ),
            ],
            interactions=["source_stage data[7:0] -> sink_stage data_in[3:0]"],
            implementation_plan=[],
        )
        understanding = Understanding(
            system_purpose="A two-stage pass-through.",
            major_components=["source_stage", "sink_stage"],
            inputs=["external_bus[7:0]: source data"],
            outputs=[],
            functional_requirements=[],
            constraints=[],
            ambiguities=[],
        )

        with tempfile.TemporaryDirectory() as output_dir:
            with patch("src.agents.pseudocode.get_llm", return_value=fake_llm):
                result = generate_pseudocode(
                    specification="Two stages forward values.",
                    decomposition=decomposition,
                    descriptions=[],
                    understanding=understanding,
                    raw_output_dir=output_dir,
                )

        self.assertEqual(
            [component.component_name for component in result.components],
            list(names),
        )
        self.assertEqual(result.generation_status, "completed")
        self.assertEqual(result.validation_status, "Failed")
        self.assertIn(
            "DECOMPOSITION_INTERACTION_INTERFACE_MISMATCH",
            {issue["code"] for issue in result.validation_issues},
        )

    def test_interaction_cannot_reference_missing_busy_output(self):
        response_data = {
            "ResultRegisterOutput": {
                "inputs": ["selected_result[31:0]"],
                "outputs": ["result[31:0]", "valid", "error"],
                "assignments": [
                    "  ASSIGN result = selected_result",
                    "  ASSIGN valid = 1'b0",
                    "  ASSIGN error = 1'b0",
                ],
            },
            "OperandCaptureControl": {
                "inputs": ["busy"],
                "outputs": ["busy_next"],
                "assignments": ["  ASSIGN busy_next = busy"],
            },
        }
        responses = iter(
            json.dumps({
                "component_name": name,
                "module_name": name,
                "inputs": data["inputs"],
                "outputs": data["outputs"],
                "pseudocode": [
                    f"MODULE {name}",
                    *(f"INPUT {signal}" for signal in data["inputs"]),
                    *(f"OUTPUT {signal}" for signal in data["outputs"]),
                    "BLOCK COMBINATIONAL",
                    *data["assignments"],
                    "END BLOCK",
                    "END MODULE",
                ],
                "assumptions": [],
                "unresolved_issues": [],
            })
            for name, data in response_data.items()
        )
        invocation_count = 0

        def fake_invoke(_prompt):
            nonlocal invocation_count
            invocation_count += 1
            return SimpleNamespace(content=next(responses))

        decomposition = DecompositionOutput(
            components=[
                Component(
                    name="ResultRegisterOutput",
                    purpose="Drive registered results.",
                    inputs=["selected_result[31:0]"],
                    outputs=["result[31:0]", "valid", "error"],
                ),
                Component(
                    name="OperandCaptureControl",
                    purpose="Control operand capture.",
                    inputs=["busy"],
                    outputs=["busy_next"],
                ),
            ],
            interactions=[
                "ResultRegisterOutput busy -> OperandCaptureControl busy"
            ],
            implementation_plan=[],
        )
        fake_llm = SimpleNamespace(invoke=fake_invoke)

        with tempfile.TemporaryDirectory() as output_dir:
            with patch("src.agents.pseudocode.get_llm", return_value=fake_llm):
                result = generate_pseudocode(
                    specification="The top-level design exposes a busy signal.",
                    decomposition=decomposition,
                    descriptions=[],
                    raw_output_dir=output_dir,
                )

        self.assertEqual(invocation_count, 2)
        self.assertEqual(
            [component.component_name for component in result.components],
            ["ResultRegisterOutput", "OperandCaptureControl"],
        )
        issue_messages = [
            issue["message"] for issue in result.validation_issues
            if issue["code"] == "DECOMPOSITION_INTERACTION_INTERFACE_MISMATCH"
        ]
        self.assertTrue(any("no output port 'busy'" in message for message in issue_messages))

    def test_apu_decomposition_repairs_connections_and_adds_busy_interface(self):
        components = [
            Component(
                name="OperandCaptureControl",
                purpose="Capture operation inputs.",
                inputs=["operand_a[31:0]", "operand_b[31:0]"],
                outputs=[
                    "captured_a[31:0]",
                    "captured_b[31:0]",
                    "captured_opcode[3:0]",
                ],
            ),
            Component(
                name="OpcodeDecoder",
                purpose="Decode the opcode.",
                inputs=["captured_opcode[3:0]"],
                outputs=["op_add"],
            ),
            Component(
                name="ArithmeticUnit",
                purpose="Perform arithmetic.",
                inputs=["captured_a[31:0]", "captured_b[31:0]"],
                outputs=["arith_result[31:0]"],
            ),
            Component(
                name="LogicalUnit",
                purpose="Perform logic operations.",
                inputs=["captured_a[31:0]", "captured_b[31:0]"],
                outputs=["logic_result[31:0]"],
            ),
            Component(
                name="ShiftUnit",
                purpose="Perform logical shifts.",
                inputs=["captured_a[31:0]", "captured_b[4:0]"],
                outputs=["shift_result[31:0]"],
            ),
            Component(
                name="ResultMux",
                purpose="Select the operation result.",
                inputs=[
                    "arith_result[31:0]",
                    "logic_result[31:0]",
                    "shift_result[31:0]",
                ],
                outputs=["selected_result[31:0]"],
            ),
            Component(
                name="ResultRegisterOutput",
                purpose="Register results and status.",
                inputs=[
                    "selected_result[31:0]",
                    "capture_enable",
                    "opcode_error",
                    "clk",
                    "rst_n",
                ],
                outputs=["result[31:0]", "valid", "error"],
            ),
        ]
        decomposition = DecompositionOutput(
            components=components,
            interactions=[
                "OperandCaptureControl captured_a[31:0] -> "
                "OpcodeDecoder captured_opcode[3:0]",
                "OperandCaptureControl captured_b[31:0] -> "
                "ArithmeticUnit captured_a[31:0]",
                "OperandCaptureControl captured_b[31:0] -> "
                "LogicalUnit captured_a[31:0]",
                "ResultRegisterOutput busy -> busy",
            ],
            implementation_plan=[],
        )
        understanding = Understanding(
            system_purpose="An arithmetic and logic unit.",
            major_components=[component.name for component in components],
            inputs=[],
            outputs=["busy: asserted while processing"],
            functional_requirements=[],
            constraints=[],
            ambiguities=[],
        )

        fake_llm = SimpleNamespace(
            invoke=lambda _messages: SimpleNamespace(
                content=decomposition.model_dump_json()
            )
        )
        with patch("src.agents.decomposer.get_llm", return_value=fake_llm):
            corrected = decomposer(understanding)
        corrected_result = next(
            component for component in corrected.components
            if component.name == "ResultRegisterOutput"
        )

        self.assertIn("busy", corrected_result.outputs)
        self.assertIn("busy", corrected_result.purpose.lower())
        self.assertIn(
            "OperandCaptureControl captured_opcode[3:0] -> "
            "OpcodeDecoder captured_opcode[3:0]",
            corrected.interactions,
        )
        self.assertIn(
            "OperandCaptureControl captured_a[31:0] -> "
            "ArithmeticUnit captured_a[31:0]",
            corrected.interactions,
        )
        self.assertIn(
            "OperandCaptureControl captured_a[31:0] -> "
            "LogicalUnit captured_a[31:0]",
            corrected.interactions,
        )
        self.assertIn("ResultRegisterOutput busy -> busy", corrected.interactions)

        description = DescriptionOutput(
            module_name="ResultRegisterOutput",
            purpose="Register results and status.",
            inputs=[
                Signal(
                    name="selected_result",
                    direction="input",
                    width="32",
                    description="Selected result value.",
                ),
                Signal(
                    name="capture_enable",
                    direction="input",
                    width="1",
                    description="Accepted-operation indicator.",
                ),
                Signal(
                    name="opcode_error",
                    direction="input",
                    width="1",
                    description="Unsupported opcode indicator.",
                ),
                Signal(
                    name="clk",
                    direction="input",
                    width="1",
                    description="System clock.",
                ),
                Signal(
                    name="rst_n",
                    direction="input",
                    width="1",
                    description="Active-low reset.",
                ),
            ],
            outputs=[
                Signal(
                    name="result",
                    direction="output",
                    width="32",
                    description="Result output.",
                ),
                Signal(
                    name="valid",
                    direction="output",
                    width="1",
                    description="Valid status.",
                ),
                Signal(
                    name="error",
                    direction="output",
                    width="1",
                    description="Error status.",
                ),
                Signal(
                    name="busy",
                    direction="output",
                    width="1",
                    description="Busy status.",
                ),
            ],
            state_elements=[],
            constraints=[],
            behavior=[],
            spec_references=[],
        )
        self.assertIs(
            align_interface_with_decomposer(description, corrected_result),
            description,
        )

    def test_pseudocode_interaction_checks_allow_only_valid_source_slices(self):
        source = Component(
            name="OperandCaptureControl",
            purpose="Capture operands.",
            inputs=[],
            outputs=["captured_b[31:0]"],
        )
        shift = Component(
            name="ShiftUnit",
            purpose="Shift by the low five bits.",
            inputs=["captured_b[4:0]"],
            outputs=["shift_result[31:0]"],
        )

        def issues_for(source_endpoint: str, destination_width: str = "[4:0]"):
            target = shift.model_copy(update={
                "inputs": [f"captured_b{destination_width}"]
            })
            return _decomposition_interaction_issues(
                DecompositionOutput(
                    components=[source, target],
                    interactions=[
                        f"OperandCaptureControl {source_endpoint} -> "
                        f"ShiftUnit captured_b{destination_width}"
                    ],
                    implementation_plan=[],
                ),
                None,
            )

        self.assertEqual(issues_for("captured_b[4:0]"), [])
        self.assertTrue(issues_for("captured_b[32:0]"))
        self.assertTrue(
            issues_for("captured_b[4:0]", destination_width="[5:0]")
        )

    def test_interaction_rejects_duplicate_destination_drivers(self):
        decomposition = DecompositionOutput(
            components=[
                Component(
                    name="producer_left",
                    purpose="Produce a value.",
                    inputs=[],
                    outputs=["value[7:0]"],
                ),
                Component(
                    name="producer_right",
                    purpose="Produce another value.",
                    inputs=[],
                    outputs=["value[7:0]"],
                ),
                Component(
                    name="consumer",
                    purpose="Consume one value.",
                    inputs=["value[7:0]"],
                    outputs=[],
                ),
            ],
            interactions=[
                "producer_left value[7:0] -> consumer value[7:0]",
                "producer_right value[7:0] -> consumer value[7:0]",
            ],
            implementation_plan=[],
        )

        issues = _decomposition_interaction_issues(decomposition, None)

        self.assertIn(
            "DECOMPOSITION_INTERACTION_DUPLICATE_DRIVER",
            {issue["code"] for issue in issues},
        )

    def test_interaction_rejects_inconsistent_operand_channel_labels(self):
        decomposition = DecompositionOutput(
            components=[
                Component(
                    name="capture",
                    purpose="Capture two values.",
                    inputs=[],
                    outputs=["captured_a[31:0]", "captured_b[31:0]"],
                ),
                Component(
                    name="operator",
                    purpose="Use two values.",
                    inputs=["captured_a[31:0]", "captured_b[31:0]"],
                    outputs=[],
                ),
            ],
            interactions=[
                "capture captured_b[31:0] -> operator captured_a[31:0]",
                "capture captured_b[31:0] -> operator captured_b[31:0]",
            ],
            implementation_plan=[],
        )

        issues = _decomposition_interaction_issues(decomposition, None)

        self.assertIn(
            "DECOMPOSITION_INTERACTION_SIGNAL_MISMATCH",
            {issue["code"] for issue in issues},
        )

    def test_interaction_reports_malformed_interface_signals(self):
        decomposition = DecompositionOutput(
            components=[
                Component(
                    name="producer",
                    purpose="Produce a value.",
                    inputs=[],
                    outputs=["bad-name[7:0]"],
                ),
                Component(
                    name="consumer",
                    purpose="Consume a value.",
                    inputs=["value[7:0]"],
                    outputs=[],
                ),
            ],
            interactions=["producer bad-name[7:0] -> consumer value[7:0]"],
            implementation_plan=[],
        )

        issues = _decomposition_interaction_issues(decomposition, None)

        self.assertIn(
            "DECOMPOSITION_INTERACTION_INTERFACE_MISMATCH",
            {issue["code"] for issue in issues},
        )

    def test_required_component_input_without_driver_is_rejected(self):
        decomposition = DecompositionOutput(
            components=[
                Component(
                    name="consumer",
                    purpose="Consume an internal value.",
                    inputs=["internal_value[7:0]"],
                    outputs=[],
                )
            ],
            interactions=[],
            implementation_plan=[],
        )
        understanding = Understanding(
            system_purpose="A consumer.",
            major_components=["consumer"],
            inputs=["external_value[7:0]"],
            outputs=[],
            functional_requirements=[],
            constraints=[],
            ambiguities=[],
        )

        issues = _decomposition_interaction_issues(
            decomposition,
            understanding,
        )

        self.assertIn(
            "DECOMPOSITION_INTERACTION_MISSING_INPUT_DRIVER",
            {issue["code"] for issue in issues},
        )

    def test_top_level_and_optional_inputs_are_not_false_missing_drivers(self):
        decomposition = DecompositionOutput(
            components=[
                Component(
                    name="consumer",
                    purpose="Consume external values.",
                    inputs=["mapped_value[7:0]", "direct_value", "optional_debug"],
                    outputs=[],
                )
            ],
            interactions=[
                "external_value[7:0] -> consumer mapped_value[7:0]"
            ],
            implementation_plan=[],
        )
        understanding = Understanding(
            system_purpose="A consumer.",
            major_components=["consumer"],
            inputs=[
                "external_value[7:0]",
                "direct_value",
                "optional_debug: optional diagnostic input",
                "unused_option: optional configuration input",
            ],
            outputs=[],
            functional_requirements=[],
            constraints=[],
            ambiguities=[],
        )

        issues = _decomposition_interaction_issues(
            decomposition,
            understanding,
        )

        self.assertNotIn(
            "DECOMPOSITION_INTERACTION_MISSING_INPUT_DRIVER",
            {issue["code"] for issue in issues},
        )

    def test_timing_ambiguities_are_scoped_to_signal_owners(self):
        understanding = Understanding(
            system_purpose="A sequential datapath.",
            major_components=["capture_control", "datapath"],
            inputs=["start", "clk", "data"],
            outputs=["captured_data", "result"],
            functional_requirements=[],
            constraints=[],
            ambiguities=[
                "NOT SPECIFIED: exact timing relationship between start "
                "assertion and operand capture relative to clock edge",
                "NOT SPECIFIED: rising versus falling clock edge",
            ],
        )
        control_description = DescriptionOutput(
            module_name="capture_control",
            purpose="Capture inputs when started.",
            inputs=[],
            outputs=[],
            state_elements=[{
                "name": "captured_data_reg",
                "type": "register",
                "width": "1",
                "reset_value": "NOT SPECIFIED",
                "description": "Captured data.",
            }],
            constraints=[],
            behavior=[],
            spec_references=[],
        )
        datapath_description = DescriptionOutput(
            module_name="datapath",
            purpose="Compute a result.",
            inputs=[],
            outputs=[],
            state_elements=[],
            constraints=[],
            behavior=["Timing follows the selected operation."],
            spec_references=[],
        )

        control_ambiguities = _component_ambiguities(
            "capture_control",
            ["start", "clk"],
            ["captured_data"],
            control_description,
            understanding,
        )
        datapath_ambiguities = _component_ambiguities(
            "datapath",
            ["clk", "data"],
            ["result"],
            datapath_description,
            understanding,
        )

        self.assertEqual(control_ambiguities, understanding.ambiguities)
        self.assertEqual(datapath_ambiguities, [])

    def test_clock_edge_ambiguity_requires_owned_sequential_behavior(self):
        understanding = Understanding(
            system_purpose="A control system.",
            major_components=["storage_owner", "clock_observer"],
            inputs=["clk", "data"],
            outputs=["stored_data"],
            functional_requirements=[],
            constraints=[],
            ambiguities=["NOT SPECIFIED: rising versus falling clock edge"],
        )
        stateful_description = DescriptionOutput(
            module_name="storage_owner",
            purpose="Capture and retain the input data.",
            inputs=[],
            outputs=[],
            state_elements=[{
                "name": "data_reg",
                "type": "register",
                "width": "8",
                "reset_value": "NOT SPECIFIED",
                "description": "Stores captured input data.",
            }],
            constraints=[],
            behavior=["Capture data in the clocked process."],
            spec_references=[],
        )
        stateless_description = DescriptionOutput(
            module_name="clock_observer",
            purpose="Observe an external clock without storing state.",
            inputs=[],
            outputs=[],
            state_elements=[],
            constraints=[],
            behavior=[],
            spec_references=[],
        )

        owned = _component_ambiguities(
            "storage_owner",
            ["clk", "data"],
            ["stored_data"],
            stateful_description,
            understanding,
        )
        unrelated = _component_ambiguities(
            "clock_observer",
            ["clk"],
            [],
            stateless_description,
            understanding,
        )
        responsibility_only = DescriptionOutput(
            module_name="capture_owner",
            purpose="Capture input data into internal storage on a clock.",
            inputs=[],
            outputs=[],
            state_elements=[],
            constraints=[],
            behavior=[],
            spec_references=[],
        )
        inferred_owner = _component_ambiguities(
            "capture_owner",
            ["clk", "data"],
            ["stored_data"],
            responsibility_only,
            understanding,
        )

        self.assertEqual(owned, understanding.ambiguities)
        self.assertEqual(inferred_owner, understanding.ambiguities)
        self.assertEqual(unrelated, [])

    def test_default_reaching_result_register_is_rejected(self):
        decomposition = DecompositionOutput(
            components=[
                Component(
                    name="ResultMux",
                    purpose="Select operation result.",
                    inputs=["arith_result[31:0]", "op_add"],
                    outputs=["selected_result[31:0]"],
                ),
                Component(
                    name="ResultRegisterOutput",
                    purpose="Register selected result.",
                    inputs=["selected_result[31:0]"],
                    outputs=["result[31:0]"],
                ),
            ],
            interactions=[
                "ResultMux selected_result[31:0] -> "
                "ResultRegisterOutput selected_result[31:0]",
                "ResultRegisterOutput result[31:0] -> result[31:0]",
            ],
            implementation_plan=[],
        )
        understanding = Understanding(
            system_purpose="A result datapath.",
            major_components=["ResultMux", "ResultRegisterOutput"],
            inputs=["arith_result[31:0]", "op_add"],
            outputs=["result[31:0]"],
            functional_requirements=[],
            constraints=[],
            ambiguities=[],
        )
        generated = [
            ComponentPseudocodeOutput(
                component_name="ResultMux",
                module_name="ResultMux",
                inputs=["arith_result[31:0]", "op_add"],
                outputs=["selected_result[31:0]"],
                pseudocode=[
                    "MODULE ResultMux",
                    "INPUT arith_result[31:0]",
                    "INPUT op_add",
                    "OUTPUT selected_result[31:0]",
                    "BLOCK COMBINATIONAL",
                    "  IF op_add == 1'b1 THEN",
                    "    ASSIGN selected_result = arith_result",
                    "  ELSE",
                    "    ASSIGN selected_result = 32'b0",
                    "  END IF",
                    "END BLOCK",
                    "END MODULE",
                ],
                assumptions=[],
                unresolved_issues=[],
            ),
            ComponentPseudocodeOutput(
                component_name="ResultRegisterOutput",
                module_name="ResultRegisterOutput",
                inputs=["selected_result[31:0]"],
                outputs=["result[31:0]"],
                pseudocode=[
                    "MODULE ResultRegisterOutput",
                    "INPUT selected_result[31:0]",
                    "OUTPUT result[31:0]",
                    "REG result_reg[31:0]",
                    "BLOCK CLOCKED CLOCK clk EDGE RISING",
                    "  result_reg <= selected_result",
                    "END BLOCK",
                    "BLOCK COMBINATIONAL",
                    "  ASSIGN result = result_reg",
                    "END BLOCK",
                    "END MODULE",
                ],
                assumptions=[],
                unresolved_issues=[],
            ),
        ]

        issues = _observable_datapath_default_issues(
            generated,
            decomposition,
            understanding,
        )

        self.assertIn(
            "OBSERVABLE_DATAPATH_DEFAULT",
            {issue["code"] for issue in issues},
        )

    def test_scalar_default_reaching_system_output_is_rejected(self):
        decomposition = DecompositionOutput(
            components=[
                Component(
                    name="selector",
                    purpose="Select a status value.",
                    inputs=["source", "select"],
                    outputs=["selected"],
                )
            ],
            interactions=["selector selected -> status"],
            implementation_plan=[],
        )
        understanding = Understanding(
            system_purpose="A status selector.",
            major_components=["selector"],
            inputs=["source", "select"],
            outputs=["status"],
            functional_requirements=[],
            constraints=[],
            ambiguities=[],
        )
        generated = [
            ComponentPseudocodeOutput(
                component_name="selector",
                module_name="selector",
                inputs=["source", "select"],
                outputs=["selected"],
                pseudocode=[
                    "MODULE selector",
                    "INPUT source",
                    "INPUT select",
                    "OUTPUT selected",
                    "BLOCK COMBINATIONAL",
                    "  IF select == 1'b1 THEN",
                    "    ASSIGN selected = source",
                    "  ELSE",
                    "    ASSIGN selected = 1'b0",
                    "  END IF",
                    "END BLOCK",
                    "END MODULE",
                ],
                assumptions=[],
                unresolved_issues=[],
            )
        ]

        issues = _observable_datapath_default_issues(
            generated,
            decomposition,
            understanding,
        )

        self.assertIn(
            "OBSERVABLE_DATAPATH_DEFAULT",
            {issue["code"] for issue in issues},
        )

    def test_generation_fails_when_default_can_reach_system_result(self):
        response = {
            "component_name": "result_mux",
            "module_name": "result_mux",
            "inputs": ["data[31:0]", "select"],
            "outputs": ["result[31:0]"],
            "pseudocode": [
                "MODULE result_mux",
                "INPUT data[31:0]",
                "INPUT select",
                "OUTPUT result[31:0]",
                "BLOCK COMBINATIONAL",
                "  IF select == 1'b1 THEN",
                "    ASSIGN result = data",
                "  ELSE",
                "    ASSIGN result = 32'b0",
                "  END IF",
                "END BLOCK",
                "END MODULE",
            ],
            "assumptions": [],
            "unresolved_issues": [],
        }
        fake_llm = SimpleNamespace(
            invoke=lambda _prompt: SimpleNamespace(content=json.dumps(response))
        )
        decomposition = DecompositionOutput(
            components=[
                Component(
                    name="result_mux",
                    purpose="Select a result.",
                    inputs=["data[31:0]", "select"],
                    outputs=["result[31:0]"],
                )
            ],
            interactions=[
                "data[31:0] -> result_mux data[31:0]",
                "select -> result_mux select",
                "result_mux result[31:0] -> result[31:0]",
            ],
            implementation_plan=[],
        )
        understanding = Understanding(
            system_purpose="A result mux.",
            major_components=["result_mux"],
            inputs=["data[31:0]", "select"],
            outputs=["result[31:0]"],
            functional_requirements=[],
            constraints=[],
            ambiguities=[],
        )

        with tempfile.TemporaryDirectory() as output_dir:
            with patch("src.agents.pseudocode.get_llm", return_value=fake_llm):
                result = generate_pseudocode(
                    specification="Select a supported result.",
                    decomposition=decomposition,
                    descriptions=[],
                    understanding=understanding,
                    raw_output_dir=output_dir,
                )

        self.assertEqual(result.validation_status, "Failed")
        self.assertIn(
            "OBSERVABLE_DATAPATH_DEFAULT",
            {issue["code"] for issue in result.validation_issues},
        )

    def test_unconnected_internal_default_is_not_marked_observable(self):
        decomposition = DecompositionOutput(
            components=[
                Component(
                    name="scratch",
                    purpose="Calculate an internal debug value.",
                    inputs=["select"],
                    outputs=["scratch_value[31:0]"],
                )
            ],
            interactions=[],
            implementation_plan=[],
        )
        understanding = Understanding(
            system_purpose="A system with an unrelated result.",
            major_components=["scratch"],
            inputs=["select"],
            outputs=["result[31:0]"],
            functional_requirements=[],
            constraints=[],
            ambiguities=[],
        )
        generated = [
            ComponentPseudocodeOutput(
                component_name="scratch",
                module_name="scratch",
                inputs=["select"],
                outputs=["scratch_value[31:0]"],
                pseudocode=[
                    "MODULE scratch",
                    "INPUT select",
                    "OUTPUT scratch_value[31:0]",
                    "BLOCK COMBINATIONAL",
                    "  IF select == 1'b1 THEN",
                    "    ASSIGN scratch_value = 32'b1",
                    "  ELSE",
                    "    ASSIGN scratch_value = 32'b0",
                    "  END IF",
                    "END BLOCK",
                    "END MODULE",
                ],
                assumptions=[],
                unresolved_issues=[],
            )
        ]

        issues = _observable_datapath_default_issues(
            generated,
            decomposition,
            understanding,
        )

        self.assertNotIn(
            "OBSERVABLE_DATAPATH_DEFAULT",
            {issue["code"] for issue in issues},
        )

    def test_component_traceability_mismatch_fails_generation(self):
        response_content = json.dumps({
            "component_name": "demo",
            "module_name": "demo",
            "inputs": ["unexpected_input"],
            "outputs": [],
            "pseudocode": ["MODULE demo", "END MODULE"],
            "assumptions": [],
            "unresolved_issues": [],
        })
        fake_llm = SimpleNamespace(
            invoke=lambda _prompt: SimpleNamespace(content=response_content)
        )
        decomposition = DecompositionOutput(
            components=[
                Component(
                    name="demo",
                    purpose="",
                    inputs=["expected_input"],
                    outputs=[],
                )
            ],
            interactions=[],
            implementation_plan=[],
        )

        with tempfile.TemporaryDirectory() as output_dir:
            with patch("src.agents.pseudocode.get_llm", return_value=fake_llm):
                result = generate_pseudocode(
                    specification="The component receives expected_input.",
                    decomposition=decomposition,
                    descriptions=[],
                    raw_output_dir=output_dir,
                )

        self.assertEqual(result.generation_status, "Failed")
        self.assertEqual(result.validation_status, "Failed")
        self.assertIn(
            "COMPONENT_TRACEABILITY_MISMATCH",
            {issue["code"] for issue in result.validation_issues},
        )

    def test_duplicate_decomposed_components_fail_without_model_call(self):
        decomposition = DecompositionOutput(
            components=[
                Component(name="demo", purpose="", inputs=[], outputs=[]),
                Component(name="demo", purpose="", inputs=[], outputs=[]),
            ],
            interactions=[],
            implementation_plan=[],
        )

        with patch("src.agents.pseudocode.get_llm") as llm:
            result = generate_pseudocode(
                specification="A hardware specification.",
                decomposition=decomposition,
                descriptions=[],
            )

        llm.assert_not_called()
        self.assertEqual(len(result.components), 2)
        self.assertEqual(result.generation_status, "Failed")
        self.assertEqual(result.validation_status, "Failed")


if __name__ == "__main__":
    unittest.main()

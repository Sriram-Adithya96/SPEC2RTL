import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from src.agents.reflection import reflect_on_rtl
from src.agents.rtl_generation import _generate_component_rtl, generate_rtl
from src.pipeline import AGENT_ORDER, run_pipeline
from src.schemas import (
    Component,
    ComponentPseudocodeOutput,
    ComponentRTLModuleOutput,
    DecompositionOutput,
    DescriptionOutput,
    PseudocodeGenerationOutput,
    RTLGenerationOutput,
    RTLReflectionOutput,
    Understanding,
    VerificationResult,
)


class TestRTLReflectionAndPipeline(unittest.TestCase):

    def setUp(self):
        self.spec = (
            "Hardware Specification: Simple 32-bit ALU\n"
            "Inputs: operand_a[31:0], operand_b[31:0], opcode[3:0], clk, rst_n\n"
            "Outputs: result[31:0], valid, busy, error\n"
        )
        self.generated_rtl = {
            "module_name": "alu_top",
            "language": "Verilog",
            "rtl_code": "module alu_top(...); endmodule",
            "component_modules": [
                {
                    "component_name": "ALU",
                    "module_name": "alu",
                    "inputs": ["operand_a[31:0]", "operand_b[31:0]", "opcode[3:0]"],
                    "outputs": ["result[31:0]", "error"],
                    "rtl_code": "module alu(...); endmodule",
                    "generation_status": "completed",
                }
            ],
            "component_instances": [],
        }

    def test_pipeline_agent_order(self):
        """Pipeline order must strictly follow the required workflow."""
        expected_order = [
            "understanding",
            "decomposer",
            "description",
            "pseudocode",
            "rtl_generation",
            "rtl_verification",
            "reflection",
        ]
        self.assertEqual(AGENT_ORDER, expected_order)

    def test_reflect_on_rtl_when_verification_passes(self):
        """When verification is valid, reflection must not request revision."""
        verification = VerificationResult(
            valid=True,
            issues=[],
            suggestions=[],
            reasoning="All requirements matched.",
        )
        result = reflect_on_rtl(self.spec, self.generated_rtl, verification)
        self.assertFalse(result.needs_revision)
        self.assertEqual(result.feedback, [])
        self.assertIn("No RTL revision required", result.reasoning)

    @patch("src.agents.reflection.create_agent")
    def test_reflect_on_rtl_when_verification_fails(self, mock_create_agent):
        """When verification fails, reflection returns actionable corrections from LLM."""
        verification = VerificationResult(
            valid=False,
            issues=["Missing active-low reset handling in sequential logic"],
            suggestions=["Add if (!rst_n) branch in always @(posedge clk)"],
            reasoning="Reset condition was not met.",
        )
        mock_agent_instance = MagicMock()
        mock_agent_instance.invoke.return_value = {
            "structured_response": RTLReflectionOutput(
                needs_revision=True,
                feedback=["Add synchronous active-low reset check in sequential block"],
                component_feedback={
                    "alu": ["Check !rst_n on clock edge and clear result and error"]
                },
                reasoning="Specification specifies active-low synchronous reset.",
            )
        }
        mock_create_agent.return_value = mock_agent_instance

        result = reflect_on_rtl(self.spec, self.generated_rtl, verification)
        self.assertTrue(result.needs_revision)
        self.assertEqual(len(result.feedback), 1)
        self.assertIn("Add synchronous active-low reset", result.feedback[0])
        self.assertIn("alu", result.component_feedback)

    def test_reflect_on_rtl_fallback_on_llm_error(self):
        """If the reflection LLM call fails, it must fallback to synthesizing feedback from issues."""
        verification = VerificationResult(
            valid=False,
            issues=["Opcode 5 shift uses wrong width"],
            suggestions=["Use operand_b[4:0] for shift amount"],
            reasoning="Shift amount width mismatch.",
        )
        with patch("src.agents.reflection.get_llm", side_effect=RuntimeError("API error")):
            result = reflect_on_rtl(self.spec, self.generated_rtl, verification)
            self.assertTrue(result.needs_revision)
            self.assertTrue(any("Opcode 5" in fb for fb in result.feedback))
            self.assertTrue(any("operand_b[4:0]" in fb for fb in result.feedback))

    def test_generate_component_rtl_injects_reflection_feedback(self):
        """_generate_component_rtl must inject reflection correction feedback into prompt."""
        decomposed = Component(
            name="ALU",
            purpose="Arithmetic",
            inputs=["operand_a[31:0]", "operand_b[31:0]", "opcode[3:0]"],
            outputs=["result[31:0]", "error"],
        )
        pseudocode = ComponentPseudocodeOutput(
            component_name="ALU",
            module_name="alu",
            inputs=["operand_a[31:0]", "operand_b[31:0]", "opcode[3:0]"],
            outputs=["result[31:0]", "error"],
            pseudocode=["MODULE alu", "ENDMODULE alu"],
            assumptions=[],
            unresolved_issues=[],
            generation_status="completed",
            validation_status="Passed",
        )
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = json.dumps({
            "module_name": "alu",
            "language": "Verilog",
            "rtl_code": "module alu(operand_a, operand_b, opcode, result, error);\ninput [31:0] operand_a, operand_b;\ninput [3:0] opcode;\noutput [31:0] result;\noutput error;\nendmodule\n",
            "assumptions": [],
            "unresolved_issues": [],
        })

        feedback = RTLReflectionOutput(
            needs_revision=True,
            feedback=["Fix subtraction underflow handling"],
            component_feedback={"alu": ["Modulo 2^32 wrap on subtraction"]},
            reasoning="Specification requires modulo 2^32 arithmetic.",
        )

        _generate_component_rtl(
            specification=self.spec,
            decomposed=decomposed,
            component_pseudocode=pseudocode,
            llm=mock_llm,
            raw_output_dir=None,
            reflection_feedback=feedback,
        )

        prompt_sent = mock_llm.invoke.call_args[0][0]
        self.assertIn("REFLECTION CORRECTION FEEDBACK", prompt_sent)
        self.assertIn("Fix subtraction underflow handling", prompt_sent)
        self.assertIn("Modulo 2^32 wrap on subtraction", prompt_sent)


class TestPipelineReflectionWorkflow(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = Path(self.temp_dir) / "run_test"
        self.spec_file = Path(self.temp_dir) / "spec.txt"
        self.spec_file.write_text(
            "Hardware Specification: Simple APU\n"
            "Inputs: operand_a[31:0], operand_b[31:0], opcode[3:0], clk, rst_n\n"
            "Outputs: result[31:0], valid, busy, error\n",
            encoding="utf-8",
        )
        self.mock_doc = MagicMock()
        self.mock_doc.page_content = self.spec_file.read_text(encoding="utf-8")
        self.mock_understanding = Understanding(
            system_purpose="Test APU",
            major_components=["ALU"],
            inputs=["operand_a[31:0]", "operand_b[31:0]", "opcode[3:0]", "clk", "rst_n"],
            outputs=["result[31:0]", "valid", "busy", "error"],
            functional_requirements=["Addition", "Reset"],
            constraints=["Synchronous active-low reset"],
            ambiguities=[],
        )
        self.mock_decomposition = DecompositionOutput(
            components=[
                Component(
                    name="ALU",
                    purpose="Arithmetic operations",
                    inputs=["operand_a[31:0]", "operand_b[31:0]", "opcode[3:0]"],
                    outputs=["result[31:0]", "error"],
                )
            ],
            interactions=[],
            implementation_plan=[],
        )
        self.mock_description = DescriptionOutput(
            module_name="ALU",
            purpose="Arithmetic",
            inputs=[],
            outputs=[],
            state_elements=[],
            constraints=[],
            behavior=["Addition"],
            spec_references=[],
        )
        self.mock_pseudocode = PseudocodeGenerationOutput(
            components=[
                ComponentPseudocodeOutput(
                    component_name="ALU",
                    module_name="alu",
                    inputs=["operand_a[31:0]", "operand_b[31:0]", "opcode[3:0]"],
                    outputs=["result[31:0]", "error"],
                    pseudocode=["MODULE alu", "ENDMODULE alu"],
                    assumptions=[],
                    unresolved_issues=[],
                    generation_status="completed",
                    validation_status="Passed",
                )
            ],
            assumptions=[],
            unresolved_issues=[],
            generation_status="completed",
            validation_status="Passed",
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_unified_rtl_result(self, verilog="module top; endmodule", name="APU_Core"):
        """Return value shape from _execute_unified_rtl_generation."""
        from src.schemas import CodeOuput as _CodeOuput
        rtl_output = {
            "module_name": name,
            "language": "Verilog",
            "rtl_code": verilog,
            "code": verilog,
            "component_modules": [
                {
                    "component_name": name,
                    "module_name": name,
                    "inputs": [],
                    "outputs": [],
                    "rtl_code": verilog,
                    "generation_status": "completed",
                    "interface_validation_status": "passed",
                    "interface_validation_errors": [],
                    "generation_error": None,
                }
            ],
            "component_instances": [],
            "interactions": [],
            "generation_status": "completed",
            "component_generation_status": "completed",
            "generation_issues": [],
            "assumptions": [],
            "unresolved_issues": [],
            "interface_validation_status": "passed",
            "integration_status": "completed",
            "compilation_status": "not_run",
            "rtl_agent_status": "completed",
            "experimental": True,
            "production_verified": False,
            "pseudocode_validation_status": "Passed",
            "artifact_paths": {},
        }
        code_output = _CodeOuput(component_name=name, code=verilog, assumptions=[])
        component_state = [{"name": name, "status": "completed"}]
        return rtl_output, code_output, component_state

    @patch("src.pipeline._load_specification")
    @patch("src.pipeline.understand_specification")
    @patch("src.pipeline.decomposer")
    @patch("src.pipeline.describe_component")
    @patch("src.pipeline.generate_pseudocode")
    @patch("src.pipeline._execute_unified_rtl_generation")
    @patch("src.pipeline.verify_rtl")
    @patch("src.pipeline.reflect_on_verification")
    def test_pipeline_skips_reflection_when_verification_passes(
        self, mock_reflect, mock_verify, mock_exec_rtl, mock_pseudo,
        mock_desc, mock_decomp, mock_under, mock_load,
    ):
        """When initial RTL verification passes, reflection is skipped and status is completed."""
        mock_load.return_value = ([self.mock_doc], self.mock_doc.page_content, [self.mock_doc], [self.mock_doc])
        mock_under.return_value = self.mock_understanding
        mock_decomp.return_value = self.mock_decomposition
        mock_desc.return_value = self.mock_description
        mock_pseudo.return_value = self.mock_pseudocode
        mock_exec_rtl.return_value = self._make_unified_rtl_result()
        mock_verify.return_value = VerificationResult(valid=True, issues=[], suggestions=[], reasoning="Valid.")

        summary = run_pipeline(self.spec_file, self.output_dir)

        mock_verify.assert_called_once()
        mock_reflect.assert_not_called()
        self.assertEqual(summary["rtl_verification"], "passed")
        self.assertEqual(summary["reflection"], "skipped")
        self.assertEqual(summary["stages"]["reflection"], "skipped")
        self.assertEqual(summary["overall_status"], "completed")

    @patch("src.pipeline._load_specification")
    @patch("src.pipeline.understand_specification")
    @patch("src.pipeline.decomposer")
    @patch("src.pipeline.describe_component")
    @patch("src.pipeline.generate_pseudocode")
    @patch("src.pipeline._execute_unified_rtl_generation")
    @patch("src.pipeline.verify_rtl")
    @patch("src.pipeline.reflect_on_verification")
    def test_pipeline_reflects_and_regenerates_on_verification_failure(
        self, mock_reflect, mock_verify, mock_exec_rtl, mock_pseudo,
        mock_desc, mock_decomp, mock_under, mock_load,
    ):
        """When verification fails, reflection corrects code and re-verification passes."""
        from src.schemas import CodeOuput as _CodeOuput
        mock_load.return_value = ([self.mock_doc], self.mock_doc.page_content, [self.mock_doc], [self.mock_doc])
        mock_under.return_value = self.mock_understanding
        mock_decomp.return_value = self.mock_decomposition
        mock_desc.return_value = self.mock_description
        mock_pseudo.return_value = self.mock_pseudocode
        mock_exec_rtl.return_value = self._make_unified_rtl_result()
        mock_verify.side_effect = [
            VerificationResult(valid=False, issues=["Shift error"], suggestions=["Fix shift"], reasoning="Fail."),
            VerificationResult(valid=True, issues=[], suggestions=[], reasoning="Pass."),
        ]
        mock_reflect.return_value = _CodeOuput(
            component_name="APU_Core",
            code="module APU_Core(input clk); endmodule",
            assumptions=["Fixed shift"],
        )

        summary = run_pipeline(self.spec_file, self.output_dir)

        self.assertEqual(mock_verify.call_count, 2)
        mock_reflect.assert_called_once()
        self.assertEqual(summary["rtl_verification"], "passed")
        self.assertEqual(summary["reflection"], "completed")
        self.assertEqual(summary["reflection_attempts"], 1)
        self.assertEqual(summary["overall_status"], "completed")

    @patch("src.pipeline._load_specification")
    @patch("src.pipeline.understand_specification")
    @patch("src.pipeline.decomposer")
    @patch("src.pipeline.describe_component")
    @patch("src.pipeline.generate_pseudocode")
    @patch("src.pipeline._execute_unified_rtl_generation")
    @patch("src.pipeline.verify_rtl")
    @patch("src.pipeline.reflect_on_verification")
    def test_pipeline_retry_limit_max_two_attempts(
        self, mock_reflect, mock_verify, mock_exec_rtl, mock_pseudo,
        mock_desc, mock_decomp, mock_under, mock_load,
    ):
        """Pipeline stops after 3 regeneration attempts and reports failure."""
        from src.schemas import CodeOuput as _CodeOuput
        mock_load.return_value = ([self.mock_doc], self.mock_doc.page_content, [self.mock_doc], [self.mock_doc])
        mock_under.return_value = self.mock_understanding
        mock_decomp.return_value = self.mock_decomposition
        mock_desc.return_value = self.mock_description
        mock_pseudo.return_value = self.mock_pseudocode
        mock_exec_rtl.return_value = self._make_unified_rtl_result()
        mock_verify.return_value = VerificationResult(
            valid=False, issues=["Reset error"], suggestions=[], reasoning="Fail."
        )
        mock_reflect.return_value = _CodeOuput(
            component_name="APU_Core", code="module APU_Core; endmodule", assumptions=[]
        )

        summary = run_pipeline(self.spec_file, self.output_dir)

        self.assertEqual(mock_verify.call_count, 4)   # 1 initial + 3 retries
        self.assertEqual(mock_reflect.call_count, 3)  # 3 reflection calls
        self.assertEqual(summary["rtl_verification"], "failed")
        self.assertEqual(summary["reflection_attempts"], 3)
        self.assertEqual(summary["stages"]["rtl_verification"], "failed")
        self.assertEqual(summary["overall_status"], "failed")

    @patch("src.pipeline._load_specification")
    @patch("src.pipeline.understand_specification")
    @patch("src.pipeline.decomposer")
    @patch("src.pipeline.describe_component")
    @patch("src.pipeline.generate_pseudocode")
    @patch("src.pipeline._execute_unified_rtl_generation")
    @patch("src.pipeline.verify_rtl")
    @patch("src.agents.verification.verify_description")
    def test_pipeline_does_not_call_verify_description(
        self, mock_verify_desc, mock_verify_rtl, mock_exec_rtl, mock_pseudo,
        mock_desc, mock_decomp, mock_under, mock_load,
    ):
        """Pipeline must NOT call verify_description in the main pipeline."""
        mock_load.return_value = ([self.mock_doc], self.mock_doc.page_content, [self.mock_doc], [self.mock_doc])
        mock_under.return_value = self.mock_understanding
        mock_decomp.return_value = self.mock_decomposition
        mock_desc.return_value = self.mock_description
        mock_pseudo.return_value = self.mock_pseudocode
        mock_exec_rtl.return_value = self._make_unified_rtl_result()
        mock_verify_rtl.return_value = VerificationResult(valid=True, issues=[], suggestions=[], reasoning="Passed.")

        run_pipeline(self.spec_file, self.output_dir)

        mock_verify_desc.assert_not_called()


if __name__ == "__main__":
    unittest.main()

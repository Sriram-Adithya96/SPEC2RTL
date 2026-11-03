import json
import unittest
from pathlib import Path

from src.agents.pseudocode import SYSTEM_PROMPT


class TestPseudocodeAgentPrompt(unittest.TestCase):
    def test_captured_opcode_instruction_is_present(self):
        normalized = " ".join(SYSTEM_PROMPT.lower().split())
        self.assertIn("captured register values for operation decoding", normalized)
        self.assertIn("live opcode", normalized)

    def test_single_output_driver_instruction_is_present(self):
        normalized = " ".join(SYSTEM_PROMPT.lower().split())
        self.assertIn("assign every combinational output and derived signal exactly once", normalized)
        self.assertIn("do not place the same assign in multiple combinational blocks", normalized)

    def test_register_hygiene_instruction_is_present(self):
        normalized = " ".join(SYSTEM_PROMPT.lower().split())
        self.assertIn("do not create valid_reg, busy_reg", normalized)
        self.assertIn("do not declare registers or signals that are not read", normalized)

    def test_unresolved_and_clock_edge_rules_are_present(self):
        normalized = " ".join(SYSTEM_PROMPT.lower().split())
        self.assertIn("preserve that behavior in unresolved entries", normalized)
        self.assertIn("never assume a clock edge", normalized)
        self.assertIn("preserve it as an unresolved clock requirement", normalized)
        self.assertIn("the example's rising-edge declaration is not evidence", normalized)
        self.assertIn("omit clock metadata and omit every block clocked", normalized)
        self.assertIn("unresolved clock : clock edge -", normalized)

    def test_unspecified_clock_edge_does_not_generate_clocked_assumption(self):
        normalized = " ".join(SYSTEM_PROMPT.lower().split())
        self.assertIn(
            "only when the original specification explicitly defines that edge",
            normalized,
        )
        self.assertIn(
            "if the specification does not define the edge",
            normalized,
        )
        self.assertIn(
            "rather than assuming either edge",
            normalized,
        )

    def test_complete_top_level_structure_allows_omitted_clock(self):
        normalized = " ".join(SYSTEM_PROMPT.lower().split())
        self.assertIn(
            "if the edge is unspecified, omit clock and clocked entirely",
            normalized,
        )
        self.assertIn(
            "clock is optional interface metadata",
            normalized,
        )
        self.assertNotIn(
            "clock <name> edge rising|falling",
            normalized,
        )

    def test_generation_has_no_automatic_regeneration_loop(self):
        source_path = Path("src/agents/pseudocode.py")
        source = source_path.read_text(encoding="utf-8")
        self.assertNotIn("max_attempts = 2", source)
        self.assertNotIn("retry_feedback", source)
        self.assertIn(
            "Requesting pseudocode from the model (single attempt)...",
            source,
        )

    def test_corrected_artifact_has_no_duplicate_saved_output_drivers(self):
        artifact = Path("outputs/pseudocode_raw.txt")
        if not artifact.exists():
            self.skipTest("Corrected pseudocode artifact is not present in this checkout.")

        data = json.loads(artifact.read_text(encoding="utf-8"))
        lines = data["pseudocode"]

        self.assertEqual(
            sum(line.strip().startswith("ASSIGN sel_") for line in lines),
            7,
        )
        self.assertFalse(
            any("valid_reg" in line or "busy_reg" in line for line in lines)
        )
        self.assertIn(
            "  ASSIGN sel_add = (reg_opcode == 4'b0000)",
            lines,
        )
        self.assertFalse(
            any("EDGE RISING" in line or "EDGE FALLING" in line for line in lines)
        )

        output_assignments = {}
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("ASSIGN "):
                target = stripped.split("=", 1)[0].split()[-1]
                output_assignments[target] = output_assignments.get(target, 0) + 1

        for output in ("result", "valid", "busy", "error"):
            self.assertEqual(output_assignments.get(output, 0), 1)


if __name__ == "__main__":
    unittest.main()

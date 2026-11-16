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
        self.assertIn(
            "at most once on every terminal execution path",
            normalized,
        )
        self.assertIn("do not add redundant self-assignments", normalized)

    def test_unresolved_and_clock_edge_rules_are_present(self):
        normalized = " ".join(SYSTEM_PROMPT.lower().split())
        self.assertIn("preserve that behavior in unresolved entries", normalized)
        self.assertIn("never assume a clock edge", normalized)
        self.assertIn("preserve it as an unresolved clock requirement", normalized)
        self.assertIn("the example's rising-edge declaration is not evidence", normalized)
        self.assertIn("omit clock metadata and omit every block clocked", normalized)
        self.assertIn("unresolved clock : clock edge -", normalized)
        self.assertIn(
            "an assumption and an unresolved issue must not contradict each other",
            normalized,
        )
        self.assertIn(
            "do not mark an explicitly defined behavior as unresolved",
            normalized,
        )

    def test_clock_is_not_duplicated_as_an_input(self):
        normalized = " ".join(SYSTEM_PROMPT.lower().split())
        self.assertIn(
            "represent a clock with clock metadata rather than also declaring "
            "that same signal as input",
            normalized,
        )

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

    def test_interface_output_and_decoder_consistency_rules_are_present(self):
        normalized = " ".join(SYSTEM_PROMPT.lower().split())
        self.assertIn(
            "never redeclare an interface signal as reg or sig",
            normalized,
        )
        self.assertIn(
            "every declared output must be driven by a supported assignment",
            normalized,
        )
        self.assertIn(
            "exactly one matching module declaration and end module delimiter",
            normalized,
        )
        self.assertIn(
            "use the decoder's source-supported mapping and exclusivity",
            normalized,
        )
        self.assertIn(
            "leave invalid combinations unresolved rather than implementing "
            "an unsupported priority",
            normalized,
        )

    def test_one_cycle_result_and_status_alignment_is_explicit(self):
        normalized = " ".join(SYSTEM_PROMPT.lower().split())
        self.assertIn("assert valid with the result on the specified following edge", normalized)
        self.assertIn("do not assert valid on capture merely because start was accepted", normalized)
        self.assertIn("do not invent priority for simultaneous events whose priority is unspecified", normalized)

    def test_known_reset_requirements_are_separate_from_missing_clock_edge(self):
        normalized = " ".join(SYSTEM_PROMPT.lower().split())
        self.assertIn("preserve every explicitly specified reset effect and value", normalized)
        self.assertIn("keep that edge unresolved and omit edge-dependent reset logic", normalized)
        self.assertIn("do not replace known reset requirements with an unresolved reset claim", normalized)

    def test_internal_datapath_default_must_be_valid_and_unobservable(self):
        normalized = " ".join(SYSTEM_PROMPT.lower().split())
        self.assertIn("never use x-valued literals such as 32'bx", normalized)
        self.assertIn("width-correct grammar-valid default", normalized)
        self.assertIn("consumers demonstrably ignore that value", normalized)
        self.assertIn("must not define unsupported-opcode result, valid, or error behavior", normalized)

    def test_generation_has_no_automatic_regeneration_loop(self):
        source_path = Path("src/agents/pseudocode.py")
        source = source_path.read_text(encoding="utf-8")
        self.assertNotIn("max_attempts = 2", source)
        self.assertNotIn("retry_feedback", source)
        self.assertIn(
            "Requesting pseudocode from the model (single attempt)...",
            source,
        )

if __name__ == "__main__":
    unittest.main()

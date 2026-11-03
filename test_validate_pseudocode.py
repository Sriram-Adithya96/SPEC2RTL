import unittest

from src.agents.validate_pseudocode import (
    validate_pseudocode,
    validate_pseudocode_detailed,
)


def counter_v1():
    return [
        "MODULE counter",
        "CLOCK clk EDGE RISING",
        "INPUT rst_n",
        "INPUT enable",
        "OUTPUT count[7:0]",
        "REG count_reg[7:0]",
        "",
        "BLOCK COMBINATIONAL",
        "  ASSIGN count = count_reg",
        "END BLOCK",
        "",
        "BLOCK CLOCKED CLOCK clk EDGE RISING",
        "  RESET ASYNCHRONOUS SIGNAL rst_n ACTIVE_LOW VALUE 0",
        "  IF rst_n == 0 THEN",
        "    count_reg <= 8'b00000000",
        "  ELSE",
        "    IF enable == 1 THEN",
        "      count_reg <= count_reg + 8'b00000001",
        "    END IF",
        "  END IF",
        "END BLOCK",
        "END MODULE",
    ]


def fsm_v1():
    return [
        "MODULE fsm",
        "CLOCK clk EDGE RISING",
        "INPUT rst",
        "INPUT start",
        "OUTPUT busy",
        "REG state[1:0]",
        "REG busy_reg",
        "SIG busy_next",
        "",
        "STATE IDLE",
        "STATE BUSY",
        "STATE DONE",
        "",
        "BLOCK COMBINATIONAL",
        "  ASSIGN busy_next = busy_reg",
        "  ASSIGN busy = busy_reg",
        "END BLOCK",
        "",
        "BLOCK CLOCKED CLOCK clk EDGE RISING",
        "  RESET SYNCHRONOUS SIGNAL rst ACTIVE_HIGH VALUE 1",
        "  IF rst == 1 THEN",
        "    state <= IDLE",
        "    busy_reg <= 0",
        "  ELSE",
        "    CASE state",
        "      WHEN IDLE:",
        "        IF start == 1 THEN",
        "          state <= BUSY",
        "          busy_reg <= 1",
        "        END IF",
        "      WHEN BUSY:",
        "        state <= DONE",
        "        busy_reg <= 0",
        "      WHEN DONE:",
        "        state <= IDLE",
        "      WHEN DEFAULT:",
        "        state <= IDLE",
        "        busy_reg <= 0",
        "    END CASE",
        "  END IF",
        "END BLOCK",
        "END MODULE",
    ]


def nested_case_function_v1():
    return [
        "MODULE alu",
        "CLOCK clk EDGE RISING",
        "INPUT operand_a[31:0]",
        "INPUT operand_b[31:0]",
        "INPUT opcode[3:0]",
        "OUTPUT result[31:0]",
        "REG result_reg[31:0]",
        "",
        "FUNCTION alu_compute(a[31:0], b[31:0], op[3:0]) -> (out[31:0], err):",
        "  SET out = 32'b00000000000000000000000000000000",
        "  SET err = 1'b0",
        "  CASE op",
        "    WHEN 4'b0000:",
        "      SET out = a + b",
        "      SET err = 1'b0",
        "    WHEN 4'b0010:",
        "      IF b[31:0] == 32'b00000000000000000000000000000000 THEN",
        "        SET out = 32'b00000000000000000000000000000000",
        "        SET err = 1'b1",
        "      ELSE",
        "        SET out = a & b",
        "        SET err = 1'b0",
        "      END IF",
        "    WHEN DEFAULT:",
        "      SET out = 32'b00000000000000000000000000000000",
        "      SET err = 1'b1",
        "  END CASE",
        "  RETURN (out, err)",
        "END FUNCTION",
        "",
        "BLOCK COMBINATIONAL",
        "  ASSIGN result = result_reg",
        "END BLOCK",
        "END MODULE",
    ]


def traffic_light_v1():
    return [
        "MODULE TrafficLightController",
        "CLOCK clk EDGE RISING",
        "INPUT car",
        "INPUT pedestrian",
        "INPUT T60",
        "INPUT T30",
        "INPUT T10",
        "OUTPUT rh",
        "OUTPUT yh",
        "OUTPUT gh",
        "OUTPUT rs",
        "OUTPUT ys",
        "OUTPUT gs",
        "REG state[2:0]",
        "SIG highway_request",
        "STATE HWY_GREEN",
        "STATE HWY_YELLOW",
        "STATE HWY_RED",
        "STATE SRD_GREEN",
        "STATE SRD_YELLOW",
        "",
        "BLOCK COMBINATIONAL",
        "  ASSIGN rh = 0",
        "  ASSIGN yh = 0",
        "  ASSIGN gh = 0",
        "  ASSIGN rs = 0",
        "  ASSIGN ys = 0",
        "  ASSIGN gs = 0",
        "END BLOCK",
        "",
        "BLOCK CLOCKED CLOCK clk EDGE RISING",
        "  RESET NOT SPECIFIED",
        "  END RESET",
        "  CASE state",
        "    WHEN HWY_GREEN:",
        "      IF T60 == 1 THEN",
        "        IF car == 1 THEN",
        "          state <= HWY_YELLOW",
        "        END IF",
        "      END IF",
        "    WHEN HWY_YELLOW:",
        "      IF T10 == 1 THEN",
        "        state <= HWY_RED",
        "      END IF",
        "    WHEN HWY_RED:",
        "      IF pedestrian == 1 THEN",
        "        state <= SRD_GREEN",
        "      ELSE",
        "        state <= HWY_GREEN",
        "      END IF",
        "    WHEN SRD_GREEN:",
        "      IF T30 == 1 THEN",
        "        state <= SRD_YELLOW",
        "      END IF",
        "    WHEN SRD_YELLOW:",
        "      IF T10 == 1 THEN",
        "        state <= HWY_GREEN",
        "      END IF",
        "    WHEN DEFAULT:",
        "      state <= HWY_GREEN",
        "  END CASE",
        "END BLOCK",
        "UNRESOLVED RESET : reset behavior - reset type, polarity, and reset value are unspecified",
        "UNRESOLVED TIMING : pedestrian behavior - ambiguous simultaneous or priority behavior is unspecified",
        "END MODULE",
    ]


class TestValidatorGrammarV1(unittest.TestCase):
    def assert_valid(self, code, **context):
        errors = validate_pseudocode(code, **context)
        self.assertEqual(errors, [], errors)

    def test_valid_counter_passes(self):
        self.assert_valid(counter_v1())

    def test_valid_fsm_passes(self):
        self.assert_valid(fsm_v1())

    def test_valid_nested_case_function_passes(self):
        self.assert_valid(nested_case_function_v1())

    def test_unbalanced_if_is_rejected(self):
        code = counter_v1()
        code.remove("  END IF")
        errors = validate_pseudocode(code)
        self.assertTrue(any("IF/END IF mismatch" in error for error in errors))

    def test_unbalanced_case_is_rejected(self):
        code = fsm_v1()
        code.remove("    END CASE")
        errors = validate_pseudocode(code)
        self.assertTrue(any("CASE/END CASE mismatch" in error for error in errors))

    def test_unbalanced_clocked_block_is_rejected(self):
        code = counter_v1()
        code.remove("END BLOCK")
        errors = validate_pseudocode(code)
        self.assertTrue(any("Clocked or combinational block mismatch" in error for error in errors))

    def test_clock_edge_must_match_top_level_declaration(self):
        code = counter_v1()
        code[code.index("BLOCK CLOCKED CLOCK clk EDGE RISING")] = (
            "BLOCK CLOCKED CLOCK clk EDGE FALLING"
        )
        errors = validate_pseudocode(code)
        self.assertTrue(any("CLOCK_EDGE_MISMATCH" not in error for error in errors))

        result = validate_pseudocode_detailed(code)
        codes = {issue.code for issue in result.issues}
        self.assertIn("CLOCK_EDGE_MISMATCH", codes)

    def test_clock_and_input_duplicate_is_rejected(self):
        code = counter_v1()
        code.insert(3, "INPUT clk")
        result = validate_pseudocode_detailed(code)
        codes = {issue.code for issue in result.issues}
        self.assertIn("CLOCK_INPUT_DUPLICATE_DECLARATION", codes)

    def test_duplicate_names_are_rejected(self):
        code = counter_v1()
        code.insert(4, "REG count_reg")
        result = validate_pseudocode_detailed(code)
        codes = {issue.code for issue in result.issues}
        self.assertIn("DUPLICATE_DECLARATION", codes)

    def test_internal_clock_interface_is_rejected(self):
        code = counter_v1()
        code.remove("CLOCK clk EDGE RISING")
        code.insert(2, "INPUT clk")
        result = validate_pseudocode_detailed(code)
        codes = {issue.code for issue in result.issues}
        self.assertIn("CLOCKED_BLOCK_UNKNOWN_CLOCK", codes)

    def test_clocked_assignment_must_use_nonblocking_operator(self):
        code = counter_v1()
        code = [line.replace("count_reg <= count_reg + 8'b00000001", "count_reg = count_reg + 8'b00000001") for line in code]
        result = validate_pseudocode_detailed(code)
        codes = {issue.code for issue in result.issues}
        self.assertIn("CLOCKED_ASSIGNMENT_OPERATOR", codes)

    def test_combinational_assignment_must_use_blocking_operator(self):
        code = counter_v1()
        code = [line.replace("ASSIGN count = count_reg", "ASSIGN count <= count_reg") for line in code]
        result = validate_pseudocode_detailed(code)
        codes = {issue.code for issue in result.issues}
        self.assertIn("COMBINATIONAL_ASSIGNMENT_OPERATOR", codes)

    def test_assign_outside_combinational_is_rejected(self):
        code = counter_v1()
        code.insert(len(code) - 1, "ASSIGN count = count_reg")
        result = validate_pseudocode_detailed(code)
        codes = {issue.code for issue in result.issues}
        self.assertIn("ASSIGN_OUTSIDE_COMBINATIONAL_BLOCK", codes)

    def test_reset_not_specified_requires_unresolved(self):
        code = counter_v1()
        code = [
            line.replace(
                "  RESET ASYNCHRONOUS SIGNAL rst_n ACTIVE_LOW VALUE 0",
                "  RESET NOT SPECIFIED",
            )
            if line.strip() == "RESET ASYNCHRONOUS SIGNAL rst_n ACTIVE_LOW VALUE 0"
            else line
            for line in code
        ]
        reset_index = code.index("  RESET NOT SPECIFIED")
        code.insert(reset_index + 1, "END RESET")
        code.append("UNRESOLVED RESET : reset behavior - reset type, polarity, and value are unspecified")
        result = validate_pseudocode_detailed(code)
        self.assertEqual(
            {issue.code for issue in result.issues}.intersection({"RESET_NOT_SPECIFIED_MISSING_UNRESOLVED"}),
            set(),
        )

        no_entry = [line for line in code if not line.startswith("UNRESOLVED ")]
        result = validate_pseudocode_detailed(no_entry)
        self.assertIn(
            "RESET_NOT_SPECIFIED_MISSING_UNRESOLVED",
            {issue.code for issue in result.issues},
        )

    def test_function_missing_return_is_rejected(self):
        code = nested_case_function_v1()
        code = [line for line in code if not line.strip().startswith("RETURN")]
        result = validate_pseudocode_detailed(code)
        codes = {issue.code for issue in result.issues}
        self.assertIn("FUNCTION_RETURN_MISSING", codes)

    def test_function_return_must_be_terminal_and_unique(self):
        code = nested_case_function_v1()
        end_function_index = code.index("END FUNCTION")
        code.insert(end_function_index, "  RETURN (out, err)")
        result = validate_pseudocode_detailed(code)
        codes = {issue.code for issue in result.issues}
        self.assertIn("FUNCTION_RETURN_COUNT", codes)

    def test_case_requires_default_in_examples(self):
        code = fsm_v1()
        code.remove("      WHEN DEFAULT:")
        code.remove("        state <= IDLE")
        code.remove("        busy_reg <= 0")
        result = validate_pseudocode_detailed(code)
        codes = {issue.code for issue in result.issues}
        self.assertIn("CASE_DEFAULT_MISSING", codes)

    def test_unresolved_syntax_is_validated(self):
        code = counter_v1() + ["UNRESOLVED TIMING : ready - latency unspecified"]
        result = validate_pseudocode_detailed(code)
        codes = {issue.code for issue in result.issues}
        self.assertIn("UNRESOLVED_REQUIREMENT_BLOCKS_RTL", codes)

        bad = counter_v1() + ["UNRESOLVED ready latency unspecified"]
        result = validate_pseudocode_detailed(bad)
        self.assertIn("INVALID_UNRESOLVED_SYNTAX", {issue.code for issue in result.issues})

    def test_cdc_sync_reg_validated_for_clock_and_stage(self):
        code = counter_v1() + [
            "CLOCK dst_clk EDGE RISING",
            "SIG sync_flag",
            "CDC_SYNC_REG sync_flag FROM clk TO dst_clk STAGES 2",
        ]
        result = validate_pseudocode_detailed(
            code,
            understanding={
                "constraints": ["A CDC synchronizer is required between clk and dst_clk."],
            },
        )
        self.assertTrue(
            "CDC_SYNC_REG" in " ".join(line for line in code)
        )
        codes = {issue.code for issue in result.issues}
        self.assertNotIn("CDC_CLOCKS_NOT_DISTINCT", codes)

    def test_cdc_sync_reg_rejects_same_clock_and_bad_stages(self):
        code = counter_v1() + [
            "SIG sync_flag",
            "CDC_SYNC_REG sync_flag FROM clk TO clk STAGES 0",
        ]
        result = validate_pseudocode_detailed(code)
        codes = {issue.code for issue in result.issues}
        self.assertIn("CDC_CLOCKS_NOT_DISTINCT", codes)
        self.assertIn("CDC_INVALID_STAGE_COUNT", codes)

    def test_cdc_handshake_requires_distinct_declared_clocks(self):
        code = counter_v1() + [
            "CLOCK dst_clk EDGE RISING",
            "REG request_reg",
            "CDC_HANDSHAKE request_reg FROM clk TO dst_clk",
        ]
        result = validate_pseudocode_detailed(
            code,
            understanding={
                "constraints": ["Use a clock-domain handshake between clk and dst_clk."],
            },
        )
        codes = {issue.code for issue in result.issues}
        self.assertNotIn("CDC_CLOCK_UNDECLARED", codes)
        self.assertNotIn("CDC_CLOCKS_NOT_DISTINCT", codes)

    def test_specification_aware_missing_interface_is_blocking(self):
        result = validate_pseudocode_detailed(
            counter_v1(),
            understanding={
                "inputs": ["enable: input enable signal"],
                "outputs": ["count: 8-bit output"],
                "constraints": [
                    "clk is a rising-edge clock.",
                    "rst_n is an asynchronous active-low reset.",
                    "Reset behavior is active-low and asynchronous.",
                ],
                "ambiguities": [],
            },
        )
        self.assertTrue(result.valid)

        result = validate_pseudocode_detailed(
            counter_v1(),
            understanding={
                "inputs": ["enable", "clear: 1-bit clear input"],
                "outputs": ["count"],
                "constraints": [],
                "ambiguities": [],
            },
        )
        codes = {issue.code for issue in result.issues}
        self.assertIn("INTERFACE_MISSING_FROM_UNDERSTANDING", codes)

    def test_binary_literal_typo_is_rejected(self):
        code = counter_v1()
        code = [
            line.replace("8'b00000000", "8b00000000")
            if "8'b00000000" in line
            else line
            for line in code
        ]
        result = validate_pseudocode_detailed(code)
        self.assertIn(
            "INVALID_BINARY_LITERAL",
            {issue.code for issue in result.issues},
        )

    def test_structured_result_and_legacy_wrapper_match_validity(self):
        code = counter_v1()
        detailed = validate_pseudocode_detailed(code)
        legacy_errors = validate_pseudocode(code)
        self.assertEqual(detailed.valid, not legacy_errors)

    def test_valid_grammar_v1_traffic_light_fixture_passes_structure(self):
        result = validate_pseudocode_detailed(
            traffic_light_v1(),
            understanding={
                "inputs": ["clk", "car", "pedestrian", "T60", "T30", "T10"],
                "outputs": ["rh", "yh", "gh", "rs", "ys", "gs"],
                "constraints": [
                    "The highway remains priority over the side road.",
                    "External timer inputs T60, T30, and T10 provide elapsed-time conditions.",
                ],
                "ambiguities": [
                    "Reset polarity and reset type are not specified.",
                    "Pedestrian behavior during ambiguous requests is not specified.",
                ],
            },
        )
        codes = {issue.code for issue in result.blocking_issues}
        self.assertIn("UNRESOLVED_REQUIREMENT_BLOCKS_RTL", codes)
        self.assertNotIn("LEGACY_CLOCKED_SYNTAX", codes)
        self.assertNotIn("LEGACY_CASE_OF_SYNTAX", codes)
        self.assertNotIn("LEGACY_DECLARATION_SEMICOLON", codes)
        self.assertFalse(result.valid)

    def test_legacy_clocked_syntax_is_rejected(self):
        code = counter_v1()
        code = [
            line.replace("BLOCK CLOCKED CLOCK clk EDGE RISING", "ON RISING EDGE OF clk")
            .replace("END BLOCK", "END ON")
            if line.strip() in {"BLOCK CLOCKED CLOCK clk EDGE RISING", "END BLOCK"}
            else line
            for line in code
        ]
        result = validate_pseudocode_detailed(code)
        codes = {issue.code for issue in result.issues}
        self.assertTrue(
            {"LEGACY_CLOCKED_SYNTAX", "LEGACY_CLOCKED_END"}.intersection(codes)
        )

    def test_legacy_declaration_and_case_syntax_are_rejected(self):
        code = traffic_light_v1()
        code[code.index("REG state[2:0]")] = "REG state[2:0];"
        code[code.index("  CASE state")] = "CASE state OF"
        result = validate_pseudocode_detailed(code)
        codes = {issue.code for issue in result.issues}
        self.assertIn("LEGACY_DECLARATION_SEMICOLON", codes)
        self.assertIn("LEGACY_CASE_OF_SYNTAX", codes)

    def test_case_colon_is_rejected(self):
        code = fsm_v1()
        code = [line.replace("    CASE state", "    CASE state:") for line in code]
        result = validate_pseudocode_detailed(code)
        self.assertIn(
            "CASE_COLON_NOT_ALLOWED",
            {issue.code for issue in result.issues},
        )

    def test_supported_reset_assumption_must_match_understanding(self):
        result = validate_pseudocode_detailed(
            counter_v1(),
            understanding={
                "inputs": ["clk", "rst_n", "enable"],
                "outputs": ["count"],
                "constraints": [
                    "clk is rising-edge.",
                    "reset behavior is synchronous active-low.",
                ],
                "ambiguities": [],
            },
        )
        self.assertIn(
            "RESET_SPECIFICATION_UNSUPPORTED",
            {issue.code for issue in result.issues},
        )

    def test_malformed_clock_syntax_is_rejected(self):
        for line in ("CLOCK clk RISING", "CLOCK clk FALLING", "CLOCK clk EDGE BOTH"):
            code = counter_v1()
            code[1] = line
            result = validate_pseudocode_detailed(code)
            self.assertIn("INVALID_CLOCK_DECLARATION", {issue.code for issue in result.issues})

    def test_combinational_block_extra_text_is_rejected(self):
        code = counter_v1()
        code[code.index("BLOCK COMBINATIONAL")] = "BLOCK COMBINATIONAL junk"
        result = validate_pseudocode_detailed(code)
        self.assertIn("INVALID_BLOCK_DECLARATION", {issue.code for issue in result.issues})

    def test_clocked_block_extra_text_is_rejected(self):
        code = counter_v1()
        code[code.index("BLOCK CLOCKED CLOCK clk EDGE RISING")] = "BLOCK CLOCKED CLOCK clk EDGE RISING junk"
        result = validate_pseudocode_detailed(code)
        self.assertIn("INVALID_BLOCK_DECLARATION", {issue.code for issue in result.issues})

    def test_when_branch_requires_colon(self):
        for branch in ("WHEN IDLE", "WHEN DEFAULT", "WHEN IDLE trailing"):
            code = fsm_v1()
            code = [line.replace("WHEN IDLE:", branch) if "WHEN IDLE:" in line else line.replace("WHEN DEFAULT:", branch) if "WHEN DEFAULT:" in line else line for line in code]
            result = validate_pseudocode_detailed(code)
            self.assertIn("INVALID_WHEN_SYNTAX", {issue.code for issue in result.issues})

    def test_reset_outside_clocked_block_is_rejected(self):
        code = ["MODULE m", "CLOCK clk EDGE RISING", "RESET SYNCHRONOUS SIGNAL rst ACTIVE_HIGH VALUE 0", "END MODULE"]
        result = validate_pseudocode_detailed(code)
        self.assertIn("RESET_OUTSIDE_CLOCKED_BLOCK", {issue.code for issue in result.issues})

    def test_incomplete_reset_is_rejected(self):
        code = counter_v1()
        code[code.index("  RESET ASYNCHRONOUS SIGNAL rst_n ACTIVE_LOW VALUE 0")] = "  RESET ASYNCHRONOUS SIGNAL rst_n"
        result = validate_pseudocode_detailed(code)
        self.assertIn("RESET_DETAILS_INCOMPLETE", {issue.code for issue in result.issues})

    def test_combinational_if_missing_different_target_is_rejected(self):
        code = counter_v1()
        start = code.index("BLOCK COMBINATIONAL")
        end = code.index("END BLOCK", start)
        code[start + 1:end] = [
            "  ASSIGN count = count_reg",
            "  IF enable == 1 THEN",
            "    ASSIGN count = count_reg",
            "  ELSE",
            "    ASSIGN enable = 0",
            "  END IF",
        ]
        result = validate_pseudocode_detailed(code)
        self.assertIn("COMBINATIONAL_PATH_INCOMPLETE", {issue.code for issue in result.issues})

    def test_clocked_duplicate_in_one_branch_is_rejected(self):
        code = counter_v1()
        clock_start = code.index("BLOCK CLOCKED CLOCK clk EDGE RISING")
        clock_end = code.index("END BLOCK", clock_start)
        code[clock_start + 1:clock_end] = [
            "  IF enable == 1 THEN",
            "    count_reg <= 8'b00000001",
            "    count_reg <= 8'b00000010",
            "  END IF",
        ]
        result = validate_pseudocode_detailed(code)
        self.assertIn("MULTIPLE_CLOCKED_ASSIGNMENTS", {issue.code for issue in result.issues})

    def test_clocked_assignments_in_mutually_exclusive_branches_are_valid(self):
        code = counter_v1()
        clock_start = code.index("BLOCK CLOCKED CLOCK clk EDGE RISING")
        clock_end = code.index("END BLOCK", clock_start)
        code[clock_start + 1:clock_end] = [
            "  RESET NOT SPECIFIED",
            "  END RESET",
            "  IF enable == 1 THEN",
            "    count_reg <= 8'b00000001",
            "  ELSE",
            "    count_reg <= 8'b00000010",
            "  END IF",
        ]
        code.append("UNRESOLVED RESET : reset behavior - reset type, polarity, and value unspecified")
        result = validate_pseudocode_detailed(code, understanding={
            "inputs": ["clk", "rst_n", "enable"],
            "outputs": ["count"],
            "constraints": [],
            "ambiguities": ["Reset polarity and reset type are not specified."],
        })
        self.assertNotIn("MULTIPLE_CLOCKED_ASSIGNMENTS", {issue.code for issue in result.issues})

    def test_cdc_requires_specification_or_understanding_evidence(self):
        code = counter_v1() + [
            "CLOCK dst_clk EDGE RISING",
            "SIG sync_flag",
            "CDC_SYNC_REG sync_flag FROM clk TO dst_clk STAGES 2",
        ]
        result = validate_pseudocode_detailed(code)
        self.assertIn("CDC_SPECIFICATION_UNSUPPORTED", {issue.code for issue in result.issues})

        result = validate_pseudocode_detailed(
            code,
            specification="The design requires a clock-domain synchronizer between clk and dst_clk.",
        )
        self.assertNotIn("CDC_SPECIFICATION_UNSUPPORTED", {issue.code for issue in result.issues})

    def test_specification_evidence_is_used_without_understanding(self):
        result = validate_pseudocode_detailed(
            counter_v1(),
            specification="clk rising edge; rst_n asynchronous active-low reset; enable input; 8-bit count output",
        )
        self.assertNotIn("INTERFACE_UNSUPPORTED_BY_SPECIFICATION", {issue.code for issue in result.issues})

    def test_ambiguity_must_match_relevant_unresolved(self):
        code = counter_v1() + [
            "UNRESOLVED TIMING : latency - clock latency unspecified"
        ]
        result = validate_pseudocode_detailed(code, understanding={
            "inputs": ["clk", "rst_n", "enable"],
            "outputs": ["count"],
            "constraints": [],
            "ambiguities": ["Reset polarity and reset type are not specified."],
        })
        self.assertIn("AMBIGUITY_UNRESOLVED_MISMATCH", {issue.code for issue in result.issues})

    def test_function_nested_missing_return_branch_is_rejected(self):
        code = nested_case_function_v1()
        code.remove("  SET err = 1'b0")
        code.remove("      SET err = 1'b0")
        result = validate_pseudocode_detailed(code)
        self.assertIn("FUNCTION_RETURN_PATH_INCOMPLETE", {issue.code for issue in result.issues})


if __name__ == "__main__":
    unittest.main(verbosity=2)

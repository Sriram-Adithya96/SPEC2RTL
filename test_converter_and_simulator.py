import importlib.util
import unittest
from pathlib import Path

from src.agents.apu_simulator import APUSimulator
from src.agents.pseudocode_to_python import convert_pseudocode


def load_generated_module(pseudocode):
    python_code = convert_pseudocode(pseudocode)
    spec = importlib.util.spec_from_loader("dynamic_generated_apu", loader=None)
    module = importlib.util.module_from_spec(spec)
    exec(python_code, module.__dict__)
    return module


class TestConverterAndSimulator(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        fixture_path = (
            Path(__file__).parent
            / "fixtures"
            / "legacy_apu_simulation.pseudo"
        )
        cls.pseudocode = fixture_path.read_text(encoding="utf-8").splitlines()
        cls.gen_module = load_generated_module(cls.pseudocode)

    def setUp(self):
        self.sim = APUSimulator()
        # Reset the generated python module
        self.gen_module.rising_edge(rst_n=0)
        self.sim.rising_edge(rst_n=0)

    def step_both(self, rst_n, start=0, operand_a=0, operand_b=0, opcode=0):
        self.sim.rising_edge(
            rst_n=rst_n,
            start=start,
            operand_a=operand_a,
            operand_b=operand_b,
            opcode=opcode,
        )
        self.gen_module.rising_edge(
            rst_n=rst_n,
            start=start,
            operand_a=operand_a,
            operand_b=operand_b,
            opcode=opcode,
        )
        # Check cycle-by-cycle equivalence
        self.assertEqual(self.sim.result, self.gen_module.result, f"Result mismatch: sim={self.sim.result}, gen={self.gen_module.result}")
        self.assertEqual(self.sim.valid, self.gen_module.valid, f"Valid mismatch: sim={self.sim.valid}, gen={self.gen_module.valid}")
        self.assertEqual(self.sim.busy, self.gen_module.busy, f"Busy mismatch: sim={self.sim.busy}, gen={self.gen_module.busy}")
        self.assertEqual(self.sim.error, self.gen_module.error, f"Error mismatch: sim={self.sim.error}, gen={self.gen_module.error}")

    def test_addition_normal_and_overflow(self):
        # 10 + 20 = 30
        self.step_both(rst_n=1, start=1, operand_a=10, operand_b=20, opcode=0)
        self.assertEqual(self.sim.busy, 1)
        self.assertEqual(self.sim.valid, 0)
        self.step_both(rst_n=1)
        self.assertEqual(self.sim.result, 30)
        self.assertEqual(self.sim.valid, 1)
        self.assertEqual(self.sim.busy, 0)
        self.assertEqual(self.sim.error, 0)

        # Overflow: 0xFFFFFFFF + 1 = 0
        self.step_both(rst_n=1, start=1, operand_a=0xFFFFFFFF, operand_b=1, opcode=0)
        self.step_both(rst_n=1)
        self.assertEqual(self.sim.result, 0)
        self.assertEqual(self.sim.valid, 1)

        # Overflow: 0xFFFFFFFF + 5 = 4
        self.step_both(rst_n=1, start=1, operand_a=0xFFFFFFFF, operand_b=5, opcode=0)
        self.step_both(rst_n=1)
        self.assertEqual(self.sim.result, 4)
        self.assertEqual(self.sim.valid, 1)

    def test_subtraction_normal_and_underflow(self):
        # 50 - 20 = 30
        self.step_both(rst_n=1, start=1, operand_a=50, operand_b=20, opcode=1)
        self.step_both(rst_n=1)
        self.assertEqual(self.sim.result, 30)
        self.assertEqual(self.sim.valid, 1)

        # Underflow: 0 - 1 = 0xFFFFFFFF (4294967295)
        self.step_both(rst_n=1, start=1, operand_a=0, operand_b=1, opcode=1)
        self.step_both(rst_n=1)
        self.assertEqual(self.sim.result, 0xFFFFFFFF)
        self.assertEqual(self.sim.valid, 1)

        # Underflow: 10 - 20 = 4294967286
        self.step_both(rst_n=1, start=1, operand_a=10, operand_b=20, opcode=1)
        self.step_both(rst_n=1)
        self.assertEqual(self.sim.result, 4294967286)
        self.assertEqual(self.sim.valid, 1)

    def test_bitwise_operations(self):
        # AND (opcode 2)
        self.step_both(rst_n=1, start=1, operand_a=0xFF00FF00, operand_b=0xFFFF0000, opcode=2)
        self.step_both(rst_n=1)
        self.assertEqual(self.sim.result, 0xFF000000)
        self.assertEqual(self.sim.valid, 1)

        # OR (opcode 3)
        self.step_both(rst_n=1, start=1, operand_a=0x00FF00FF, operand_b=0xFF00FF00, opcode=3)
        self.step_both(rst_n=1)
        self.assertEqual(self.sim.result, 0xFFFFFFFF)
        self.assertEqual(self.sim.valid, 1)

        # XOR (opcode 4)
        self.step_both(rst_n=1, start=1, operand_a=0xAAAAAAAA, operand_b=0x55555555, opcode=4)
        self.step_both(rst_n=1)
        self.assertEqual(self.sim.result, 0xFFFFFFFF)
        self.assertEqual(self.sim.valid, 1)

    def test_left_and_right_shifts(self):
        # SLL (opcode 5): 1 << 4 = 16
        self.step_both(rst_n=1, start=1, operand_a=1, operand_b=4, opcode=5)
        self.step_both(rst_n=1)
        self.assertEqual(self.sim.result, 16)
        self.assertEqual(self.sim.valid, 1)

        # SLL 32-bit wrap: 0x80000000 << 1 = 0
        self.step_both(rst_n=1, start=1, operand_a=0x80000000, operand_b=1, opcode=5)
        self.step_both(rst_n=1)
        self.assertEqual(self.sim.result, 0)
        self.assertEqual(self.sim.valid, 1)

        # SRL (opcode 6): 64 >> 2 = 16
        self.step_both(rst_n=1, start=1, operand_a=64, operand_b=2, opcode=6)
        self.step_both(rst_n=1)
        self.assertEqual(self.sim.result, 16)
        self.assertEqual(self.sim.valid, 1)

    def test_shift_amount_uses_lower_5_bits(self):
        # SLL with operand_b = 36 (36 & 0x1F = 4): 1 << 4 = 16
        self.step_both(rst_n=1, start=1, operand_a=1, operand_b=36, opcode=5)
        self.step_both(rst_n=1)
        self.assertEqual(self.sim.result, 16)

        # SRL with operand_b = 36 (36 & 0x1F = 4): 64 >> 4 = 4
        self.step_both(rst_n=1, start=1, operand_a=64, operand_b=36, opcode=6)
        self.step_both(rst_n=1)
        self.assertEqual(self.sim.result, 4)

        # SLL with operand_b = 0xFFFFFFE4 (0xFFFFFFE4 & 0x1F = 4)
        self.step_both(rst_n=1, start=1, operand_a=1, operand_b=0xFFFFFFE4, opcode=5)
        self.step_both(rst_n=1)
        self.assertEqual(self.sim.result, 16)

    def test_unsupported_opcodes(self):
        for op in [7, 8, 15]:
            self.step_both(rst_n=1, start=1, operand_a=10, operand_b=20, opcode=op)
            self.step_both(rst_n=1)
            self.assertEqual(self.sim.error, 1, f"Expected error=1 for opcode {op}")
            self.assertEqual(self.sim.valid, 1)
            self.assertEqual(self.sim.result, 0)

    def test_operand_masking(self):
        # Operands exceeding 32-bit width should be masked to 32 bits
        self.step_both(rst_n=1, start=1, operand_a=0x100000005, operand_b=0x200000003, opcode=0)
        self.step_both(rst_n=1)
        self.assertEqual(self.sim.result, 8)

    def test_synchronous_active_low_reset(self):
        # Start an operation
        self.step_both(rst_n=1, start=1, operand_a=10, operand_b=20, opcode=0)
        self.assertEqual(self.sim.busy, 1)

        # Reset active low at rising edge
        self.step_both(rst_n=0, start=1, operand_a=5, operand_b=5, opcode=0)
        self.assertEqual(self.sim.result, 0)
        self.assertEqual(self.sim.valid, 0)
        self.assertEqual(self.sim.busy, 0)
        self.assertEqual(self.sim.error, 0)

        # Normal operation must not execute while rst_n == 0
        self.step_both(rst_n=0, start=1, operand_a=5, operand_b=5, opcode=0)
        self.assertEqual(self.sim.busy, 0)
        self.assertEqual(self.sim.valid, 0)

    def test_start_while_busy_is_ignored(self):
        # Start operation 1 (takes 1 cycle latency)
        self.step_both(rst_n=1, start=1, operand_a=10, operand_b=20, opcode=0)
        self.assertEqual(self.sim.busy, 1)

        # Try to start operation 2 while busy
        self.step_both(rst_n=1, start=1, operand_a=99, operand_b=99, opcode=0)
        # Operation 1 completes
        self.assertEqual(self.sim.result, 30)
        self.assertEqual(self.sim.valid, 1)
        self.assertEqual(self.sim.busy, 0)

        # Verify operation 2 was not accepted while busy
        self.step_both(rst_n=1, start=0)
        self.assertEqual(self.sim.valid, 0)
        self.assertNotEqual(self.sim.result, 198)

    def test_one_cycle_valid_and_clearing_stale_error(self):
        # Trigger unsupported opcode
        self.step_both(rst_n=1, start=1, operand_a=5, operand_b=5, opcode=9)
        self.step_both(rst_n=1)
        self.assertEqual(self.sim.valid, 1)
        self.assertEqual(self.sim.error, 1)

        # Next cycle: valid and error must be cleared (1-cycle pulse)
        self.step_both(rst_n=1)
        self.assertEqual(self.sim.valid, 0)
        self.assertEqual(self.sim.error, 0)

    def test_back_to_back_requests(self):
        # Op 1: 10 + 20
        self.step_both(rst_n=1, start=1, operand_a=10, operand_b=20, opcode=0)
        self.assertEqual(self.sim.busy, 1)
        self.assertEqual(self.sim.valid, 0)

        # Cycle 2: Op 1 completes, asserting valid=1 and returning busy=0
        self.step_both(rst_n=1, start=0)
        self.assertEqual(self.sim.result, 30)
        self.assertEqual(self.sim.valid, 1)
        self.assertEqual(self.sim.busy, 0)

        # Cycle 3: Op 2 immediately starts: 50 - 15 = 35
        self.step_both(rst_n=1, start=1, operand_a=50, operand_b=15, opcode=1)
        self.assertEqual(self.sim.busy, 1)
        self.assertEqual(self.sim.valid, 0)

        # Cycle 4: Op 2 completes
        self.step_both(rst_n=1, start=0)
        self.assertEqual(self.sim.result, 35)
        self.assertEqual(self.sim.valid, 1)
        self.assertEqual(self.sim.busy, 0)

        # Cycle 5: idle
        self.step_both(rst_n=1, start=0)
        self.assertEqual(self.sim.valid, 0)
        self.assertEqual(self.sim.busy, 0)

    def test_sequential_if_old_state_semantics(self):
        """
        Verify that sequential IF statements in pseudocode:
          IF start == 1 AND busy_reg == 0 THEN state = EXEC ... END IF
          IF state == EXEC THEN ... END IF
        do not trigger 0-cycle execution in the Python simulation.
        """
        pseudo = [
            "REG state : {IDLE, EXEC}",
            "REG operand_a_reg[31:0]",
            "REG operand_b_reg[31:0]",
            "REG opcode_reg[3:0]",
            "REG result_reg[31:0]",
            "REG busy_reg",
            "REG valid_reg",
            "REG error_reg",
            "FUNCTION alu_compute(a[31:0], b[31:0], op[3:0]) -> (out[31:0], err):",
            "  CASE op:",
            "    4'b0000: out = (a + b) MOD 2^32; err = 0",
            "    DEFAULT: out = 32'b0; err = 1",
            "  END CASE",
            "  RETURN (out, err)",
            "END FUNCTION",
            "ON RISING EDGE OF clk",
            "  IF rst_n == 0 THEN",
            "    state = IDLE",
            "    result_reg = 0",
            "    valid_reg = 0",
            "    busy_reg = 0",
            "    error_reg = 0",
            "  ELSE",
            "    valid_reg = 0",
            "    IF start == 1 AND busy_reg == 0 THEN",
            "      operand_a_reg = operand_a",
            "      operand_b_reg = operand_b",
            "      opcode_reg = opcode",
            "      busy_reg = 1",
            "      state = EXEC",
            "    END IF",
            "    IF state == EXEC THEN",
            "      (result_reg, error_reg) = alu_compute(operand_a_reg, operand_b_reg, opcode_reg)",
            "      valid_reg = 1",
            "      busy_reg = 0",
            "      state = IDLE",
            "    END IF",
            "  END IF",
            "END ON",
            "result = result_reg",
            "valid = valid_reg",
            "busy = busy_reg",
            "error = error_reg",
        ]
        mod = load_generated_module(pseudo)
        # Reset
        mod.rising_edge(rst_n=0)
        self.assertEqual(mod.valid, 0)
        self.assertEqual(mod.busy, 0)

        # Cycle 1: Start 10 + 20
        mod.rising_edge(rst_n=1, start=1, operand_a=10, operand_b=20, opcode=0)
        # MUST be busy=1 and valid=0 (NOT 0-cycle completion!)
        self.assertEqual(mod.busy, 1, "Must be busy during execution cycle")
        self.assertEqual(mod.valid, 0, "Must NOT complete in the acceptance cycle (0 latency)")

        # Cycle 2: Op completes
        mod.rising_edge(rst_n=1, start=0)
        self.assertEqual(mod.result, 30)
        self.assertEqual(mod.valid, 1)
        self.assertEqual(mod.busy, 0)

        # Cycle 3: valid cleared on next cycle
        mod.rising_edge(rst_n=1, start=0)
        self.assertEqual(mod.valid, 0)
        self.assertEqual(mod.busy, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

import json
from pathlib import Path

path = Path("outputs/pseudocode.json")

with path.open("r", encoding="utf-8") as file:
    data = json.load(file)

data["pseudocode"] = [
    "REG state : {IDLE, EXEC}",
    "REG operand_a_reg[31:0]",
    "REG operand_b_reg[31:0]",
    "REG opcode_reg[3:0]",
    "REG result_reg[31:0]",
    "REG busy_reg",
    "REG valid_reg",
    "REG error_reg",
    "",
    "SIG alu_out[31:0]",
    "SIG opcode_error",
    "",
    "// Combinational ALU",
    "FUNCTION alu_compute(a[31:0], b[31:0], op[3:0]) -> (out[31:0], err):",
    "  CASE op:",
    "    4'b0000: out = (a + b) MOD 2^32; err = 0",
    "    4'b0001: out = (a - b) MOD 2^32; err = 0",
    "    4'b0010: out = a & b; err = 0",
    "    4'b0011: out = a | b; err = 0",
    "    4'b0100: out = a ^ b; err = 0",
    "    4'b0101: out = a << operand_b[4:0]; err = 0",
    "    4'b0110: out = a >> operand_b[4:0]; err = 0",
    "    DEFAULT: out = 32'b0; err = 1",
    "  END CASE",
    "  RETURN (out, err)",
    "END FUNCTION",
    "",
    "// Combinational ALU evaluation",
    "(alu_out, opcode_error) = alu_compute(operand_a_reg, operand_b_reg, opcode_reg)",
    "",
    "// Synchronous active-low reset and state machine",
    "ON RISING EDGE OF clk",
    "  IF rst_n == 0 THEN",
    "    state = IDLE",
    "    operand_a_reg = 32'b0",
    "    operand_b_reg = 32'b0",
    "    opcode_reg = 4'b0",
    "    result_reg = 32'b0",
    "    busy_reg = 0",
    "    valid_reg = 0",
    "    error_reg = 0",
    "  ELSE",
    "    valid_reg = 0",
    "    IF state == IDLE THEN",
    "      busy_reg = 0",
    "      error_reg = 0",
    "      IF start == 1 THEN",
    "        operand_a_reg = operand_a",
    "        operand_b_reg = operand_b",
    "        opcode_reg = opcode",
    "        state = EXEC",
    "        busy_reg = 1",
    "      END IF",
    "    ELSE",
    "      result_reg = alu_out",
    "      error_reg = opcode_error",
    "      valid_reg = 1",
    "      busy_reg = 0",
    "      state = IDLE",
    "    END IF",
    "  END IF",
    "END ON",
    "",
    "// Output assignments",
    "result = result_reg",
    "busy = busy_reg",
    "valid = valid_reg",
    "error = error_reg",
]

with path.open("w", encoding="utf-8") as file:
    json.dump(data, file, indent=2)

print("Saved pseudocode replaced successfully.")
print("Pseudocode lines:", len(data["pseudocode"]))
print("API calls made: 0")

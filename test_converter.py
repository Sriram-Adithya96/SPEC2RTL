from src.agents.pseudocode_to_python import convert_pseudocode

pseudocode = [
    "// Initialize registers",
    "REG result : 32-bit := 32'b0",
    "REG valid : 1-bit := 0",
    "IF rst_n == 0 THEN",
    "    result := 32'b0",
    "    valid := 0",
    "ELSE",
    "    result := operand_a",
    "    valid := 1",
    "END IF",
]

python_code = convert_pseudocode(pseudocode)

print("Generated Python:")
print(python_code)
from src.agents.pseudocode_to_python import to_32bit

print(to_32bit(0xFFFFFFFF + 1))  # 0
print(to_32bit(10 - 20))         # 4294967286
print(to_32bit(100 + 200))       # 300
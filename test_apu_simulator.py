from src.agents.apu_simulator import APUSimulator

apu = APUSimulator()

print("\n--- Reset ---")
apu.rising_edge(rst_n=0)

print("\n--- Start addition: 10 + 20 ---")
apu.rising_edge(
    rst_n=1,
    start=1,
    operand_a=10,
    operand_b=20,
    opcode=0,
)

print("\n--- Complete addition ---")
apu.rising_edge(rst_n=1)

assert apu.result == 30
assert apu.valid == 1
assert apu.busy == 0

print("\nAddition test passed!")

print("\n--- Test 32-bit overflow ---")
apu.rising_edge(
    rst_n=1,
    start=1,
    operand_a=0xFFFFFFFF,
    operand_b=1,
    opcode=0,
)

apu.rising_edge(rst_n=1)

assert apu.result == 0

print("Overflow test passed!")

print("\n--- Test unsupported opcode ---")
apu.rising_edge(
    rst_n=1,
    start=1,
    operand_a=10,
    operand_b=5,
    opcode=7,
)

apu.rising_edge(rst_n=1)

assert apu.error == 1
assert apu.valid == 1

print("Unsupported opcode test passed!")
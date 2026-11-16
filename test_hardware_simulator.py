from src.agents.hardware_simulator import HardwareSimulator

sim = HardwareSimulator()

# Initialize registers
sim.set_register("result_reg", 0)
sim.set_register("busy_reg", 0)
sim.set_register("valid_reg", 0)

sim.show_registers()

# Simulate two rising clock edges
sim.rising_edge()
sim.rising_edge()

# Simulate synchronous reset
sim.reset_registers({
    "result_reg": 0,
    "busy_reg": 0,
    "valid_reg": 0,
})

sim.show_registers()
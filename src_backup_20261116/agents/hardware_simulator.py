class HardwareSimulator:
    def __init__(self):
        self.registers = {}
        self.cycle = 0

    def set_register(self, name, value):
        self.registers[name] = value

    def get_register(self, name):
        return self.registers.get(name, 0)

    def rising_edge(self):
        """Simulate one rising edge of the clock."""
        self.cycle += 1
        print(f"Clock cycle: {self.cycle}")

    def reset_registers(self, reset_values):
        """Reset registers to their specified values."""
        for name, value in reset_values.items():
            self.registers[name] = value

    def show_registers(self):
        print("Register values:")
        for name, value in self.registers.items():
            print(f"  {name} = {value}")
class APUSimulator:
    MASK_32 = 0xFFFFFFFF

    def __init__(self):
        self.result = 0
        self.valid = 0
        self.busy = 0
        self.error = 0

        self.pending_result = 0
        self.pending_error = 0
        self.pending_operation = False

        self.cycle = 0

    def calculate(self, operand_a, operand_b, opcode):
        """Calculate the selected 32-bit APU operation."""

        a = operand_a & self.MASK_32
        b = operand_b & self.MASK_32
        shift = b & 0x1F

        if opcode == 0b0000:
            return (a + b) & self.MASK_32, 0

        elif opcode == 0b0001:
            return (a - b) & self.MASK_32, 0

        elif opcode == 0b0010:
            return a & b, 0

        elif opcode == 0b0011:
            return a | b, 0

        elif opcode == 0b0100:
            return a ^ b, 0

        elif opcode == 0b0101:
            return (a << shift) & self.MASK_32, 0

        elif opcode == 0b0110:
            return a >> shift, 0

        else:
            return 0, 1

    def rising_edge(
        self,
        rst_n,
        start=0,
        operand_a=0,
        operand_b=0,
        opcode=0,
    ):
        """Simulate one rising clock edge."""

        self.cycle += 1

        # Synchronous active-low reset.
        if rst_n == 0:
            self.result = 0
            self.valid = 0
            self.busy = 0
            self.error = 0

            self.pending_result = 0
            self.pending_error = 0
            self.pending_operation = False

            return

        # Default: valid and error are one-cycle pulses.
        self.valid = 0
        self.error = 0

        # Complete an operation accepted on the previous edge.
        if self.pending_operation:
            self.result = self.pending_result
            self.error = self.pending_error
            self.valid = 1
            self.busy = 0
            self.pending_operation = False

        # Accept a new operation only if idle at the start of the edge.
        elif self.busy == 0 and start == 1:
            result, error = self.calculate(
                operand_a & self.MASK_32,
                operand_b & self.MASK_32,
                opcode,
            )

            self.pending_result = result
            self.pending_error = error
            self.pending_operation = True
            self.busy = 1

        print(
            f"Cycle={self.cycle}, "
            f"result={self.result}, "
            f"valid={self.valid}, "
            f"busy={self.busy}, "
            f"error={self.error}"
        )
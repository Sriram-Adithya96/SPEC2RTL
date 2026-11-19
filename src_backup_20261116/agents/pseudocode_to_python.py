import ast
import re


def to_32bit(value):
    """Wrap an integer to an unsigned 32-bit value."""
    return value & 0xFFFFFFFF


def convert_expression(expression):
    """Convert supported hardware expressions into Python expressions."""
    expression = expression.strip()

    # Convert Verilog-style binary constants, e.g. 32'b0 or 4'b1010.
    expression = re.sub(
        r"(\d+)'[bB]([01]+)",
        lambda match: str(int(match.group(2), 2)),
        expression,
    )

    # Convert hexadecimal and decimal width constants if present.
    expression = re.sub(
        r"(\d+)'[hH]([0-9a-fA-F]+)",
        lambda match: str(int(match.group(2), 16)),
        expression,
    )

    # Convert logical operators.
    expression = expression.replace("&&", " and ")
    expression = expression.replace("||", " or ")

    # The APU pseudocode names operand_b / operand_b_value / b inside a shift statement,
    # but the ALU function receives it as parameter b.
    expression = re.sub(r"\b(?:operand_b(?:\w*)?|b)\[4:0\]", "(b & 0x1F)", expression)

    # The saved APU pseudocode uses named enum states.
    expression = re.sub(r"\bIDLE\b", '"IDLE"', expression)
    expression = re.sub(r"\bEXEC\b", '"EXEC"', expression)

    # Convert hardware equality operators without changing >=, <=, !=, or ==.
    expression = re.sub(r"(?<![<>=!])!(?!=)", " not ", expression)
    expression = re.sub(r"(?<![<>=!])=(?!=)", "==", expression)

    # Convert common modulo notation.
    expression = expression.replace("MOD 2^32", "& 0xFFFFFFFF")

    # Left shifts must wrap back to 32 bits.
    if "<<" in expression and not expression.startswith("("):
        expression = f"({expression}) & 0xFFFFFFFF"

    # Convert bit slices such as b[4:0] to a mask expression.
    expression = re.sub(
        r"\b(\w+)\[(\d+):0\]",
        lambda match: (
            f"({match.group(1)} & {(1 << (int(match.group(2)) + 1)) - 1})"
        ),
        expression,
    )

    return expression.strip()


def convert_pseudocode(pseudocode):
    """
    Convert a supported subset of hardware pseudocode into Python.

    Supported:
    - Register declarations
    - Signal declarations
    - Assignments (including tuple unpack)
    - IF / ELSE IF / ELSE / END IF
    - FUNCTION / END FUNCTION
    - CASE / END CASE
    - DEFAULT
    - ON RISING EDGE OF clk / END ON
    """

    python_lines = []
    indent = 0
    block_stack = []
    case_variable = None
    case_first_branch = True
    in_clocked_block = False
    clock_block_seen = False
    register_names = []
    output_names = ["result", "busy", "valid", "error"]

    def emit(line):
        python_lines.append("    " * indent + line)

    def convert_clocked_condition(condition_expr):
        """
        Evaluate condition expressions using the register state sampled at the
        start of the clock edge (old-state semantics).
        """
        # Convert word-based boolean operators in conditions
        cond = re.sub(r"\bAND\b", " and ", condition_expr)
        cond = re.sub(r"\bOR\b", " or ", cond)
        cond = re.sub(r"\bNOT\b", " not ", cond)
        conv = convert_expression(cond)
        if in_clocked_block:
            for reg in register_names:
                conv = re.sub(r"\b" + re.escape(reg) + r"\b", f"_old_{reg}", conv)
        return conv

    for original_line in pseudocode:
        line = original_line.strip()

        # Skip blank lines and comments.
        if not line or line.startswith("//"):
            continue

        # Clocked logic becomes a Python function called for each clock edge.
        if re.match(r"ON\s+RISING\s+EDGE\s+OF\s+clk", line, re.IGNORECASE):
            for name in output_names:
                emit(f"{name} = 0")
            emit("def rising_edge(rst_n, start=0, operand_a=0, operand_b=0, opcode=0):")
            indent += 1
            global_names = register_names + output_names + ["alu_out", "opcode_error"]
            emit("global " + ", ".join(global_names))

            # Sample registers at the rising edge to provide true hardware non-blocking semantics
            for reg in register_names:
                emit(f"_old_{reg} = {reg}")

            emit("alu_out, opcode_error = alu_compute(operand_a_reg, operand_b_reg, opcode_reg)")
            block_stack.append("CLOCK")
            in_clocked_block = True
            clock_block_seen = True
            continue

        if line.upper() == "END ON":
            if not block_stack or block_stack[-1] != "CLOCK":
                raise ValueError("END ON without a matching clock block.")
            for name in output_names:
                emit(f"{name} = {name}_reg")
            indent -= 1
            block_stack.pop()
            in_clocked_block = False
            continue

        # Ignore signal declarations; they don't require Python declarations.
        if line.startswith("SIG "):
            continue

        # Register declarations, including enums and optional initial values.
        if line.startswith("REG "):
            match = re.match(r"REG\s+(\w+(?:\[\d+:\d+\])?)\s*(?::\s*(.*))?$", line)
            if not match:
                raise ValueError(f"Unsupported register declaration: {line}")

            name = match.group(1).split("[")[0]
            register_names.append(name)
            declaration = (match.group(2) or "").strip()

            if ":=" in declaration:
                value = declaration.split(":=", 1)[1].strip()
                value = convert_expression(value)
            elif declaration.startswith("{") and declaration.endswith("}"):
                value = repr(declaration[1:-1].split(",")[0].strip())
            else:
                value = "0"

            emit(f"{name} = {value}")
            continue

        # Function declarations.
        function_match = re.match(
            r"FUNCTION\s+(\w+)\s*\((.*?)\)\s*->\s*\((.*?)\)\s*:?",
            line,
            re.IGNORECASE,
        )

        if function_match:
            name = function_match.group(1)
            parameters = function_match.group(2)

            parameter_names = []
            for parameter in parameters.split(","):
                parameter = parameter.strip()
                if parameter:
                    parameter_names.append(parameter.split("[")[0].strip())

            emit(f"def {name}({', '.join(parameter_names)}):")
            indent += 1
            block_stack.append("FUNCTION")
            continue

        if line.upper() == "END FUNCTION":
            if not block_stack or block_stack[-1] != "FUNCTION":
                raise ValueError("END FUNCTION without a matching FUNCTION.")
            indent -= 1
            block_stack.pop()
            continue

        # CASE statement.
        case_match = re.match(r"CASE\s+(.+?)\s*:?\s*$", line, re.IGNORECASE)
        if case_match:
            case_var_expr = case_match.group(1).strip().rstrip(":")
            if in_clocked_block:
                case_variable = convert_clocked_condition(case_var_expr)
            else:
                case_variable = convert_expression(case_var_expr)
            case_first_branch = True
            block_stack.append("CASE")
            continue

        if line.upper() == "END CASE":
            if not block_stack or block_stack[-1] != "CASE":
                raise ValueError("END CASE without a matching CASE.")
            block_stack.pop()
            case_variable = None
            continue

        # CASE branch, e.g. 4'b0000: out = a + b; err = 0
        if case_variable is not None and ":" in line:
            label, statement = line.split(":", 1)
            label = label.strip()
            statement = statement.strip()

            if label.upper() == "DEFAULT":
                emit("else:")
            else:
                label = convert_expression(label)
                keyword = "if" if case_first_branch else "elif"
                emit(f"{keyword} {case_variable} == {label}:")
            indent += 1
            case_first_branch = False

            if statement:
                for part in statement.split(";"):
                    part = part.strip()
                    if part:
                        translate_assignment(part, emit)
                indent -= 1
            continue

        # ELSE IF statements.
        if (line.upper().startswith("ELSE IF ") or line.upper().startswith("ELSIF ")) and line.upper().endswith(" THEN"):
            if not block_stack or block_stack[-1] != "IF":
                raise ValueError("ELSE IF without a matching IF.")
            indent -= 1
            prefix_len = 8 if line.upper().startswith("ELSE IF ") else 6
            cond_str = line[prefix_len:-5].strip()
            condition = convert_clocked_condition(cond_str)
            emit(f"elif {condition}:")
            indent += 1
            continue

        # IF statements.
        if line.upper().startswith("IF ") and line.upper().endswith(" THEN"):
            cond_str = line[3:-5].strip()
            condition = convert_clocked_condition(cond_str)
            emit(f"if {condition}:")
            indent += 1
            block_stack.append("IF")
            continue

        if line.upper() == "ELSE":
            if not block_stack or block_stack[-1] != "IF":
                raise ValueError("ELSE without a matching IF.")
            indent -= 1
            emit("else:")
            indent += 1
            continue

        if line.upper() == "END IF":
            if not block_stack or block_stack[-1] != "IF":
                raise ValueError("END IF without a matching IF.")
            indent -= 1
            block_stack.pop()
            continue

        # Return statement.
        if line.upper().startswith("RETURN "):
            expression = convert_expression(line[7:].strip())
            emit(f"return {expression}")
            continue

        # Simple or tuple assignment.
        if ":=" in line or "=" in line:
            assignment_target = re.split(r":=|=", line, maxsplit=1)[0].strip()
            if assignment_target in output_names and clock_block_seen and not in_clocked_block:
                continue
            translate_assignment(line, emit)
            continue

        raise ValueError(f"Unsupported pseudocode statement: {line}")

    if block_stack:
        raise ValueError(f"Unclosed pseudocode block(s): {block_stack}")

    python_code = "\n".join(python_lines)

    if not python_code.strip():
        raise ValueError("No Python code was generated.")

    # Validate Python syntax without executing the generated code.
    ast.parse(python_code)

    return python_code


def translate_assignment(line, emit):
    """Translate simple assignments into Python."""
    parts = line.split(";")

    for part in parts:
        part = part.strip()
        if not part:
            continue

        match = re.match(r"(.+?)\s*:=\s*(.+)$", part)
        if not match:
            match = re.match(r"(.+?)\s*=(?!=)\s*(.+)$", part)

        if not match:
            raise ValueError(f"Unsupported assignment: {part}")

        target = match.group(1).strip()
        raw_val = match.group(2).strip()

        # Handle tuple unpack e.g. (result_reg, error_reg) = alu_compute(...)
        if target.startswith("(") and target.endswith(")"):
            value = convert_expression(raw_val)
            emit(f"{target} = {value}")
            continue

        # Convert bitwise keywords that appear in assignments e.g. a AND b -> a & b
        raw_val = re.sub(r"(?<=\w)\s+XOR\s+(?=\w)", " ^ ", raw_val, flags=re.IGNORECASE)
        raw_val = re.sub(r"(?<=\w)\s+AND\s+(?=\w)", " & ", raw_val, flags=re.IGNORECASE)
        raw_val = re.sub(r"(?<=\w)\s+OR\s+(?=\w)", " | ", raw_val, flags=re.IGNORECASE)

        value = convert_expression(raw_val)

        if target in ("operand_a_reg", "operand_b_reg", "result", "result_reg", "out"):
            value = f"({value}) & 0xFFFFFFFF"

        emit(f"{target} = {value}")

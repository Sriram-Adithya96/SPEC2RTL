import pytest

from src.agents.rtl_generation import validate_rtl_output
from src.schemas import ComponentRTLModuleOutput


MODULE_NAME = "StreamAdapter"
EXPECTED_INPUTS = ["payload[7:0]", "enable"]
EXPECTED_OUTPUTS = ["result[7:0]", "ready"]


def _module(rtl_code):
    return ComponentRTLModuleOutput(
        component_name=MODULE_NAME,
        module_name=MODULE_NAME,
        inputs=EXPECTED_INPUTS,
        outputs=EXPECTED_OUTPUTS,
        rtl_code=rtl_code,
    )


def _ansi_rtl(ports):
    declarations = []
    for direction, width, name in ports:
        width_text = f" {width}" if width else ""
        declarations.append(f"{direction} wire{width_text} {name}")
    return (
        f"module {MODULE_NAME} ({', '.join(declarations)});\n"
        "endmodule\n"
    )


def _non_ansi_rtl(ports):
    names = ", ".join(name for _direction, _width, name in ports)
    declarations = []
    for direction, width, name in ports:
        width_text = f" {width}" if width else ""
        declarations.append(f"{direction} wire{width_text} {name};")
    return (
        f"module {MODULE_NAME} ({names});\n"
        + "\n".join(declarations)
        + "\nendmodule\n"
    )


def _ports_for_case(style, case):
    ports = [
        ("input", "[7:0]", "payload"),
        ("input", None, "enable"),
        ("output", "[7:0]", "result"),
        ("output", None, "ready"),
    ]
    if case == "missing":
        ports = ports[:-1]
    elif case == "extra":
        ports.append(("output", None, "unexpected"))
    elif case == "duplicate":
        ports.insert(2, ("input", None, "enable"))
    elif case == "wrong_order":
        ports[0], ports[1] = ports[1], ports[0]
    elif case == "wrong_direction":
        ports[1] = ("output", None, "enable")
    elif case == "wrong_width":
        ports[0] = ("input", "[6:0]", "payload")

    return _ansi_rtl(ports) if style == "ansi" else _non_ansi_rtl(ports)


def test_accepts_ansi_module_header():
    rtl = _ansi_rtl([
        ("input", "[7:0]", "payload"),
        ("input", None, "enable"),
        ("output", "[7:0]", "result"),
        ("output", None, "ready"),
    ])

    validate_rtl_output(
        _module(rtl),
        MODULE_NAME,
        EXPECTED_INPUTS,
        EXPECTED_OUTPUTS,
    )


def test_accepts_ansi_header_with_inherited_direction_and_width():
    rtl = """
module StreamAdapter (
    input wire [7:0] payload, payload_copy,
    output reg [7:0] result, result_copy
);
endmodule
"""
    module = ComponentRTLModuleOutput(
        component_name=MODULE_NAME,
        module_name=MODULE_NAME,
        inputs=["payload[7:0]", "payload_copy[7:0]"],
        outputs=["result[7:0]", "result_copy[7:0]"],
        rtl_code=rtl,
    )

    validate_rtl_output(
        module,
        MODULE_NAME,
        module.inputs,
        module.outputs,
    )


def test_accepts_non_ansi_module_header():
    rtl = _non_ansi_rtl([
        ("input", "[7:0]", "payload"),
        ("input", None, "enable"),
        ("output", "[7:0]", "result"),
        ("output", None, "ready"),
    ])

    validate_rtl_output(
        _module(rtl),
        MODULE_NAME,
        EXPECTED_INPUTS,
        EXPECTED_OUTPUTS,
    )


@pytest.mark.parametrize("style", ["ansi", "non_ansi"])
@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "extra",
        "duplicate",
        "wrong_direction",
        "wrong_width",
        "wrong_order",
    ],
)
def test_rejects_mismatched_port_interfaces(style, case):
    rtl = _ports_for_case(style, case)

    with pytest.raises(ValueError):
        validate_rtl_output(
            _module(rtl),
            MODULE_NAME,
            EXPECTED_INPUTS,
            EXPECTED_OUTPUTS,
        )


def test_non_ansi_port_declaration_order_does_not_change_header_order():
    rtl = """
module StreamAdapter (payload, enable, result, ready);
output ready;
input enable;
output [7:0] result;
input [7:0] payload;
endmodule
"""

    validate_rtl_output(
        _module(rtl),
        MODULE_NAME,
        EXPECTED_INPUTS,
        EXPECTED_OUTPUTS,
    )

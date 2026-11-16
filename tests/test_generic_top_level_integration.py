import re

import pytest

from src.agents.rtl_generation import (
    _integrate_component_rtl,
    _parse_signal,
    validate_rtl_output,
)
from src.schemas import (
    Component,
    ComponentRTLModuleOutput,
    DecompositionOutput,
    Understanding,
)


def _design(
    system_inputs,
    system_outputs,
    components,
    interactions,
):
    component_models = [
        Component(
            name=name,
            purpose=f"Synthetic component {name}.",
            inputs=inputs,
            outputs=outputs,
        )
        for name, inputs, outputs, _connection_expectations in components
    ]
    module_outputs = []
    for name, inputs, outputs, _connection_expectations in components:
        signals = [
            (signal, "input")
            for signal in inputs
        ] + [
            (signal, "output")
            for signal in outputs
        ]
        port_names = [_parse_signal(signal)[0] for signal, _ in signals]
        declarations = []
        for signal, direction in signals:
            port_name, width = _parse_signal(signal)
            declarations.append(
                f"{direction}{f' {width}' if width else ''} {port_name};"
            )
        module_outputs.append(ComponentRTLModuleOutput(
            component_name=name,
            module_name=name,
            inputs=inputs,
            outputs=outputs,
            rtl_code=(
                f"module {name} ({', '.join(port_names)});\n"
                + "\n".join(declarations)
                + "\nendmodule"
            ),
            generation_status="completed",
        ))

    understanding = Understanding(
        system_purpose="A generic synthetic hardware design.",
        major_components=[name for name, *_ in components],
        inputs=system_inputs,
        outputs=system_outputs,
        functional_requirements=[],
        constraints=[],
        ambiguities=[],
    )
    decomposition = DecompositionOutput(
        components=component_models,
        interactions=interactions,
        implementation_plan=[],
    )
    return component_models, module_outputs, decomposition, understanding


def _assert_integrated(design):
    component_models, modules, decomposition, understanding = design
    top_name, top_rtl, instances, integrated_rtl = _integrate_component_rtl(
        component_models,
        modules,
        decomposition,
        understanding,
    )

    assert top_name == "system_top"
    assert {item.component_name for item in instances} == {
        component.name for component in component_models
    }
    assert len(instances) == len(component_models)
    assert all(
        set(instance.port_connections)
        == {
            _parse_signal(signal)[0]
            for signal in (
                next(
                    component.inputs
                    for component in component_models
                    if component.name == instance.component_name
                )
                + next(
                    component.outputs
                    for component in component_models
                    if component.name == instance.component_name
                )
            )
        }
        for instance in instances
    )

    expected_inputs = [
        _signal_name_width(item) for item in understanding.inputs
    ]
    expected_outputs = [
        _signal_name_width(item) for item in understanding.outputs
    ]
    validate_rtl_output(
        ComponentRTLModuleOutput(
            component_name=top_name,
            module_name=top_name,
            inputs=[name + (width or "") for name, width in expected_inputs],
            outputs=[name + (width or "") for name, width in expected_outputs],
            rtl_code=top_rtl,
        ),
        top_name,
        [name + (width or "") for name, width in expected_inputs],
        [name + (width or "") for name, width in expected_outputs],
    )
    assert integrated_rtl.endswith(top_rtl)
    for component, module in zip(component_models, modules):
        validate_rtl_output(
            module,
            component.name,
            component.inputs,
            component.outputs,
        )
    return {item.component_name: item.port_connections for item in instances}


def _signal_name_width(signal):
    match = re.fullmatch(
        r"\s*([A-Za-z_][A-Za-z0-9_]*)"
        r"(?:\s*\[\s*([0-9]+)\s*:\s*([0-9]+)\s*\])?"
        r"(?:\s*:\s*.+)?\s*",
        signal,
    )
    assert match is not None
    name, msb, lsb = match.groups()
    return name, f"[{msb}:{lsb}]" if msb else None


@pytest.mark.parametrize(
    ("design_factory", "expected_connections"),
    [
        (
            lambda: _design(
                [
                    "data_a[7:0]: first datapath operand",
                    "data_b[7:0]: second datapath operand",
                    "operation[1:0]: selects the datapath operation",
                ],
                ["result[7:0]: selected datapath result"],
                [
                    (
                        "ArithmeticBlock",
                        ["left[7:0]", "right[7:0]"],
                        ["sum[7:0]"],
                        None,
                    ),
                    (
                        "LogicalBlock",
                        ["left[7:0]", "right[7:0]"],
                        ["combined[7:0]"],
                        None,
                    ),
                    (
                        "ResultSelector",
                        ["sum[7:0]", "combined[7:0]", "operation[1:0]"],
                        ["result[7:0]"],
                        None,
                    ),
                ],
                [
                    "data_a[7:0] -> ArithmeticBlock left[7:0]",
                    "data_b[7:0] -> ArithmeticBlock right[7:0]",
                    "data_a[7:0] -> LogicalBlock left[7:0]",
                    "data_b[7:0] -> LogicalBlock right[7:0]",
                    "ArithmeticBlock sum[7:0] -> ResultSelector sum[7:0]",
                    "LogicalBlock combined[7:0] -> ResultSelector combined[7:0]",
                    "operation[1:0] -> ResultSelector operation[1:0]",
                    "ResultSelector result[7:0] -> result[7:0]",
                ],
            ),
            {
                "ArithmeticBlock": {
                    "left": "data_a",
                    "right": "data_b",
                    "sum": "net_ArithmeticBlock_sum",
                },
                "LogicalBlock": {
                    "left": "data_a",
                    "right": "data_b",
                    "combined": "net_LogicalBlock_combined",
                },
                "ResultSelector": {
                    "sum": "net_ArithmeticBlock_sum",
                    "combined": "net_LogicalBlock_combined",
                    "operation": "operation",
                    "result": "result",
                },
            },
        ),
        (
            lambda: _design(
                [
                    "clock: controller clock",
                    "reset: active-high controller reset",
                    "vehicle_sensor: vehicle detector",
                    "pedestrian_sensor: pedestrian request button",
                ],
                [
                    "red_lamp: red vehicle indication",
                    "yellow_lamp: yellow vehicle indication",
                    "green_lamp: green vehicle indication",
                    "walk_signal: pedestrian indication",
                ],
                [
                    (
                        "SensorConditioner",
                        ["vehicle_sensor", "pedestrian_sensor"],
                        ["vehicle_request", "pedestrian_request"],
                        None,
                    ),
                    (
                        "IntervalTimer",
                        ["clock", "reset", "timer_enable"],
                        ["timer_expired"],
                        None,
                    ),
                    (
                        "TrafficStateMachine",
                        [
                            "clock",
                            "reset",
                            "vehicle_request",
                            "pedestrian_request",
                            "timer_expired",
                        ],
                        [
                            "timer_enable",
                            "red",
                            "yellow",
                            "green",
                            "walk",
                        ],
                        None,
                    ),
                ],
                [
                    "vehicle_sensor -> SensorConditioner vehicle_sensor",
                    "pedestrian_sensor -> SensorConditioner pedestrian_sensor",
                    "clock -> IntervalTimer clock",
                    "reset -> IntervalTimer reset",
                    "TrafficStateMachine timer_enable -> IntervalTimer timer_enable",
                    "clock -> TrafficStateMachine clock",
                    "reset -> TrafficStateMachine reset",
                    "SensorConditioner vehicle_request -> TrafficStateMachine vehicle_request",
                    "SensorConditioner pedestrian_request -> TrafficStateMachine pedestrian_request",
                    "IntervalTimer timer_expired -> TrafficStateMachine timer_expired",
                    "TrafficStateMachine red -> red_lamp",
                    "TrafficStateMachine yellow -> yellow_lamp",
                    "TrafficStateMachine green -> green_lamp",
                    "TrafficStateMachine walk -> walk_signal",
                ],
            ),
            {
                "SensorConditioner": {
                    "vehicle_sensor": "vehicle_sensor",
                    "pedestrian_sensor": "pedestrian_sensor",
                    "vehicle_request": "net_SensorConditioner_vehicle_request",
                    "pedestrian_request": "net_SensorConditioner_pedestrian_request",
                },
                "IntervalTimer": {
                    "clock": "clock",
                    "reset": "reset",
                    "timer_enable": "net_TrafficStateMachine_timer_enable",
                    "timer_expired": "net_IntervalTimer_timer_expired",
                },
                "TrafficStateMachine": {
                    "clock": "clock",
                    "reset": "reset",
                    "vehicle_request": "net_SensorConditioner_vehicle_request",
                    "pedestrian_request": "net_SensorConditioner_pedestrian_request",
                    "timer_expired": "net_IntervalTimer_timer_expired",
                    "timer_enable": "net_TrafficStateMachine_timer_enable",
                    "red": "net_TrafficStateMachine_red",
                    "yellow": "net_TrafficStateMachine_yellow",
                    "green": "net_TrafficStateMachine_green",
                    "walk": "net_TrafficStateMachine_walk",
                },
            },
        ),
        (
            lambda: _design(
                [
                    "clock: counter clock",
                    "reset_n: active-low reset",
                    "enable: count enable",
                ],
                ["count[7:0]: current count value"],
                [
                    (
                        "CounterCore",
                        ["clock", "reset_n", "enable"],
                        ["count[7:0]"],
                        None,
                    ),
                ],
                [],
            ),
            {
                "CounterCore": {
                    "clock": "clock",
                    "reset_n": "reset_n",
                    "enable": "enable",
                    "count": "count",
                },
            },
        ),
        (
            lambda: _design(
                [
                    "input_a: first Boolean input",
                    "input_b: second Boolean input",
                    "input_c: third Boolean input",
                    "qualifier: output qualification",
                ],
                [
                    "parity_out: parity result",
                    "any_out: any-input result",
                ],
                [
                    (
                        "PairLogic",
                        ["input_a", "input_b"],
                        ["pair_term"],
                        None,
                    ),
                    (
                        "BooleanOutputs",
                        ["pair_term", "input_c", "qualifier"],
                        ["parity_out", "any_out"],
                        None,
                    ),
                ],
                [
                    "input_a -> PairLogic input_a",
                    "input_b -> PairLogic input_b",
                    "PairLogic pair_term -> BooleanOutputs pair_term",
                    "input_c -> BooleanOutputs input_c",
                    "qualifier -> BooleanOutputs qualifier",
                ],
            ),
            {
                "PairLogic": {
                    "input_a": "input_a",
                    "input_b": "input_b",
                    "pair_term": "net_PairLogic_pair_term",
                },
                "BooleanOutputs": {
                    "pair_term": "net_PairLogic_pair_term",
                    "input_c": "input_c",
                    "qualifier": "qualifier",
                    "parity_out": "parity_out",
                    "any_out": "any_out",
                },
            },
        ),
    ],
    ids=[
        "datapath",
        "traffic-light-fsm",
        "counter",
        "combinational-multi-output",
    ],
)
def test_generic_design_interfaces_and_dynamic_integration(
    design_factory,
    expected_connections,
):
    connections = _assert_integrated(design_factory())

    assert connections == expected_connections


def test_rejects_interaction_destination_that_is_component_output():
    design = _design(
        ["opcode_error"],
        [],
        [
            (
                "OpcodeDecoder",
                ["opcode"],
                ["opcode_error"],
                None,
            ),
            (
                "ControlLogic",
                ["opcode"],
                ["error"],
                None,
            ),
        ],
        [
            "opcode_error -> ControlLogic error",
        ],
    )
    components, modules, decomposition, understanding = design

    with pytest.raises(
        ValueError,
        match=(
            r"targets output port 'ControlLogic\.error'; "
            r"a component destination must identify an input port"
        ),
    ):
        _integrate_component_rtl(
            components,
            modules,
            decomposition,
            understanding,
        )

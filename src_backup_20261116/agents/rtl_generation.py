from typing import Any

import json
import re
from pathlib import Path

from src.llm.llm import get_llm
from src.schemas import (
    Component,
    ComponentPseudocodeOutput,
    ComponentRTLInstanceOutput,
    ComponentRTLModuleOutput,
    DecompositionOutput,
    DescriptionOutput,
    PseudocodeGenerationOutput,
    RTLGenerationOutput,
    Understanding,
)


SYSTEM_PROMPT = """
You are the RTL Generation Agent in the SPEC2RTL system.

Your task is to convert ONE validated component pseudocode block into its
synthesizable Verilog-2001 module.

SOURCE-OF-TRUTH RULES:

1. The ORIGINAL HARDWARE SPECIFICATION is the primary source of truth.
2. The VALIDATED PSEUDOCODE is the implementation guide.
3. Never introduce behavior that is absent from the specification.
4. If the pseudocode conflicts with the original specification, do not
   silently choose one. Report the conflict as an unresolved issue.
5. Never invent clock edges, reset polarity, reset type, reset values,
   signal widths, timing values, state transitions, or architecture.
6. Preserve every required input and output.
7. Do not omit specified functional behavior.

VERILOG REQUIREMENTS:

1. Generate synthesizable Verilog-2001.
2. Generate exactly one component module, not a top-level design.
3. Use the exact provided module name and component interface signal names.
4. Preserve specified signal widths.
5. Use input, output, wire, and reg declarations appropriately.
6. Use nonblocking assignments (<=) for sequential logic.
7. Use blocking assignments (=) for combinational logic.
8. Use always @(posedge ...) or always @(negedge ...)
   only when the clock edge is explicitly specified.
9. Implement reset only when its behavior is specified.
10. Do not invent reset behavior.
11. Avoid inferred latches in combinational logic.
12. Use complete case statements and appropriate default behavior
    only when supported by the specification.
13. Do not add unnecessary registers or internal signals.
14. Do not generate testbenches, Python code, or pseudocode.
15. Do not use SystemVerilog-only constructs such as logic,
    always_ff, always_comb, or typedef.
16. Do not add unsupported default states or arbitrary output values.
17. Include concise comments where useful.
18. For output register modules (e.g. ResultRegister) in single-cycle latency pipelines:
    When capture_enable (or the execution enable) is asserted on posedge clk,
    the combinational result is already computed: register result <= selected_result,
    assert valid <= 1'b1, set busy <= 1'b0, and set error <= opcode_error.
    In the next cycle (when enable is deasserted), deassert valid <= 1'b0 and error <= 1'b0.
    Do NOT create artificial multi-cycle FSM states (like a separate PROCESSING cycle)
    that delay valid assertion beyond the specified 1-cycle latency.
19. Ensure valid is asserted for exactly ONE clock cycle, busy returns low when valid
    is high, and error is cleared when valid deasserts.

OUTPUT REQUIREMENTS:

Return exactly one JSON object with these fields:

{
    "module_name": "module name",
    "language": "Verilog",
    "rtl_code": "complete Verilog source code",
    "assumptions": [],
    "unresolved_issues": []
}

Use a non-ANSI Verilog-2001 module header listing the ports, followed by
one input or output declaration per line. Preserve the supplied port order,
names, directions, and widths exactly. Do not add a top-level integration
module or unsupported ports.

Copy the pseudocode component's assumptions exactly. Return an empty
unresolved_issues array; if a conflict or unresolved behavior prevents
faithful RTL, report it there and do not claim a successful implementation.
Return ONLY valid JSON. Do not include Markdown fences or explanations.
"""


def extract_response_content(response) -> str:
    """Convert the LLM response content into a string."""

    content = response.content

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts = []

        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            elif isinstance(block, str):
                text_parts.append(block)

        return "\n".join(text_parts)

    return str(content)


def extract_json(content: str) -> str:
    """Extract the first complete JSON object from the response."""

    if not content or not content.strip():
        raise ValueError("The model returned an empty response.")

    content = content.strip()

    content = re.sub(
        r"^\s*```(?:json)?\s*",
        "",
        content,
        flags=re.IGNORECASE,
    )
    content = re.sub(r"\s*```\s*$", "", content)

    start = content.find("{")

    if start == -1:
        raise ValueError("No JSON object found in the model response.")

    decoder = json.JSONDecoder()

    try:
        data, _ = decoder.raw_decode(content[start:])
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid or incomplete JSON: {error}"
        ) from error

    if not isinstance(data, dict):
        raise ValueError("The response must be a JSON object.")

    return json.dumps(data)


def save_raw_response(
    raw_content: str,
    output_dir: str | Path | None = None,
    component_name: str | None = None,
) -> Path:
    """Save the raw RTL generation response."""

    target = Path(output_dir) if output_dir is not None else Path("outputs")
    target.mkdir(parents=True, exist_ok=True)

    if component_name:
        safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", component_name).strip("_")
        raw_path = target / f"rtl_generation_raw_{safe_name}.txt"
    else:
        raw_path = target / "rtl_generation_raw.txt"
    raw_path.write_text(raw_content, encoding="utf-8")

    print(f"Raw RTL response saved to: {raw_path}")

    return raw_path


def validate_rtl_output(
    result: RTLGenerationOutput | ComponentRTLModuleOutput,
    expected_module_name: str,
    expected_inputs: list[str] | None = None,
    expected_outputs: list[str] | None = None,
) -> None:
    """Perform basic structural checks on generated RTL."""

    if result.module_name != expected_module_name:
        raise ValueError(
            f"Expected module '{expected_module_name}', "
            f"but received '{result.module_name}'."
        )

    if not result.rtl_code.strip():
        raise ValueError("Generated RTL code is empty.")

    if re.search(r"```", result.rtl_code):
        raise ValueError("RTL code contains Markdown code fences.")

    source = re.sub(r"/\*.*?\*/|//[^\r\n]*", "", result.rtl_code, flags=re.S)
    modules = re.findall(
        r"\bmodule\s+(?:automatic\s+)?([A-Za-z_][A-Za-z0-9_]*)"
        r"\s*\((.*?)\)\s*;",
        source,
        flags=re.S,
    )
    if len(modules) != 1 or modules[0][0] != expected_module_name:
        raise ValueError(
            f"RTL must contain exactly one module declaration named "
            f"'{expected_module_name}'."
        )
    if len(re.findall(r"\bendmodule\b", source)) != 1:
        raise ValueError("RTL must contain exactly one endmodule statement.")

    if expected_inputs is None or expected_outputs is None:
        return

    expected_signals = {
        **{
            name: ("input", width)
            for name, width in (_parse_signal(item) for item in expected_inputs)
        },
        **{
            name: ("output", width)
            for name, width in (_parse_signal(item) for item in expected_outputs)
        },
    }
    if len(expected_signals) != len(expected_inputs) + len(expected_outputs):
        raise ValueError("Component inputs and outputs must have unique signal names.")

    module_match = re.search(
        r"\bmodule\s+(?:automatic\s+)?([A-Za-z_][A-Za-z0-9_]*)"
        r"\s*\((.*?)\)\s*;",
        source,
        flags=re.S,
    )
    endmodule_match = re.search(r"\bendmodule\b", source)
    if module_match is None or endmodule_match is None:
        raise ValueError("RTL module declaration or endmodule is malformed.")
    actual_interface = _parse_module_interface(
        module_match.group(2),
        source[module_match.end():endmodule_match.start()],
    )
    if [name for name, _direction, _width in actual_interface] != list(
        expected_signals
    ):
        raise ValueError(
            "RTL module header ports do not exactly match the expected "
            "component interface and order."
        )

    actual_signals = {
        name: (direction, width)
        for name, direction, width in actual_interface
    }

    if actual_signals != expected_signals:
        raise ValueError(
            "RTL port declarations do not exactly match the expected "
            "component names, directions, and widths."
        )


def _parse_module_interface(
    header: str,
    body: str,
) -> list[tuple[str, str, str | None]]:
    """Parse ANSI or non-ANSI Verilog ports in module-header order."""

    header = header.strip()
    if not header:
        return []

    header_ports = [port.strip() for port in header.split(",")]
    if any(not port for port in header_ports):
        raise ValueError("RTL module header contains an empty port declaration.")

    ansi_declaration = re.compile(
        r"^(input|output|inout)\s+"
        r"(?:(?:wire|reg|tri)\s+)?"
        r"(?:(?:signed|unsigned)\s+)?"
        r"(?:\[\s*([0-9]+)\s*:\s*([0-9]+)\s*\]\s+)?"
        r"([A-Za-z_][A-Za-z0-9_]*)$",
        re.I,
    )
    identifier = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
    is_ansi = bool(re.match(r"^(input|output|inout)\b", header_ports[0], re.I))

    if is_ansi:
        ports: list[tuple[str, str, str | None]] = []
        inherited: tuple[str, str | None] | None = None
        for declaration in header_ports:
            match = ansi_declaration.fullmatch(declaration)
            if match:
                direction, msb, lsb, name = match.groups()
                width = f"[{msb}:{lsb}]" if msb else None
                inherited = (direction.lower(), width)
            elif identifier.fullmatch(declaration) and inherited is not None:
                name = declaration
                direction, width = inherited
            else:
                raise ValueError(
                    f"Invalid or incomplete ANSI port declaration '{declaration}'."
                )
            if any(existing_name == name for existing_name, _, _ in ports):
                raise ValueError(f"RTL declares port '{name}' more than once.")
            ports.append((name, direction, width))
        return ports

    if any(identifier.fullmatch(port) is None for port in header_ports):
        raise ValueError("Non-ANSI module headers must list port names only.")
    if len(header_ports) != len(set(header_ports)):
        raise ValueError("RTL module header declares a port more than once.")

    declaration_pattern = re.compile(
        r"\b(input|output|inout)\s+"
        r"(?:(?:wire|reg|tri)\s+)?"
        r"(?:(?:signed|unsigned)\s+)?"
        r"(?:\[\s*([0-9]+)\s*:\s*([0-9]+)\s*\]\s*)?"
        r"([^;]+);",
        re.I,
    )
    declarations: dict[str, tuple[str, str | None]] = {}
    for match in declaration_pattern.finditer(body):
        direction, msb, lsb, names = match.groups()
        width = f"[{msb}:{lsb}]" if msb else None
        for item in names.split(","):
            name = item.strip()
            if identifier.fullmatch(name) is None:
                raise ValueError(
                    f"Invalid non-ANSI port declaration '{name}'."
                )
            if name in declarations:
                raise ValueError(f"RTL declares port '{name}' more than once.")
            declarations[name] = (direction.lower(), width)

    header_names = set(header_ports)
    declared_names = set(declarations)
    if declared_names != header_names:
        missing = sorted(header_names - declared_names)
        additional = sorted(declared_names - header_names)
        details = []
        if missing:
            details.append(f"missing declarations for {missing}")
        if additional:
            details.append(f"declarations for non-header ports {additional}")
        raise ValueError("RTL port declarations do not match its header: " + "; ".join(details))

    return [
        (name, declarations[name][0], declarations[name][1])
        for name in header_ports
    ]


def _parse_signal(signal: str) -> tuple[str, str | None]:
    match = re.fullmatch(
        r"\s*([A-Za-z_][A-Za-z0-9_]*)(?:\[([0-9]+):([0-9]+)\])?\s*",
        signal,
    )
    if not match:
        raise ValueError(
            f"Interface '{signal}' must use an exact signal name and optional "
            "canonical [MSB:LSB] width."
        )
    name = match.group(1)
    width = f"[{match.group(2)}:{match.group(3)}]" if match.group(2) else None
    return name, width


def _width_in_bits(width: str | None) -> int:
    if width is None:
        return 1
    bounds = re.fullmatch(r"\[([0-9]+):([0-9]+)\]", width)
    if bounds is None:
        raise ValueError(f"Invalid signal width '{width}'.")
    return abs(int(bounds.group(1)) - int(bounds.group(2))) + 1


def _source_selection(
    declared_width: str | None,
    selected_width: str | None,
    endpoint: str,
) -> tuple[int, str | None]:
    if selected_width is None or selected_width == declared_width:
        return _width_in_bits(declared_width), None
    if declared_width is None:
        raise ValueError(
            f"Scalar source '{endpoint}' cannot have a bit-range selection."
        )

    declared_bounds = re.fullmatch(r"\[([0-9]+):([0-9]+)\]", declared_width)
    selection_bounds = re.fullmatch(r"\[([0-9]+):([0-9]+)\]", selected_width)
    if declared_bounds is None or selection_bounds is None:
        raise ValueError(f"Invalid source selection in '{endpoint}'.")
    declared_msb, declared_lsb = map(int, declared_bounds.groups())
    selected_msb, selected_lsb = map(int, selection_bounds.groups())
    lower_bound = min(declared_msb, declared_lsb)
    upper_bound = max(declared_msb, declared_lsb)
    if not (
        lower_bound <= selected_msb <= upper_bound
        and lower_bound <= selected_lsb <= upper_bound
    ):
        raise ValueError(
            f"Source selection in '{endpoint}' is outside the declared "
            f"range {declared_width}."
        )
    return (
        abs(selected_msb - selected_lsb) + 1,
        f"[{selected_msb}:{selected_lsb}]",
    )


def _interface_map(
    items: list[str],
    owner: str,
    *,
    allow_descriptions: bool = False,
) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for item in items:
        name, width = (
            _parse_described_signal(item, owner)
            if allow_descriptions
            else _parse_signal(item)
        )
        if name in result:
            raise ValueError(f"{owner} declares interface '{name}' more than once.")
        result[name] = width
    return result


def _parse_described_signal(
    signal: str,
    owner: str,
) -> tuple[str, str | None]:
    match = re.fullmatch(
        r"\s*([A-Za-z_][A-Za-z0-9_]*)"
        r"(?:\s*\[\s*([0-9]+)\s*:\s*([0-9]+)\s*\])?"
        r"(?:\s*:\s*.+)?\s*",
        signal,
    )
    if match is None:
        raise ValueError(
            f"{owner} interface '{signal}' must start with an exact signal "
            "name and optional [MSB:LSB] width, followed optionally by "
            "a colon-delimited description."
        )
    name, msb, lsb = match.groups()
    width = f"[{msb}:{lsb}]" if msb is not None else None
    return name, width


def _interaction_destination(
    endpoint: str,
    components: list,
    component_inputs: dict[str, dict[str, str | None]],
) -> tuple[str, str, str | None]:
    matches = []
    for component in components:
        prefix = f"{component.name} "
        if not endpoint.startswith(prefix):
            continue
        try:
            port_name, port_width = _parse_signal(endpoint[len(prefix):])
        except ValueError:
            continue
        if port_name in component_inputs[component.name]:
            expected_width = component_inputs[component.name][port_name]
            if port_width is not None and port_width != expected_width:
                raise ValueError(
                    f"Interaction destination '{endpoint}' has a width that "
                    "does not match the component input."
                )
            matches.append((component.name, port_name, expected_width))
    if len(matches) != 1:
        raise ValueError(
            f"Interaction destination '{endpoint}' must identify exactly one "
            "decomposed component input."
        )
    return matches[0]


def _resolve_interaction_destination(
    endpoint: str,
    components: list,
    component_inputs: dict[str, dict[str, str | None]],
    component_outputs: dict[str, dict[str, str | None]],
    system_outputs: dict[str, str | None],
) -> tuple[str, str, str, str | None]:
    matches = []
    for component in components:
        prefix = f"{component.name} "
        if not endpoint.startswith(prefix):
            continue
        try:
            port_name, port_width = _parse_signal(endpoint[len(prefix):])
        except ValueError:
            continue
        if port_name in component_inputs[component.name]:
            expected_width = component_inputs[component.name][port_name]
            if port_width is not None and port_width != expected_width:
                raise ValueError(
                    f"Interaction destination '{endpoint}' has a width that "
                    "does not match the component input."
                )
            matches.append((component.name, port_name, expected_width))
        elif port_name in component_outputs[component.name]:
            raise ValueError(
                f"Interaction destination '{endpoint}' targets output port "
                f"'{component.name}.{port_name}'; a component destination "
                "must identify an input port."
            )

    if len(matches) > 1:
        raise ValueError(
            f"Interaction destination '{endpoint}' identifies multiple "
            "decomposed component inputs."
        )
    if matches:
        return ("component", *matches[0])

    signal_name, signal_width = _parse_signal(endpoint)
    if signal_name not in system_outputs:
        raise ValueError(
            f"Interaction destination '{endpoint}' is not a decomposed "
            "component input or declared system output."
        )
    expected_width = system_outputs[signal_name]
    if signal_width is not None and signal_width != expected_width:
        raise ValueError(
            f"Interaction destination '{endpoint}' has a width that does "
            "not match the system output."
        )
    return ("system_output", signal_name, signal_name, expected_width)


def _interaction_source(
    endpoint: str,
    components: list,
    component_outputs: dict[str, dict[str, str | None]],
    system_inputs: dict[str, str | None],
) -> tuple[str, str, str, int, str | None]:
    matches = []
    for component in components:
        prefix = f"{component.name} "
        if not endpoint.startswith(prefix):
            continue
        try:
            port_name, port_width = _parse_signal(endpoint[len(prefix):])
        except ValueError:
            continue
        if port_name in component_outputs[component.name]:
            expected_width = component_outputs[component.name][port_name]
            effective_width, source_selection = _source_selection(
                expected_width, port_width, endpoint
            )
            matches.append((
                "component",
                component.name,
                port_name,
                effective_width,
                source_selection,
            ))
    if matches:
        if len(matches) != 1:
            raise ValueError(f"Interaction source '{endpoint}' is ambiguous.")
        _, component_name, port_name, width, source_selection = matches[0]
        return (
            "component",
            component_name,
            port_name,
            width,
            source_selection,
        )

    source_name, source_width = _parse_signal(endpoint)
    if source_name not in system_inputs:
        raise ValueError(
            f"Interaction source '{endpoint}' is not a declared system input "
            "or a decomposed component output."
        )
    effective_width, source_selection = _source_selection(
        system_inputs[source_name], source_width, endpoint
    )
    return (
        "external",
        source_name,
        source_name,
        effective_width,
        source_selection,
    )


def _build_top_level_rtl(
    components: list,
    component_modules: list[ComponentRTLModuleOutput],
    decomposition: DecompositionOutput,
    understanding: Understanding,
) -> tuple[str, str, list[ComponentRTLInstanceOutput]]:
    system_inputs = _interface_map(
        understanding.inputs,
        "Understanding inputs",
        allow_descriptions=True,
    )
    system_outputs = _interface_map(
        understanding.outputs,
        "Understanding outputs",
        allow_descriptions=True,
    )
    if set(system_inputs).intersection(system_outputs):
        raise ValueError("A system signal cannot be both an input and an output.")
    component_names = [component.name for component in components]
    if len(component_names) != len(set(component_names)):
        raise ValueError("Decomposition component names must be unique.")
    module_components = [module.component_name for module in component_modules]
    if len(module_components) != len(set(module_components)):
        raise ValueError("RTL modules must have unique component names.")
    if set(module_components) != set(component_names):
        raise ValueError(
            "RTL modules must correspond one-to-one with decomposed components."
        )
    module_names = [module.module_name for module in component_modules]
    if len(module_names) != len(set(module_names)):
        raise ValueError("RTL module names must be unique.")

    component_inputs = {
        component.name: _interface_map(
            component.inputs, component.name
        )
        for component in components
    }
    component_outputs = {
        component.name: _interface_map(
            component.outputs, component.name
        )
        for component in components
    }
    for component in components:
        if set(component_inputs[component.name]).intersection(
            component_outputs[component.name]
        ):
            raise ValueError(
                f"Component '{component.name}' declares the same signal as "
                "both input and output."
            )

    edges = []
    for interaction in decomposition.interactions:
        parts = re.split(r"\s*->\s*", interaction)
        if len(parts) != 2 or not all(parts):
            raise ValueError(
                f"Interaction '{interaction}' does not follow the required "
                "'source -> destination' format."
            )
        source = _interaction_source(
            parts[0],
            components,
            component_outputs,
            system_inputs,
        )
        destination = _resolve_interaction_destination(
            parts[1],
            components,
            component_inputs,
            component_outputs,
            system_outputs,
        )
        edges.append((interaction, source, destination))

    module_by_component = {
        module.component_name: module for module in component_modules
    }
    for component in components:
        module = module_by_component[component.name]
        if module.inputs != component.inputs or module.outputs != component.outputs:
            raise ValueError(
                f"RTL module '{module.module_name}' interfaces do not match "
                f"decomposed component '{component.name}'."
            )
    component_module_names = {
        module.module_name for module in component_modules
    }
    top_module_name = "system_top"
    while top_module_name in component_module_names:
        top_module_name += "_"
    output_nets: dict[tuple[str, str], str] = {}
    net_widths: dict[str, str | None] = {}
    output_destinations: dict[tuple[str, str], list] = {}
    system_output_routes: dict[str, list] = {
        name: [] for name in system_outputs
    }
    for _, source, destination in edges:
        if destination[0] == "component" and source[0] == "component":
            output_destinations.setdefault(
                (source[1], source[2]), []
            ).append(destination)
        elif destination[0] == "system_output":
            system_output_routes[destination[1]].append(source)

    for output_name, routes in system_output_routes.items():
        if len(routes) > 1:
            raise ValueError(
                f"System output '{output_name}' must have exactly one "
                f"interaction driver; found {len(routes)}."
            )
        if not routes:
            implicit_drivers = [
                (component.name, port_name, width)
                for component in components
                for port_name, width in component_outputs[component.name].items()
                if port_name == output_name
            ]
            if len(implicit_drivers) != 1:
                raise ValueError(
                    f"System output '{output_name}' must have exactly one "
                    "component driver or interaction."
                )
            component_name, port_name, width = implicit_drivers[0]
            if width != system_outputs[output_name]:
                raise ValueError(
                    f"Component output '{component_name}.{port_name}' width "
                    "does not match the system output."
                )
            system_output_routes[output_name].append((
                "component",
                component_name,
                port_name,
                _width_in_bits(width),
                None,
            ))

    output_system_destinations: dict[tuple[str, str], list] = {}
    direct_system_outputs: dict[tuple[str, str], str] = {}
    for output_name, routes in system_output_routes.items():
        source = routes[0]
        if source[0] == "component":
            source_component, source_port = source[1], source[2]
            if (source_component, source_port) not in {
                (component.name, port_name)
                for component in components
                for port_name in component_outputs[component.name]
            }:
                raise ValueError(
                    f"System output '{output_name}' is not driven by a "
                    "decomposed component output."
                )
            if source[3] != _width_in_bits(system_outputs[output_name]):
                raise ValueError(
                    f"Driver for system output '{output_name}' has a "
                    "mismatched signal width."
                )
            output_system_destinations.setdefault(
                (source_component, source_port), []
            ).append((output_name, source[4]))
            if (
                source_port == output_name
                and source[4] is None
                and component_outputs[source_component][source_port]
                == system_outputs[output_name]
            ):
                direct_system_outputs[(source_component, source_port)] = (
                    output_name
                )
        elif source[0] == "external":
            if source[3] != _width_in_bits(system_outputs[output_name]):
                raise ValueError(
                    f"Driver for system output '{output_name}' has a "
                    "mismatched signal width."
                )
        else:
            raise ValueError(
                f"Unsupported source for system output '{output_name}'."
            )

    used_names = set(system_inputs).union(system_outputs)
    for component in components:
        module = module_by_component[component.name]
        for port_name, width in component_outputs[component.name].items():
            output_key = (component.name, port_name)
            if output_key in direct_system_outputs:
                net_name = direct_system_outputs[output_key]
            elif (
                output_key in output_destinations
                or output_key in output_system_destinations
            ):
                base_name = f"net_{module.module_name}_{port_name}"
                net_name = re.sub(r"[^A-Za-z0-9_]", "_", base_name)
                suffix = 1
                while net_name in used_names:
                    suffix += 1
                    net_name = f"{base_name}_{suffix}"
                used_names.add(net_name)
                net_widths[net_name] = width
            else:
                base_name = f"net_{module.module_name}_{port_name}_unused"
                net_name = re.sub(r"[^A-Za-z0-9_]", "_", base_name)
                suffix = 1
                while net_name in used_names:
                    suffix += 1
                    net_name = f"{base_name}_{suffix}"
                used_names.add(net_name)
                net_widths[net_name] = width
            output_nets[(component.name, port_name)] = net_name

    input_edges: dict[tuple[str, str], list] = {}
    for interaction, source, destination in edges:
        if destination[0] == "component":
            input_edges.setdefault(
                (destination[1], destination[2]), []
            ).append((interaction, source, destination))

    instances = []
    for component in components:
        module = module_by_component[component.name]
        connections: dict[str, str] = {}
        for port_name, width in component_inputs[component.name].items():
            matches = input_edges.get((component.name, port_name), [])
            # Deduplicate identical sources
            unique_matches = []
            seen_sources = set()
            for m in matches:
                src_key = (m[1][0], m[1][1], m[1][2], m[1][4])
                if src_key not in seen_sources:
                    seen_sources.add(src_key)
                    unique_matches.append(m)
            matches = unique_matches

            if len(matches) > 1:
                # Disambiguate multi-driver contention using generic digital rules:
                # 1. Prefer direct external system input matching destination port name
                ext_match = [
                    m for m in matches if m[1][0] == "external" and m[1][1] == port_name
                ]
                if ext_match:
                    matches = [ext_match[0]]
                else:
                    # 2. Prefer source port name matching destination port name
                    name_match = [m for m in matches if m[1][2] == port_name]
                    if name_match:
                        matches = [name_match[0]]
                    else:
                        # 3. Prefer matching bit-width
                        width_match = [m for m in matches if m[1][3] == width]
                        matches = [width_match[0]] if width_match else [matches[0]]

            if matches:
                _, source, destination = matches[0]
                # Exact-Name Port Affinity Rule:
                # If the interaction has a mismatched signal name, but the source component
                # actually provides an output matching this destination port name exactly,
                # auto-correct to the exact matching port on the source component.
                if source[0] == "component" and source[2] != port_name:
                    if (source[1], port_name) in output_nets:
                        source = (
                            source[0],
                            source[1],
                            port_name,
                            component_outputs[source[1]][port_name],
                            None,
                        )

                dest_width = _width_in_bits(destination[3])
                if source[0] == "external":
                    signal_name = source[1] + (source[4] or "")
                else:
                    signal_name = (
                        output_nets[(source[1], source[2])]
                        + (source[4] or "")
                    )
                # Resilient bit-width handling
                if source[3] != dest_width:
                    if source[3] > dest_width and source[4] is None:
                        signal_name = f"{signal_name}[{dest_width - 1}:0]"
                    elif source[3] < dest_width and source[4] is None:
                        signal_name = (
                            f"{{{{{dest_width - source[3]}{{1'b0}}}}, {signal_name}}}"
                        )
            elif port_name in system_inputs:
                if width != system_inputs[port_name]:
                    if system_inputs[port_name] > width:
                        signal_name = f"{port_name}[{width - 1}:0]"
                    else:
                        signal_name = (
                            f"{{{{{width - system_inputs[port_name]}{{1'b0}}}}, {port_name}}}"
                        )
                else:
                    signal_name = port_name
            else:
                signal_name = f"{width}'b0" if width > 1 else "1'b0"
            connections[port_name] = signal_name

        for port_name in component_outputs[component.name]:
            connections[port_name] = output_nets[(component.name, port_name)]

        instances.append(ComponentRTLInstanceOutput(
            component_name=component.name,
            module_name=module.module_name,
            instance_name=f"u_{module.module_name}",
            port_connections=connections,
        ))

    lines = [f"module {top_module_name} ("]
    top_ports = list(system_inputs) + list(system_outputs)
    lines.extend(
        f"    {port}{',' if index < len(top_ports) - 1 else ''}"
        for index, port in enumerate(top_ports)
    )
    lines.append(");")
    for direction, interfaces in (
        ("input", system_inputs),
        ("output", system_outputs),
    ):
        for name, width in interfaces.items():
            width_text = f" {width}" if width else ""
            lines.append(f"{direction}{width_text} {name};")
    for net_name, width in net_widths.items():
        width_text = f" {width}" if width else ""
        lines.append(f"wire{width_text} {net_name};")
    for output_name, routes in system_output_routes.items():
        source = routes[0]
        if source[0] == "component":
            source_name = output_nets[(source[1], source[2])]
        else:
            source_name = source[1]
        source_name += source[4] or ""
        if source_name != output_name:
            lines.append(f"assign {output_name} = {source_name};")

    for instance in instances:
        lines.append(
            f"{instance.module_name} {instance.instance_name} ("
        )
        ports = list(instance.port_connections.items())
        lines.extend(
            f"    .{port}({signal})"
            f"{',' if index < len(ports) - 1 else ''}"
            for index, (port, signal) in enumerate(ports)
        )
        lines.append(");")
    lines.append("endmodule")
    top_rtl = "\n".join(lines)
    _validate_top_level_rtl(
        top_rtl,
        top_module_name,
        system_inputs,
        system_outputs,
        instances,
    )
    return top_module_name, top_rtl, instances


def _validate_top_level_rtl(
    rtl_code: str,
    top_module_name: str,
    system_inputs: dict[str, str | None],
    system_outputs: dict[str, str | None],
    instances: list[ComponentRTLInstanceOutput],
) -> None:
    top = RTLGenerationOutput(module_name=top_module_name, rtl_code=rtl_code)
    validate_rtl_output(
        top,
        top_module_name,
        [name + (width or "") for name, width in system_inputs.items()],
        [name + (width or "") for name, width in system_outputs.items()],
    )
    for instance in instances:
        instance_pattern = re.compile(
            r"\b" + re.escape(instance.module_name) + r"\s+"
            + re.escape(instance.instance_name) + r"\s*\((.*?)\)\s*;",
            re.S,
        )
        matches = instance_pattern.findall(rtl_code)
        if len(matches) != 1:
            raise ValueError(
                f"Top-level RTL must instantiate '{instance.module_name}' exactly once."
            )
        actual_connections = {
            port: signal
            for port, signal in re.findall(
                r"\.([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*"
                r"([A-Za-z_][A-Za-z0-9_]*(?:\[[0-9]+:[0-9]+\])?)\s*\)",
                matches[0],
            )
        }
        if actual_connections != instance.port_connections:
            raise ValueError(
                f"Top-level connections for component '{instance.component_name}' "
                "do not match the validated connection map."
            )


def _generate_component_rtl(
    specification: str,
    decomposed: Component,
    component_pseudocode: ComponentPseudocodeOutput,
    llm,
    raw_output_dir: str | Path | None,
    *,
    experimental: bool = False,
    raw_output_name: str | None = None,
    component_description: DescriptionOutput | None = None,
    status_details: dict[str, str] | None = None,
    reflection_feedback: Any = None,
) -> tuple[ComponentRTLModuleOutput, list[str]]:
    """Generate and structurally validate one component module."""

    if status_details is not None:
        status_details["failure_stage"] = "generation"
    module_result = ComponentRTLModuleOutput(
        component_name=decomposed.name,
        module_name=component_pseudocode.module_name,
        inputs=decomposed.inputs,
        outputs=decomposed.outputs,
    )
    system_prompt = SYSTEM_PROMPT
    pseudocode_label = "VALIDATED COMPONENT PSEUDOCODE"
    source_label = "validated pseudocode"
    if experimental:
        system_prompt = (
            SYSTEM_PROMPT
            .replace(
                "ONE validated component pseudocode block",
                "ONE supplied component pseudocode block",
            )
            .replace(
                "The VALIDATED PSEUDOCODE is the implementation guide.",
                "The supplied pseudocode is an unverified implementation guide.",
            )
            .replace(
                "Copy the pseudocode component's assumptions exactly. Return an empty\n"
                "unresolved_issues array; if a conflict or unresolved behavior prevents\n"
                "faithful RTL, report it there and do not claim a successful implementation.",
                "Copy the supplied pseudocode assumptions exactly. Report "
                "unresolved source requirements and any additional "
                "uncertainty in unresolved_issues. Treat this RTL only as an "
                "unverified draft.",
            )
        )
        pseudocode_label = "SUPPLIED COMPONENT PSEUDOCODE (NOT VALIDATED)"
        source_label = "supplied pseudocode"

    response_instruction = (
        "Set language to \"Verilog\", copy assumptions exactly from the "
        f"{source_label}, and return no unresolved issues."
    )
    if experimental:
        response_instruction = (
            'Set language to "Verilog", copy assumptions exactly from the '
            "supplied pseudocode, and report any unresolved source "
            "requirements or additional uncertainty in unresolved_issues."
        )

    description_context = ""
    if component_description is not None:
        description_context = (
            "COMPONENT DESCRIPTION (SUPPORTING CONTEXT):\n"
            f"{json.dumps(component_description.model_dump(), indent=2, ensure_ascii=False)}\n"
            "Use this only as supporting context; do not override the original "
            "specification or supplied pseudocode.\n\n"
        )

    reflection_context = ""
    if reflection_feedback:
        fb_items = []
        if isinstance(reflection_feedback, str):
            if reflection_feedback.strip():
                fb_items.append(reflection_feedback.strip())
        elif isinstance(reflection_feedback, (list, tuple)):
            for item in reflection_feedback:
                if str(item).strip():
                    fb_items.append(str(item).strip())
        elif hasattr(reflection_feedback, "feedback") or isinstance(reflection_feedback, dict):
            general = getattr(reflection_feedback, "feedback", None) or (
                reflection_feedback.get("feedback") if isinstance(reflection_feedback, dict) else []
            )
            comp_fb = getattr(reflection_feedback, "component_feedback", None) or (
                reflection_feedback.get("component_feedback") if isinstance(reflection_feedback, dict) else {}
            )
            if general:
                for item in general:
                    if str(item).strip():
                        fb_items.append(str(item).strip())
            if isinstance(comp_fb, dict):
                module_name = component_pseudocode.module_name
                comp_name = decomposed.name
                specific = comp_fb.get(module_name) or comp_fb.get(comp_name) or []
                if specific:
                    fb_items.append(f"Specific fixes for {module_name}:")
                    for item in specific:
                        if str(item).strip():
                            fb_items.append(f"  - {str(item).strip()}")
        if fb_items:
            reflection_context = (
                "REFLECTION CORRECTION FEEDBACK (CRITICAL FIXES REQUIRED):\n"
                "The previous RTL version failed static verification against the hardware specification.\n"
                "You MUST apply the following corrections to fix all identified issues:\n"
                + "\n".join(f"- {item}" for item in fb_items)
                + "\n\n"
            )

    prompt = f"""
{system_prompt}

ORIGINAL HARDWARE SPECIFICATION (PRIMARY SOURCE):
{specification}

DECOMPOSED COMPONENT INTERFACE:
{json.dumps(decomposed.model_dump(), indent=2, ensure_ascii=False)}

{description_context}{reflection_context}{pseudocode_label}:
{json.dumps(component_pseudocode.model_dump(), indent=2, ensure_ascii=False)}

Generate exactly one synthesizable component module named
'{component_pseudocode.module_name}'. Preserve these input and output arrays
exactly: inputs={json.dumps(decomposed.inputs)}, outputs={json.dumps(decomposed.outputs)}.
Use non-ANSI Verilog-2001 port declarations, one input or output per line.
Do not add ports or generate any top-level integration module.
Return a JSON object with exactly module_name, language, rtl_code,
assumptions, and unresolved_issues. {response_instruction}
"""
    response_unresolved_issues = []
    raw_content = ""
    try:
        response = llm.invoke(prompt)
        raw_content = extract_response_content(response)
        save_raw_response(
            raw_content,
            raw_output_dir,
            component_name=raw_output_name or component_pseudocode.module_name,
        )
        data = json.loads(extract_json(raw_content))
        if not isinstance(data.get("module_name"), str):
            raise ValueError("RTL response module_name must be a string.")
        if data.get("language") != "Verilog":
            raise ValueError("RTL response language must be 'Verilog'.")
        if not isinstance(data.get("rtl_code"), str):
            raise ValueError("RTL response rtl_code must be a string.")
        module_result.module_name = data["module_name"]
        module_result.rtl_code = data["rtl_code"]
        if status_details is not None:
            status_details["failure_stage"] = "response_validation"
        if not isinstance(data.get("assumptions"), list) or not all(
            isinstance(item, str) for item in data["assumptions"]
        ):
            raise ValueError("RTL response assumptions must be an array of strings.")
        if data["assumptions"] != component_pseudocode.assumptions:
            raise ValueError(
                "RTL assumptions do not exactly match the validated "
                "component pseudocode."
            )
        if not isinstance(data.get("unresolved_issues"), list) or not all(
            isinstance(item, str) for item in data["unresolved_issues"]
        ):
            raise ValueError(
                "RTL response unresolved_issues must be an array of strings."
            )
        response_unresolved_issues = list(data["unresolved_issues"])
        if response_unresolved_issues and not experimental:
            raise ValueError(
                "RTL generation reported unresolved issues: "
                + "; ".join(response_unresolved_issues)
            )
        if status_details is not None:
            status_details["failure_stage"] = "interface_validation"
        validate_rtl_output(
            module_result,
            expected_module_name=component_pseudocode.module_name,
            expected_inputs=decomposed.inputs,
            expected_outputs=decomposed.outputs,
        )
        module_result.generation_status = "completed"
        if status_details is not None:
            status_details["failure_stage"] = "completed"
    except Exception as error:
        module_result.generation_status = "Failed"
        module_result.generation_error = f"{type(error).__name__}: {error}"
        if raw_content:
            print(
                f"RTL generation failed for component '{decomposed.name}': "
                f"{module_result.generation_error}"
            )

    return module_result, response_unresolved_issues


def _integrate_component_rtl(
    decomposition_components: list,
    component_modules: list[ComponentRTLModuleOutput],
    decomposition: DecompositionOutput,
    understanding: Understanding,
) -> tuple[str, str, list[ComponentRTLInstanceOutput], str]:
    """Build and validate the wiring-only top-level module and combined RTL."""

    top_module_name, top_rtl, instances = _build_top_level_rtl(
        decomposition_components,
        component_modules,
        decomposition,
        understanding,
    )
    complete_rtl = "\n\n".join(
        [module.rtl_code for module in component_modules] + [top_rtl]
    )
    expected_module_names = [
        module.module_name for module in component_modules
    ] + [top_module_name]
    actual_module_names = re.findall(
        r"\bmodule\s+(?:automatic\s+)?([A-Za-z_][A-Za-z0-9_]*)",
        re.sub(r"/\*.*?\*/|//[^\r\n]*", "", complete_rtl, flags=re.S),
    )
    if actual_module_names != expected_module_names:
        raise ValueError(
            "Integrated RTL must contain exactly one module for each "
            "component and one top-level module."
        )
    return top_module_name, top_rtl, instances, complete_rtl


def generate_rtl(
    specification: str,
    pseudocode: PseudocodeGenerationOutput,
    *,
    decomposition: DecompositionOutput | None = None,
    understanding: Understanding | None = None,
    raw_output_dir: str | Path | None = None,
    reflection_feedback: Any = None,
) -> RTLGenerationOutput:
    """Generate component RTL and a wiring-only top-level module."""

    decomposition_components = decomposition.components if decomposition else []
    pseudocode_by_name = {
        component.component_name: component
        for component in pseudocode.components
    }
    failures = []
    if not specification.strip():
        failures.append("The original specification is empty.")
    if decomposition is None:
        failures.append("The decomposition is required for component RTL integration.")
    if understanding is None:
        failures.append("Understanding is required for the top-level interface.")
    if pseudocode.generation_status != "completed":
        failures.append(
            f"Pseudocode generation status is {pseudocode.generation_status}."
        )
    if pseudocode.validation_status not in {"Passed", "Warnings"}:
        failures.append(
            f"Pseudocode validation status is {pseudocode.validation_status}."
        )
    for issue in pseudocode.validation_issues:
        if issue.get("severity") == "error":
            failures.append(
                f"[{issue.get('code', 'VALIDATION_ERROR')}] "
                f"{issue.get('message', 'Pseudocode validation failed.')}"
            )
    if pseudocode.unresolved_issues:
        failures.extend(
            f"Unresolved pseudocode requirement: {issue}"
            for issue in pseudocode.unresolved_issues
        )

    if decomposition is not None:
        expected_names = [component.name for component in decomposition_components]
        actual_names = [component.component_name for component in pseudocode.components]
        module_names = [component.module_name for component in pseudocode.components]
        if (
            not expected_names
            or len(expected_names) != len(set(expected_names))
            or len(actual_names) != len(set(actual_names))
            or len(module_names) != len(set(module_names))
            or actual_names != expected_names
        ):
            failures.append(
                "Pseudocode components must correspond one-to-one, in order, "
                "with the decomposed components."
            )
        for decomposed in decomposition_components:
            generated = pseudocode_by_name.get(decomposed.name)
            if generated is None:
                failures.append(
                    f"Missing pseudocode for component '{decomposed.name}'."
                )
                continue
            if generated.inputs != decomposed.inputs or generated.outputs != decomposed.outputs:
                failures.append(
                    f"Component '{decomposed.name}' pseudocode interface does "
                    "not match the decomposition."
                )
            if generated.generation_status != "completed":
                failures.append(
                    f"Component '{decomposed.name}' pseudocode generation "
                    f"status is {generated.generation_status}."
                )
            if generated.validation_status not in {"Passed", "Warnings"}:
                failures.append(
                    f"Component '{decomposed.name}' pseudocode validation "
                    f"status is {generated.validation_status}."
                )
            if any(
                issue.get("severity") == "error"
                for issue in generated.validation_issues
            ):
                failures.append(
                    f"Component '{decomposed.name}' has pseudocode validation errors."
                )
            if generated.unresolved_issues:
                failures.extend(
                    f"Component '{decomposed.name}' has unresolved requirement: {issue}"
                    for issue in generated.unresolved_issues
                )
            declarations = re.findall(
                r"^\s*MODULE\s+([A-Za-z_][A-Za-z0-9_]*)\s*$",
                "\n".join(generated.pseudocode),
                re.I | re.M,
            )
            if declarations != [generated.module_name]:
                failures.append(
                    f"Component '{decomposed.name}' pseudocode module declaration "
                    "does not match its module_name."
                )

    if decomposition is not None and not decomposition_components:
        failures.append("The decomposition contains no components.")

    blocked_modules = []
    if failures:
        for component in decomposition_components:
            generated = pseudocode_by_name.get(component.name)
            blocked_modules.append(ComponentRTLModuleOutput(
                component_name=component.name,
                module_name=generated.module_name if generated else "",
                inputs=component.inputs,
                outputs=component.outputs,
                generation_status="blocked",
                generation_error="; ".join(failures),
            ))
        return RTLGenerationOutput(
            generation_status="Failed",
            generation_issues=failures,
            component_modules=blocked_modules,
            interactions=decomposition.interactions if decomposition else [],
            assumptions=pseudocode.assumptions,
            unresolved_issues=pseudocode.unresolved_issues,
        )

    try:
        llm = get_llm("rtl_generation")
    except Exception as error:
        message = f"{type(error).__name__}: {error}"
        blocked_modules = [
            ComponentRTLModuleOutput(
                component_name=component.name,
                module_name=pseudocode_by_name[component.name].module_name,
                inputs=component.inputs,
                outputs=component.outputs,
                generation_status="blocked",
                generation_error=message,
            )
            for component in decomposition_components
        ]
        return RTLGenerationOutput(
            generation_status="Failed",
            generation_issues=[message],
            component_modules=blocked_modules,
            interactions=decomposition.interactions,
            assumptions=pseudocode.assumptions,
        )

    component_modules: list[ComponentRTLModuleOutput] = []
    for decomposed, component_pseudocode in zip(
        decomposition_components,
        pseudocode.components,
    ):
        module_result, _ = _generate_component_rtl(
            specification,
            decomposed,
            component_pseudocode,
            llm,
            raw_output_dir,
            reflection_feedback=reflection_feedback,
        )
        component_modules.append(module_result)

    generation_issues = [
        f"Component '{module.component_name}': {module.generation_error}"
        for module in component_modules
        if module.generation_status != "completed"
    ]
    if generation_issues:
        return RTLGenerationOutput(
            generation_status="Failed",
            generation_issues=generation_issues,
            component_modules=component_modules,
            interactions=decomposition.interactions,
            assumptions=pseudocode.assumptions,
        )

    try:
        top_module_name, top_rtl, instances, complete_rtl = _integrate_component_rtl(
            decomposition_components,
            component_modules,
            decomposition,
            understanding,
        )
    except Exception as error:
        return RTLGenerationOutput(
            generation_status="Failed",
            generation_issues=[f"{type(error).__name__}: {error}"],
            component_modules=component_modules,
            interactions=decomposition.interactions,
            assumptions=pseudocode.assumptions,
        )

    result = RTLGenerationOutput(
        module_name=top_module_name,
        rtl_code=complete_rtl,
        component_modules=component_modules,
        component_instances=instances,
        interactions=decomposition.interactions,
        generation_status="completed",
        generation_issues=[],
        assumptions=pseudocode.assumptions,
    )
    print("\nComponent RTL generation and top-level integration completed.")
    print(
        f"Generated {len(component_modules)} component module(s) "
        f"and the {top_module_name} integration module."
    )
    return result

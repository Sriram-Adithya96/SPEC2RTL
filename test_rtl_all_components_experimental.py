import argparse
import hashlib
import json
import re
from pathlib import Path
from types import SimpleNamespace

from src.agents.rtl_generation import (
    SYSTEM_PROMPT,
    _build_top_level_rtl,
    _interaction_destination,
    _interaction_source,
    _interface_map,
    _parse_signal,
    _width_in_bits,
    extract_json,
    extract_response_content,
    get_llm,
    save_raw_response,
    validate_rtl_output,
)
from src.ingestion import ingest_spec
from src.schemas import (
    ComponentRTLModuleOutput,
    DecompositionOutput,
    PseudocodeGenerationOutput,
    Understanding,
)


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
DEFAULT_SPEC_PATH = Path(
    r"C:\Users\srira\OneDrive\Desktop\ps spec2rtl\fake_spec2rtl_spec (1).docx"
)
OUTPUT_PATH = OUTPUT_DIR / "rtl_generation_experimental.json"
EXPERIMENTAL_LABEL = "EXPERIMENTAL — pseudocode validation has not passed"


def load_json(path: Path):
    if not path.is_file():
        raise FileNotFoundError(f"Required JSON artifact not found: {path}")
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_specification(spec_path: Path) -> str:
    if not spec_path.is_file():
        raise FileNotFoundError(f"Specification document not found: {spec_path}")
    docs, _, _ = ingest_spec(str(spec_path))
    specification = "\n\n".join(doc.page_content for doc in docs).strip()
    if not specification:
        raise ValueError("The specification text is empty.")
    return specification


def build_prompt(specification, component, component_pseudocode) -> str:
    return f"""
{SYSTEM_PROMPT}

ORIGINAL HARDWARE SPECIFICATION (PRIMARY SOURCE):
{specification}

DECOMPOSED COMPONENT INTERFACE:
{json.dumps(component.model_dump(), indent=2, ensure_ascii=False)}

SAVED COMPONENT PSEUDOCODE:
{json.dumps(component_pseudocode.model_dump(), indent=2, ensure_ascii=False)}

Generate exactly one synthesizable Verilog-2001 component module named
'{component_pseudocode.module_name}'. Preserve these interface arrays and
their order exactly: inputs={json.dumps(component.inputs)},
outputs={json.dumps(component.outputs)}. Use a non-ANSI port list containing
only port names, followed by separate input/output declarations, one per line.
Do not add ports or create a top-level integration module.
Return a JSON object with exactly module_name, language, rtl_code,
assumptions, and unresolved_issues. Set language to "Verilog", copy
assumptions exactly from the saved pseudocode, and return no unresolved
issues.
"""


def convert_ansi_to_non_ansi(rtl_code: str) -> str:
    module_match = re.search(
        r"\bmodule\s+(?:automatic\s+)?"
        r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*"
        r"\((?P<ports>.*?)\)\s*;",
        rtl_code,
        re.DOTALL,
    )
    if module_match is None:
        raise ValueError("RTL must contain a module declaration with a port list.")

    port_entries = [
        item.strip() for item in module_match.group("ports").split(",")
    ]
    if all(
        re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", port)
        for port in port_entries
    ):
        return rtl_code

    port_names = []
    declarations = []
    inherited = None
    declaration_pattern = re.compile(
        r"^(input|output|inout)\s+"
        r"(?:(wire|reg|tri)\s+)?"
        r"(?:(signed|unsigned)\s+)?"
        r"(\[[0-9]+\s*:\s*[0-9]+\]\s*)?"
        r"([A-Za-z_][A-Za-z0-9_]*)$"
    )
    for port in port_entries:
        match = declaration_pattern.fullmatch(port)
        if match:
            direction, net_type, sign, width, name = match.groups()
            width = width.strip() if width else None
            inherited = direction, net_type, sign, width
        else:
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", port) is None:
                raise ValueError(f"Cannot convert ANSI port declaration '{port}'.")
            if inherited is None:
                raise ValueError(
                    f"ANSI port '{port}' has no direction/type declaration."
                )
            name = port
            direction, net_type, sign, width = inherited

        port_names.append(name)
        parts = [direction]
        if net_type:
            parts.append(net_type)
        if sign:
            parts.append(sign)
        if width:
            parts.append(width)
        parts.append(name)
        declarations.append(" ".join(parts) + ";")

    header = (
        f"module {module_match.group('name')} ({', '.join(port_names)});"
        f"\n{chr(10).join(declarations)}"
    )
    return (
        rtl_code[:module_match.start()]
        + header
        + rtl_code[module_match.end():]
    )


def _validate_response(
    data: dict,
    component,
    component_pseudocode,
) -> tuple[ComponentRTLModuleOutput, dict]:
    for field in ("module_name", "language", "rtl_code"):
        if not isinstance(data.get(field), str):
            raise ValueError(f"RTL response {field} must be a string.")
    if data["language"] != "Verilog":
        raise ValueError("RTL response language must be 'Verilog'.")
    if not isinstance(data.get("assumptions"), list) or not all(
        isinstance(item, str) for item in data["assumptions"]
    ):
        raise ValueError("RTL response assumptions must be an array of strings.")
    if data["assumptions"] != component_pseudocode.assumptions:
        raise ValueError(
            "RTL assumptions do not exactly match the saved component pseudocode."
        )
    if not isinstance(data.get("unresolved_issues"), list) or not all(
        isinstance(item, str) for item in data["unresolved_issues"]
    ):
        raise ValueError(
            "RTL response unresolved_issues must be an array of strings."
        )
    if data["unresolved_issues"]:
        raise ValueError(
            "RTL generation reported unresolved issues: "
            + "; ".join(data["unresolved_issues"])
        )

    converted_rtl = convert_ansi_to_non_ansi(data["rtl_code"])
    module_result = ComponentRTLModuleOutput(
        component_name=component.name,
        module_name=data["module_name"],
        inputs=component.inputs,
        outputs=component.outputs,
        rtl_code=converted_rtl,
    )
    validate_rtl_output(
        module_result,
        expected_module_name=component_pseudocode.module_name,
        expected_inputs=component.inputs,
        expected_outputs=component.outputs,
    )
    return module_result, {
        "language": data["language"],
        "assumptions": data["assumptions"],
        "unresolved_issues": data["unresolved_issues"],
    }


def _reusable_candidates(component_name: str, combined_result: dict | None):
    for path in OUTPUT_DIR.glob("rtl_*_experimental.json"):
        if path == OUTPUT_PATH:
            continue
        candidate = load_json(path)
        if candidate.get("component_name") == component_name:
            yield candidate
    if combined_result is not None:
        for item in combined_result.get("components", []):
            if item.get("component_name") == component_name:
                yield item


def _try_reuse(
    component,
    component_pseudocode,
    specification_hash: str,
    combined_result: dict | None,
):
    for candidate in _reusable_candidates(component.name, combined_result):
        if (
            candidate.get("specification_sha256") != specification_hash
            or candidate.get("component_name") != component.name
            or candidate.get("module_name") != component_pseudocode.module_name
            or candidate.get("inputs") != component.inputs
            or candidate.get("outputs") != component.outputs
            or candidate.get("assumptions") != component_pseudocode.assumptions
            or candidate.get("validation_result") is not True
        ):
            continue
        data = {
            "module_name": candidate["module_name"],
            "language": candidate.get("language", "Verilog"),
            "rtl_code": candidate.get("rtl_code"),
            "assumptions": candidate["assumptions"],
            "unresolved_issues": candidate.get("unresolved_issues", []),
        }
        try:
            module_result, metadata = _validate_response(
                data, component, component_pseudocode
            )
        except Exception:
            continue
        return module_result, metadata
    return None


def _failed_component(component, error: Exception, component_pseudocode=None) -> dict:
    return {
        "component_name": component.name,
        "module_name": (
            component_pseudocode.module_name if component_pseudocode else ""
        ),
        "inputs": list(component.inputs),
        "outputs": list(component.outputs),
        "assumptions": (
            list(component_pseudocode.assumptions)
            if component_pseudocode
            else []
        ),
        "unresolved_issues": [],
        "generation_status": "failed",
        "validation_status": "failed",
        "validation_errors": [f"{type(error).__name__}: {error}"],
        "rtl_code": "",
        "raw_response_path": None,
    }


def _normalize_understanding_interfaces(understanding: Understanding):
    def normalize(items: list[str], direction: str) -> list[str]:
        interfaces = []
        pattern = re.compile(
            r"^\s*([A-Za-z_][A-Za-z0-9_]*"
            r"(?:\[[0-9]+:[0-9]+\])?)"
        )
        for item in items:
            match = pattern.match(item)
            if match is None:
                raise ValueError(
                    f"Cannot parse system {direction} interface '{item}'."
                )
            interfaces.append(match.group(1))
        return interfaces

    return understanding.model_copy(update={
        "inputs": normalize(understanding.inputs, "input"),
        "outputs": normalize(understanding.outputs, "output"),
    })


def integrate_saved_components(
    specification: str,
    specification_hash: str,
    decomposition: DecompositionOutput,
    understanding: Understanding,
    experimental_data: dict,
) -> dict:
    errors = []
    component_errors = []
    records = experimental_data.get("components")
    if not isinstance(records, list):
        records = []
        component_errors.append(
            "Experimental component records are missing or invalid."
        )

    by_name: dict[str, list[dict]] = {}
    for record in records:
        if isinstance(record, dict) and isinstance(
            record.get("component_name"), str
        ):
            by_name.setdefault(record["component_name"], []).append(record)

    component_modules = []
    module_names = set()
    for component in decomposition.components:
        matches = by_name.get(component.name, [])
        if len(matches) != 1:
            component_errors.append(
                f"Component '{component.name}' has {len(matches)} saved RTL "
                "records; expected exactly one."
            )
            continue
        record = matches[0]
        if (
            record.get("generation_status")
            not in {"completed", "reused", "validated_from_raw"}
            or record.get("validation_status") != "passed"
        ):
            component_errors.append(
                f"Component '{component.name}' did not pass component-level "
                "RTL structural validation."
            )
            component_errors.extend(
                f"Component '{component.name}': {error}"
                for error in record.get("validation_errors", [])
            )
            continue
        if (
            record.get("specification_sha256") != specification_hash
            or experimental_data.get("specification_sha256")
            != specification_hash
        ):
            component_errors.append(
                f"Component '{component.name}' RTL was generated for a "
                "different specification."
            )
            continue
        if record.get("inputs") != component.inputs:
            component_errors.append(
                f"Component '{component.name}' RTL inputs do not match "
                "decomposition interfaces."
            )
            continue
        if record.get("outputs") != component.outputs:
            component_errors.append(
                f"Component '{component.name}' RTL outputs do not match "
                "decomposition interfaces."
            )
            continue
        module_name = record.get("module_name")
        if not isinstance(module_name, str) or not module_name:
            component_errors.append(
                f"Component '{component.name}' has no valid RTL module name."
            )
            continue
        if module_name in module_names:
            component_errors.append(
                f"Duplicate RTL module name '{module_name}' in saved component "
                "records."
            )
            continue
        module_names.add(module_name)
        module = ComponentRTLModuleOutput(
            component_name=component.name,
            module_name=module_name,
            inputs=component.inputs,
            outputs=component.outputs,
            rtl_code=record.get("rtl_code", ""),
            generation_status="completed",
        )
        try:
            validate_rtl_output(
                module,
                expected_module_name=module_name,
                expected_inputs=component.inputs,
                expected_outputs=component.outputs,
            )
        except Exception as error:
            component_errors.append(
                f"Component '{component.name}' RTL validation failed: "
                f"{type(error).__name__}: {error}"
            )
            continue
        component_modules.append(module)

    expected_names = [component.name for component in decomposition.components]
    saved_names = [record.get("component_name") for record in records]
    for saved_name in saved_names:
        if saved_name not in expected_names:
            component_errors.append(
                f"Saved RTL component '{saved_name}' is not in the decomposition."
            )

    internal_interactions = []
    output_interactions: dict[str, list[tuple[str, tuple]]] = {}
    if not component_errors and len(component_modules) == len(
        decomposition.components
    ):
        try:
            normalized_understanding = _normalize_understanding_interfaces(
                understanding
            )
            system_outputs = _interface_map(
                normalized_understanding.outputs, "Understanding outputs"
            )
            component_outputs = {
                component.name: _interface_map(
                    component.outputs, component.name
                )
                for component in decomposition.components
            }
            component_inputs = {
                component.name: _interface_map(
                    component.inputs, component.name
                )
                for component in decomposition.components
            }
            input_interaction_counts: dict[tuple[str, str], int] = {}
            for interaction in decomposition.interactions:
                parts = re.split(r"\s*->\s*", interaction)
                if len(parts) != 2 or not all(parts):
                    raise ValueError(
                        f"Interaction '{interaction}' does not follow the "
                        "'source -> destination' format."
                    )
                try:
                    destination_name, destination_width = _parse_signal(
                        parts[1]
                    )
                except ValueError:
                    destination_name, destination_width = "", None
                if destination_name not in system_outputs:
                    destination = _interaction_destination(
                        parts[1],
                        decomposition.components,
                        component_inputs,
                    )
                    key = (destination[0], destination[1])
                    input_interaction_counts[key] = (
                        input_interaction_counts.get(key, 0) + 1
                    )
                    internal_interactions.append(interaction)
                    continue

                source = _interaction_source(
                    parts[0],
                    decomposition.components,
                    component_outputs,
                    {},
                )
                if source[0] != "component":
                    raise ValueError(
                        f"System output '{destination_name}' must be driven "
                        "by a component output."
                    )
                if source[2] != destination_name:
                    raise ValueError(
                        f"System output '{destination_name}' is connected from "
                        f"component port '{source[1]}.{source[2]}'; the existing "
                        "integration helper requires a same-named output port."
                    )
                if source[4] is not None:
                    raise ValueError(
                        f"System output '{destination_name}' cannot use a "
                        "sliced source."
                    )
                if destination_width != system_outputs[destination_name]:
                    raise ValueError(
                        f"System output interaction destination "
                        f"'{parts[1]}' has a width that does not match the "
                        "declared system output."
                    )
                if source[3] != _width_in_bits(system_outputs[destination_name]):
                    raise ValueError(
                        f"System output '{destination_name}' has an "
                        "incompatible component driver width."
                    )
                output_interactions.setdefault(destination_name, []).append(
                    (interaction, source)
                )

            for output_name in system_outputs:
                matches = output_interactions.get(output_name, [])
                if len(matches) != 1:
                    raise ValueError(
                        f"System output '{output_name}' must have exactly one "
                        f"decomposition interaction; found {len(matches)}."
                    )
            for component in decomposition.components:
                for input_name in component_inputs[component.name]:
                    count = input_interaction_counts.get(
                        (component.name, input_name), 0
                    )
                    if count != 1:
                        raise ValueError(
                            f"Component input '{component.name}.{input_name}' "
                            "must have exactly one decomposition interaction; "
                            f"found {count}."
                        )

            helper_decomposition = decomposition.model_copy(update={
                "interactions": internal_interactions,
            })
            top_name, top_rtl, instances = _build_top_level_rtl(
                decomposition.components,
                component_modules,
                helper_decomposition,
                normalized_understanding,
            )
        except Exception as error:
            errors.append(f"{type(error).__name__}: {error}")
        else:
            combined_rtl = "\n\n".join(
                [module.rtl_code for module in component_modules] + [top_rtl]
            )
            return {
                "label": EXPERIMENTAL_LABEL,
                "production_ready": False,
                "specification_sha256": specification_hash,
                "pseudocode_validation_status": experimental_data.get(
                    "pseudocode_validation_status"
                ),
                "component_validation": "passed",
                "integration_status": "passed",
                "validation_status": "passed",
                "generation_status": "completed",
                "errors": [],
                "top_module_name": top_name,
                "component_modules": [
                    module.model_dump() for module in component_modules
                ],
                "component_instances": [
                    instance.model_dump() for instance in instances
                ],
                "interactions": decomposition.interactions,
                "top_level_rtl": top_rtl,
                "integrated_rtl": combined_rtl,
            }

    return {
        "label": EXPERIMENTAL_LABEL,
        "production_ready": False,
        "specification_sha256": specification_hash,
        "pseudocode_validation_status": experimental_data.get(
            "pseudocode_validation_status"
        ),
        "component_validation": (
            "failed" if component_errors else "passed"
        ),
        "integration_status": "failed",
        "validation_status": "failed",
        "generation_status": "failed",
        "errors": component_errors + errors or [
            "Component RTL set does not correspond one-to-one with the decomposition."
        ],
        "component_modules": [
            module.model_dump() for module in component_modules
        ],
        "component_instances": [],
        "interactions": decomposition.interactions,
        "top_level_rtl": "",
        "integrated_rtl": "",
    }


def _raw_response_path(component_name: str) -> Path:
    safe_name = re.sub(
        r"[^A-Za-z0-9_-]+", "_", component_name
    ).strip("_")
    return OUTPUT_DIR / f"rtl_generation_raw_{safe_name}.txt"


def generate_component(component, component_pseudocode, specification, spec_hash,
                       combined_result, *, validate_raw_only=False):
    record = {
        "component_name": component.name,
        "module_name": component_pseudocode.module_name,
        "inputs": component.inputs,
        "outputs": component.outputs,
        "assumptions": list(component_pseudocode.assumptions),
        "unresolved_issues": [],
        "generation_status": "failed",
        "validation_status": "failed",
        "validation_errors": [],
        "rtl_code": "",
        "raw_response_path": None,
        "specification_sha256": spec_hash,
    }

    try:
        if validate_raw_only:
            raw_path = _raw_response_path(component.name)
            if not raw_path.is_file():
                raise FileNotFoundError(
                    f"Saved raw RTL response not found for component "
                    f"'{component.name}': {raw_path}"
                )
            raw_content = raw_path.read_text(encoding="utf-8")
        else:
            reused = _try_reuse(
                component, component_pseudocode, spec_hash, combined_result
            )
            if reused is not None:
                module_result, metadata = reused
                record.update({
                    **metadata,
                    "rtl_code": module_result.rtl_code,
                    "generation_status": "reused",
                    "validation_status": "passed",
                })
                return record

            prompt = build_prompt(specification, component, component_pseudocode)
            response = get_llm("rtl_generation").invoke(prompt)
            raw_content = extract_response_content(response)
            raw_path = save_raw_response(
                raw_content,
                OUTPUT_DIR,
                component_name=component.name,
            )
        record["raw_response_path"] = str(raw_path)
        data = json.loads(extract_json(raw_content))
        module_result, metadata = _validate_response(
            data, component, component_pseudocode
        )
        record.update({
            **metadata,
            "rtl_code": module_result.rtl_code,
            "generation_status": (
                "validated_from_raw" if validate_raw_only else "completed"
            ),
            "validation_status": "passed",
        })
    except Exception as error:
        record["validation_errors"].append(
            f"{type(error).__name__}: {error}"
        )
    return record


def main():
    parser = argparse.ArgumentParser(
        description="Generate experimental RTL for saved decomposed components."
    )
    parser.add_argument(
        "--spec",
        type=Path,
        default=DEFAULT_SPEC_PATH,
        help="Original specification file (defaults to the saved APU spec).",
    )
    parser.add_argument(
        "--validate-raw-only",
        action="store_true",
        help=(
            "Convert and validate saved per-component raw RTL responses "
            "without making LLM calls or reusing generated RTL."
        ),
    )
    parser.add_argument(
        "--integrate-only",
        action="store_true",
        help=(
            "Integrate and validate saved component RTL without making any "
            "LLM calls."
        ),
    )
    args = parser.parse_args()

    specification = load_specification(args.spec)
    specification_hash = hashlib.sha256(
        specification.encode("utf-8")
    ).hexdigest()
    decomposition = DecompositionOutput.model_validate(
        load_json(OUTPUT_DIR / "decomposition.json")
    )
    pseudocode = PseudocodeGenerationOutput.model_validate(
        load_json(OUTPUT_DIR / "pseudocode.json")
    )

    if args.integrate_only:
        understanding = Understanding.model_validate(
            load_json(OUTPUT_DIR / "understanding.json")
        )
        experimental_data = load_json(OUTPUT_PATH)
        result = integrate_saved_components(
            specification,
            specification_hash,
            decomposition,
            understanding,
            experimental_data,
        )
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        integration_path = OUTPUT_DIR / "top_level_rtl_experimental.json"
        integration_path.write_text(
            json.dumps(result, indent=4, ensure_ascii=False),
            encoding="utf-8",
        )
        print(EXPERIMENTAL_LABEL)
        print("Production ready: No")
        print("Integration status:", result["integration_status"])
        for error in result["errors"]:
            print("Error:", error)
        print("Saved to:", integration_path)
        return

    pseudocode_by_name: dict[str, list] = {}
    for item in pseudocode.components:
        pseudocode_by_name.setdefault(item.component_name, []).append(item)

    combined_path = OUTPUT_PATH
    prior_combined = (
        load_json(combined_path) if combined_path.is_file() else None
    )
    records = []
    for component in decomposition.components:
        matches = pseudocode_by_name.get(component.name, [])
        if len(matches) != 1:
            error = ValueError(
                f"Expected exactly one pseudocode result for component "
                f"'{component.name}', found {len(matches)}."
            )
            records.append(_failed_component(
                component,
                error,
                matches[0] if matches else None,
            ))
            continue
        records.append(generate_component(
            component,
            matches[0],
            specification,
            specification_hash,
            prior_combined,
            validate_raw_only=args.validate_raw_only,
        ))

    status = (
        "completed"
        if records and all(
            record["generation_status"]
            in {"completed", "reused", "validated_from_raw"}
            and record["validation_status"] == "passed"
            for record in records
        )
        else "failed"
    )
    result = {
        "label": EXPERIMENTAL_LABEL,
        "production_ready": False,
        "specification_path": str(args.spec.resolve()),
        "specification_sha256": specification_hash,
        "pseudocode_validation_status": pseudocode.validation_status,
        "validation_mode": (
            "saved_raw_responses"
            if args.validate_raw_only
            else "generate_or_reuse"
        ),
        "generation_status": status,
        "components": records,
    }
    OUTPUT_PATH.write_text(
        json.dumps(result, indent=4, ensure_ascii=False),
        encoding="utf-8",
    )

    print(EXPERIMENTAL_LABEL)
    print("Production ready: No")
    print("Validation mode:", result["validation_mode"])
    print("Generation status:", status)
    for record in records:
        print(
            f"- {record['component_name']}: "
            f"generation={record['generation_status']}, "
            f"validation={record['validation_status']}"
        )
        for error in record["validation_errors"]:
            print(f"  Error: {error}")
    print("Saved to:", OUTPUT_PATH)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"\nERROR: {type(error).__name__}: {error}")

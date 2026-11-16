import json
import re
from pathlib import Path
from types import SimpleNamespace

from src.agents.rtl_generation import (
    SYSTEM_PROMPT,
    extract_json,
    extract_response_content,
    validate_rtl_output,
)
from src.ingestion import ingest_spec
from src.schemas import (
    ComponentRTLModuleOutput,
    DecompositionOutput,
    PseudocodeGenerationOutput,
)


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
SPEC_PATH = Path(
    r"C:\Users\srira\OneDrive\Desktop\ps spec2rtl\fake_spec2rtl_spec (1).docx"
)
COMPONENT_NAME = "ArithmeticUnit"
RAW_RESPONSE_PATH = OUTPUT_DIR / "rtl_generation_raw_ArithmeticUnit.txt"


def load_json(filename):
    path = OUTPUT_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(f"Missing required saved JSON file: {path}")
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_specification():
    if not SPEC_PATH.is_file():
        raise FileNotFoundError(f"Specification document not found: {SPEC_PATH}")

    docs, _, _ = ingest_spec(str(SPEC_PATH))
    specification = "\n\n".join(doc.page_content for doc in docs).strip()
    if not specification:
        raise ValueError("The specification text is empty.")
    return specification


def build_prompt(specification, component, component_pseudocode):
    port_names = []
    declarations = []
    for direction, signals in (
        ("input", component.inputs),
        ("output", component.outputs),
    ):
        for signal in signals:
            match = re.fullmatch(
                r"\s*([A-Za-z_][A-Za-z0-9_]*)(\[[0-9]+:[0-9]+\])?\s*",
                signal,
            )
            if match is None:
                raise ValueError(f"Invalid component interface signal: {signal}")
            name, width = match.groups()
            port_names.append(name)
            declarations.append(
                f"{direction}{f' {width}' if width else ''} {name};"
            )

    return f"""
{SYSTEM_PROMPT}

ORIGINAL HARDWARE SPECIFICATION (PRIMARY SOURCE):
{specification}

DECOMPOSED COMPONENT INTERFACE:
{json.dumps(component.model_dump(), indent=2, ensure_ascii=False)}

SAVED COMPONENT PSEUDOCODE:
{json.dumps(component_pseudocode.model_dump(), indent=2, ensure_ascii=False)}

Generate exactly one synthesizable component module named
'{component_pseudocode.module_name}'.
The module header must contain only port names, in this exact order:
module {component_pseudocode.module_name} ({', '.join(port_names)});
Do not put input/output declarations in the module header.
After the header, use separate declarations with these exact directions,
names, widths, and order:
{chr(10).join(declarations)}
For example:
module ArithmeticUnit (captured_a, captured_b, op_add, op_sub, arith_result);
input [31:0] captured_a;
input [31:0] captured_b;
input op_add;
input op_sub;
output [31:0] arith_result;
Preserve the provided interface exactly; do not add, remove, reorder, rename,
or resize any port. Do not generate any top-level integration module.
Return a JSON object with exactly module_name, language, rtl_code,
assumptions, and unresolved_issues. Set language to "Verilog", copy
assumptions exactly from the saved pseudocode, and return no unresolved
issues.
"""


def convert_ansi_to_non_ansi(rtl_code):
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
        entry.strip() for entry in module_match.group("ports").split(",")
    ]
    port_names = []
    declarations = []
    inherited_declaration = None
    declaration_pattern = re.compile(
        r"^(input|output|inout)\s+"
        r"(?:(wire|reg|tri)\s+)?"
        r"(?:(signed|unsigned)\s+)?"
        r"(\[[0-9]+\s*:\s*[0-9]+\]\s*)?"
        r"([A-Za-z_][A-Za-z0-9_]*)$"
    )
    for entry in port_entries:
        declaration_match = declaration_pattern.fullmatch(entry)
        if declaration_match is not None:
            direction, net_type, sign, width, name = declaration_match.groups()
            width = width.strip() if width else None
            inherited_declaration = (
                direction,
                net_type,
                sign,
                width,
            )
        else:
            name_match = re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", entry)
            if name_match is None or inherited_declaration is None:
                raise ValueError(
                    f"Cannot convert ANSI port declaration '{entry}'."
                )
            name = entry
            direction, net_type, sign, width = inherited_declaration

        port_names.append(name)
        declaration_parts = [direction]
        if net_type:
            declaration_parts.append(net_type)
        if sign:
            declaration_parts.append(sign)
        if width:
            declaration_parts.append(width)
        declaration_parts.append(name)
        declarations.append(" ".join(declaration_parts) + ";")

    non_ansi_header = (
        f"module {module_match.group('name')} ({', '.join(port_names)});"
        f"\n{chr(10).join(declarations)}"
    )
    return (
        rtl_code[:module_match.start()]
        + non_ansi_header
        + rtl_code[module_match.end():]
    )


def main():
    print("EXPERIMENTAL — pseudocode validation has not passed")
    specification = load_specification()
    decomposition = DecompositionOutput.model_validate(
        load_json("decomposition.json")
    )
    pseudocode = PseudocodeGenerationOutput.model_validate(
        load_json("pseudocode.json")
    )

    component = next(
        (
            item for item in decomposition.components
            if item.name == COMPONENT_NAME
        ),
        None,
    )
    component_pseudocode = next(
        (
            item for item in pseudocode.components
            if item.component_name == COMPONENT_NAME
        ),
        None,
    )
    if component is None:
        raise ValueError(
            f"Component '{COMPONENT_NAME}' is missing from decomposition.json."
        )
    if component_pseudocode is None:
        raise ValueError(
            f"Component '{COMPONENT_NAME}' is missing from pseudocode.json."
        )

    result = {
        "label": "EXPERIMENTAL — pseudocode validation has not passed",
        "production_ready": False,
        "component_name": COMPONENT_NAME,
        "module_name": component_pseudocode.module_name,
        "generation_status": "failed",
        "validation_result": False,
        "validation_errors": [],
        "rtl_code": "",
    }

    try:
        prompt = build_prompt(specification, component, component_pseudocode)
        print(
            "Prepared non-ANSI RTL prompt "
            f"({len(prompt)} characters); not sent to an LLM."
        )
        if not RAW_RESPONSE_PATH.is_file():
            raise FileNotFoundError(
                f"Saved RTL response not found: {RAW_RESPONSE_PATH}"
            )
        response = SimpleNamespace(
            content=RAW_RESPONSE_PATH.read_text(encoding="utf-8")
        )
        raw_content = extract_response_content(response)
        data = json.loads(extract_json(raw_content))

        for field in ("module_name", "language", "rtl_code"):
            if not isinstance(data.get(field), str):
                raise ValueError(f"RTL response {field} must be a string.")
        data["rtl_code"] = convert_ansi_to_non_ansi(data["rtl_code"])
        result.update({
            "module_name": data["module_name"],
            "language": data["language"],
            "rtl_code": data["rtl_code"],
        })
        if data["language"] != "Verilog":
            raise ValueError("RTL response language must be 'Verilog'.")
        if not isinstance(data.get("assumptions"), list) or not all(
            isinstance(item, str) for item in data["assumptions"]
        ):
            raise ValueError("RTL response assumptions must be an array of strings.")
        if data["assumptions"] != component_pseudocode.assumptions:
            raise ValueError(
                "RTL assumptions do not exactly match the saved pseudocode."
            )
        if not isinstance(data.get("unresolved_issues"), list) or not all(
            isinstance(item, str) for item in data["unresolved_issues"]
        ):
            raise ValueError(
                "RTL response unresolved_issues must be an array of strings."
            )
        result.update({
            "assumptions": data["assumptions"],
            "unresolved_issues": data["unresolved_issues"],
        })
        if data["unresolved_issues"]:
            raise ValueError(
                "RTL generation reported unresolved issues: "
                + "; ".join(data["unresolved_issues"])
            )

        module_result = ComponentRTLModuleOutput(
            component_name=COMPONENT_NAME,
            module_name=data["module_name"],
            inputs=component.inputs,
            outputs=component.outputs,
            rtl_code=data["rtl_code"],
        )
        validate_rtl_output(
            module_result,
            expected_module_name=component_pseudocode.module_name,
            expected_inputs=component.inputs,
            expected_outputs=component.outputs,
        )
        result.update({
            "generation_status": "completed",
            "validation_result": True,
        })
    except Exception as error:
        result["validation_errors"].append(
            f"{type(error).__name__}: {error}"
        )

    output_path = OUTPUT_DIR / "rtl_ArithmeticUnit_experimental.json"
    output_path.write_text(
        json.dumps(result, indent=4, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\nGenerated RTL")
    print(result["rtl_code"] or "(none)")
    print("Generation status:", result["generation_status"])
    print("RTL validation result:", result["validation_result"])
    print("Production ready: No")
    print("Errors:", result["validation_errors"] or "None")
    print("Saved to:", output_path)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"\nERROR: {type(error).__name__}: {error}")

"""Deterministic parser and validator for SPEC2RTL Pseudocode Grammar v1.

This module intentionally validates syntax and semantics without an LLM.  It
also keeps the historical list[str] public API for callers that predate
Grammar v1 while exposing structured results through
validate_pseudocode_detailed().
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping, Optional, Sequence


IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_$]*"
IDENTIFIER_RE = re.compile(rf"^{IDENTIFIER}$")
WIDTH_RE = re.compile(r"^\[([0-9]+):([0-9]+)\]$")


@dataclass
class ValidationIssue:
    code: str
    severity: str
    line: Optional[int]
    message: str
    blocks_rtl_generation: bool = False
    identifier: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationResult:
    valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    blocking_issues: list[ValidationIssue] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "issues": [issue.as_dict() for issue in self.issues],
            "blocking_issues": [
                issue.as_dict() for issue in self.blocking_issues
            ],
        }


@dataclass
class Symbol:
    name: str
    kind: str
    width: Optional[str] = None
    line: Optional[int] = None
    direction: Optional[str] = None


@dataclass
class AstNode:
    kind: str
    line: int
    text: str
    children: list["AstNode"] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)


class GrammarParser:
    """Stack-based parser for Grammar v1 block and declaration structure."""

    def __init__(self, lines: Sequence[Any]):
        self.lines = lines
        self.root = AstNode("ROOT", 1, "")
        self.stack: list[AstNode] = [self.root]
        self.issues: list[ValidationIssue] = []
        self.symbols: dict[str, Symbol] = {}
        self.clocks: dict[str, dict[str, Any]] = {}
        self.module_names: set[str] = set()

    def issue(
        self,
        code: str,
        message: str,
        line: Optional[int] = None,
        severity: str = "error",
        blocking: bool = True,
        identifier: Optional[str] = None,
    ) -> None:
        self.issues.append(
            ValidationIssue(
                code=code,
                severity=severity,
                line=line,
                message=message,
                blocks_rtl_generation=blocking,
                identifier=identifier,
            )
        )

    def parse(self) -> AstNode:
        for index, raw_line in enumerate(self.lines, start=1):
            text = raw_line.strip()
            if not text or text.startswith("//") or text.startswith("#"):
                continue

            upper = text.upper()

            if upper.startswith("MODULE "):
                node = AstNode("MODULE", index, text, attributes={})
                match = re.match(r"^MODULE\s+(" + IDENTIFIER + r")\s*$", text, re.I)
                if match:
                    node.attributes["name"] = match.group(1)
                    self.module_names.add(match.group(1))
                else:
                    self.issue("INVALID_MODULE_DECLARATION", "Module declaration is malformed.", index)
                self._append(node)
                self.stack.append(node)
                continue

            if upper == "END MODULE":
                if not self._close("MODULE", "END MODULE", index):
                    continue
                continue

            if upper.startswith("ASSIGN "):
                assignment = self._parse_assignment(text[len("ASSIGN"):].strip())
                if assignment:
                    node = AstNode(
                        "ASSIGNMENT",
                        index,
                        text,
                        attributes={
                            "lhs": assignment[0],
                            "operator": assignment[1],
                            "rhs": assignment[2],
                            "assignment": True,
                        },
                    )
                    self._append(node)
                else:
                    self.issue("INVALID_ASSIGNMENT", "ASSIGN requires a valid assignment.", index)
                continue

            bare_assignment = self._parse_assignment(text)
            if bare_assignment:
                node = AstNode(
                    "ASSIGNMENT",
                    index,
                    text,
                    attributes={
                        "lhs": bare_assignment[0],
                        "operator": bare_assignment[1],
                        "rhs": bare_assignment[2],
                        "assignment": True,
                    },
                )
                self._append(node)
                continue

            if upper.startswith("CLOCK "):
                self._parse_clock(text, index)
                continue

            declaration_match = re.match(
                r"^(INPUT|OUTPUT|INOUT|REG|SIG|PARAMETER|CONST|STATE|FUNCTION)\b(.*)$",
                text,
                re.I,
            )
            if declaration_match:
                kind = declaration_match.group(1).upper()
                remainder = declaration_match.group(2).strip()
                if kind == "FUNCTION":
                    self._parse_function(remainder, index)
                else:
                    self._parse_declaration(kind, remainder, index)
                continue

            if upper.startswith("BLOCK "):
                match = re.match(
                    r"^BLOCK\s+(CLOCKED|COMBINATIONAL)\b(?:\s+(.*))?$",
                    text,
                    re.I,
                )
                if not match:
                    self.issue("INVALID_BLOCK_DECLARATION", "BLOCK declaration is malformed.", index)
                    continue
                kind = match.group(1).upper()
                remainder = match.group(2) or ""
                if kind == "COMBINATIONAL" and remainder:
                    self.issue(
                        "INVALID_BLOCK_DECLARATION",
                        "COMBINATIONAL block header must be exactly 'BLOCK COMBINATIONAL'.",
                        index,
                    )
                    continue
                if kind == "CLOCKED" and not re.fullmatch(
                    r"CLOCK\s+" + IDENTIFIER + r"\s+EDGE\s+(RISING|FALLING)",
                    remainder,
                    re.I,
                ):
                    self.issue(
                        "INVALID_BLOCK_DECLARATION",
                        "CLOCKED block header must be exactly 'BLOCK CLOCKED CLOCK <name> EDGE RISING|FALLING'.",
                        index,
                    )
                    continue
                node = AstNode(
                    f"BLOCK_{kind}",
                    index,
                    text,
                    attributes={"header": remainder},
                )
                if kind == "CLOCKED":
                    clock_match = re.search(
                        r"\bCLOCK\s+(" + IDENTIFIER + r")\b", remainder, re.I
                    )
                    edge_match = re.search(r"\bEDGE\s+(RISING|FALLING)\b", remainder, re.I)
                    node.attributes["clock"] = clock_match.group(1) if clock_match else None
                    node.attributes["edge"] = edge_match.group(1).upper() if edge_match else None
                    if not clock_match:
                        self.issue("CLOCKED_BLOCK_CLOCK_MISSING", "CLOCKED block must declare CLOCK <name>.", index)
                    if not edge_match:
                        self.issue("CLOCKED_BLOCK_EDGE_MISSING", "CLOCKED block must declare EDGE RISING or EDGE FALLING.", index)
                self._append(node)
                self.stack.append(node)
                continue

            if upper == "END BLOCK":
                if not self._close_block(index):
                    continue
                continue

            # Grammar v1 clocked legacy compatibility at block boundaries only.
            legacy_clock = re.match(
                r"^ON\s+(RISING|FALLING)\s+EDGE\s+OF\s+(" + IDENTIFIER + r")\s*$",
                text,
                re.I,
            )
            if legacy_clock:
                self.issue(
                    "LEGACY_CLOCKED_SYNTAX",
                    "Legacy 'ON RISING|FALLING EDGE OF <clock>' syntax is not valid in Grammar v1. Use 'BLOCK CLOCKED CLOCK <name> EDGE RISING|FALLING'.",
                    index,
                )
                continue
            if upper == "END ON":
                self.issue(
                    "LEGACY_CLOCKED_END",
                    "Legacy 'END ON' syntax is not valid in Grammar v1. Use 'END BLOCK'.",
                    index,
                )
                continue

            if upper.startswith("IF ") and upper.endswith(" THEN"):
                node = AstNode("IF", index, text, attributes={"condition": text[:-5].strip()[3:].strip()})
                self._append(node)
                self.stack.append(node)
                continue
            if upper.startswith("ELSE IF ") and upper.endswith(" THEN"):
                node = AstNode("ELSE_IF", index, text, attributes={"condition": text[:-5].strip()[8:].strip()})
                self._append(node)
                continue
            if upper == "ELSE":
                self._append(AstNode("ELSE", index, text))
                continue
            if upper == "END IF":
                if not self._close("IF", "END IF", index):
                    continue
                continue

            if upper.startswith("CASE "):
                expr = text[text.find(" ") + 1:].strip()
                if expr.upper().endswith(" OF"):
                    self.issue(
                        "LEGACY_CASE_OF_SYNTAX",
                        "Legacy 'CASE expression OF' syntax is not valid in Grammar v1. Use 'CASE expression'.",
                        index,
                    )
                    continue
                if expr.endswith(":"):
                    self.issue(
                        "CASE_COLON_NOT_ALLOWED",
                        "CASE syntax is 'CASE expression'; do not add a colon.",
                        index,
                    )
                    continue
                node = AstNode("CASE", index, text, attributes={"expression": expr})
                self._append(node)
                self.stack.append(node)
                continue
            if upper.startswith("WHEN "):
                node = AstNode("WHEN", index, text, attributes={"default": upper == "WHEN DEFAULT:"})
                if not node.attributes["default"]:
                    branch_match = re.match(
                        r"^WHEN\s+(.+):\s*$",
                        text,
                        re.I,
                    )
                    if not branch_match or branch_match.group(1).strip().upper() == "DEFAULT":
                        self.issue(
                            "INVALID_WHEN_SYNTAX",
                            "WHEN branches require exactly 'WHEN value:'; use 'WHEN DEFAULT:' for the default branch.",
                            index,
                        )
                        continue
                    node.attributes["values"] = [branch_match.group(1).strip()]
                self._append(node)
                continue
            # Legacy named DEFAULT branch compatibility, retained only as a warning.
            if upper.startswith("DEFAULT:"):
                node = AstNode("WHEN", index, text, attributes={"default": True, "legacy": True})
                self.issue(
                    "LEGACY_DEFAULT_BRANCH",
                    "Named 'DEFAULT:' syntax is not valid in Grammar v1. Use 'WHEN DEFAULT:'.",
                    index,
                )
                self._append(node)
                continue
            if upper == "END CASE":
                if not self._close("CASE", "END CASE", index):
                    continue
                continue

            if upper == "END FUNCTION":
                if not self._close("FUNCTION", "END FUNCTION", index):
                    continue
                continue

            if upper.startswith("RESET "):
                match = re.match(r"^RESET\s+(SYNCHRONOUS|ASYNCHRONOUS|NOT\s+SPECIFIED)\b(.*)$", text, re.I)
                if match:
                    mode = "NOT SPECIFIED" if match.group(1).upper().replace("  ", " ") == "NOT SPECIFIED" else match.group(1).upper()
                    node = AstNode("RESET", index, text, attributes={"mode": mode, "details": match.group(2).strip()})
                    if node.attributes["details"]:
                        node.attributes.update(self._parse_reset_details(node.attributes["details"], index))
                    self._append(node)
                    if mode == "NOT SPECIFIED":
                        self.stack.append(node)
                else:
                    self.issue("INVALID_RESET_SYNTAX", "RESET must specify SYNCHRONOUS, ASYNCHRONOUS, or NOT SPECIFIED.", index)
                continue
            if upper == "END RESET":
                if not self._close("RESET", "END RESET", index):
                    continue
                continue

            if upper.startswith("UNRESOLVED "):
                match = re.match(r"^UNRESOLVED\s+([^:]+)\s*:\s*([^-]+)\s*-\s*(.+)$", text, re.I)
                if not match:
                    self.issue(
                        "INVALID_UNRESOLVED_SYNTAX",
                        "UNRESOLVED must use: UNRESOLVED <scope> : <identifier_or_requirement> - <missing_detail>",
                        index,
                    )
                else:
                    self._append(AstNode("UNRESOLVED", index, text, attributes={
                        "scope": match.group(1).strip(),
                        "target": match.group(2).strip(),
                        "detail": match.group(3).strip(),
                    }))
                continue

            if upper.startswith("TIMING "):
                self._append(AstNode("TIMING", index, text, attributes={"text": text[len("TIMING"):].strip()}))
                continue

            if upper.startswith("CDC_SYNC_REG "):
                self._append(AstNode("CDC_SYNC_REG", index, text, attributes={"text": text[len("CDC_SYNC_REG"):].strip()}))
                continue
            if upper.startswith("CDC_HANDSHAKE "):
                self._append(AstNode("CDC_HANDSHAKE", index, text, attributes={"text": text[len("CDC_HANDSHAKE"):].strip()}))
                continue

            if upper.startswith("RETURN"):
                expr = text[len("RETURN"):].strip()
                self._append(AstNode("RETURN", index, text, attributes={"expression": expr.lstrip(" (").rstrip(") ")}))
                continue

            assignment = self._parse_assignment(text)
            if assignment:
                node = AstNode(
                    "ASSIGNMENT",
                    index,
                    text,
                    attributes={
                        "lhs": assignment[0],
                        "operator": assignment[1],
                        "rhs": assignment[2],
                        "assignment": assignment[1] == "<=",
                    },
                )
                self._append(node)
                continue

            if upper.startswith("SET "):
                assignment_text = text[4:].strip()
                assignment = self._parse_assignment(assignment_text)
                if assignment:
                    node = AstNode(
                        "FUNCTION_SET",
                        index,
                        text,
                        attributes={"lhs": assignment[0], "operator": assignment[1], "rhs": assignment[2]},
                    )
                    self._append(node)
                else:
                    self.issue("INVALID_SET", "SET requires a valid assignment.", index)
                continue

            self.issue("UNRECOGNIZED_STATEMENT", f"Unrecognized pseudocode statement: {text}", index)

        while len(self.stack) > 1:
            node = self.stack[-1]
            self.issue(
                "MISSING_END_DELIMITER",
                f"Missing end delimiter for {node.kind} opened on line {node.line}.",
                node.line,
            )
            self.stack.pop()

        return self.root

    def _append(self, node: AstNode) -> None:
        self.stack[-1].children.append(node)

    def _close(self, kind: str, delimiter: str, index: int) -> bool:
        if len(self.stack) < 2 or self.stack[-1].kind != kind:
            opened = self.stack[-1].kind if len(self.stack) > 1 else "ROOT"
            self.issue(
                "UNMATCHED_END_DELIMITER",
                f"{delimiter} found without matching {kind}; current block is {opened}.",
                index,
            )
            return False
        self.stack.pop()
        return True

    def _close_block(self, index: int) -> bool:
        if len(self.stack) >= 2 and self.stack[-1].kind.startswith("BLOCK_"):
            self.stack.pop()
            return True
        opened = self.stack[-1].kind if len(self.stack) > 1 else "ROOT"
        self.issue("UNMATCHED_END_DELIMITER", f"END BLOCK found without matching BLOCK; current block is {opened}.", index)
        return False

    def _parse_clock(self, text: str, line: int) -> None:
        match = re.match(
            r"^CLOCK\s+(" + IDENTIFIER + r")"
            r"\s+EDGE\s+(RISING|FALLING)\s*$",
            text,
            re.I,
        )
        if not match:
            self.issue("INVALID_CLOCK_DECLARATION", "CLOCK must use 'CLOCK <name> EDGE RISING|FALLING'.", line)
            return
        name = match.group(1)
        edge = match.group(2).upper()
        if name in self.symbols or name in self.clocks:
            self.issue("DUPLICATE_DECLARATION", f"Duplicate name or interface declaration '{name}'.", line, identifier=name)
            return
        self.clocks[name] = {"edge": edge, "line": line}
        self.symbols[name] = Symbol(name=name, kind="CLOCK", width=None, line=line, direction="clock")

    def _parse_reset_details(self, details: str, line: int) -> dict[str, Any]:
        result: dict[str, Any] = {}
        signal_match = re.search(r"\b(?:SIGNAL\s+)?(" + IDENTIFIER + r")", details, re.I)
        polarity_match = re.search(r"\b(ACTIVE_HIGH|ACTIVE_LOW|HIGH|LOW)\b", details, re.I)
        value_match = re.search(r"\bVALUE\s+(.+)$", details, re.I)
        if signal_match:
            result["signal"] = signal_match.group(1)
        if polarity_match:
            value = polarity_match.group(1).upper()
            result["polarity"] = "ACTIVE_HIGH" if value == "HIGH" else "ACTIVE_LOW" if value == "LOW" else value
        if value_match:
            result["value"] = value_match.group(1).strip()
        return result

    def _parse_declaration(self, kind: str, remainder: str, line: int) -> None:
        if remainder.rstrip().endswith(";"):
            self.issue(
                "LEGACY_DECLARATION_SEMICOLON",
                "Declarations with trailing semicolons are not valid in Grammar v1.",
                line,
            )
            remainder = remainder.rstrip()[:-1].rstrip()
        match = re.match(
            r"^(" + IDENTIFIER + r")"
            r"(?:\s*(\[[0-9]+:[0-9]+\]))?"
            r"(?:\s*:\s*(.+))?$",
            remainder,
            re.I,
        )
        if not match:
            self.issue("INVALID_DECLARATION", f"Invalid {kind} declaration: {remainder}", line)
            return
        name = match.group(1)
        width = match.group(2)
        suffix = (match.group(3) or "").strip()

        if name in self.symbols:
            self.issue("DUPLICATE_DECLARATION", f"Duplicate declaration name '{name}'.", line, identifier=name)
            return

        if kind in {"INPUT", "OUTPUT", "INOUT"}:
            if width is None:
                width_match = re.search(r"\bWIDTH\s+(\d+)\b", suffix, re.I)
                width = f"[{int(width_match.group(1)) - 1}:0]" if width_match else None
            direction = "input" if kind == "INPUT" else "output" if kind == "OUTPUT" else "inout"
            self.symbols[name] = Symbol(name, kind, width, line, direction)
        elif kind in {"REG", "SIG", "STATE", "PARAMETER", "CONST"}:
            self.symbols[name] = Symbol(name, kind, width, line)
        else:
            self.symbols[name] = Symbol(name, kind, width, line)

        # Clock names cannot be repeated through INPUT declarations.
        if kind == "INPUT" and name in self.clocks:
            self.issue(
                "CLOCK_INPUT_DUPLICATE_DECLARATION",
                f"Clock '{name}' is declared by CLOCK and must not also be declared with INPUT.",
                line,
                identifier=name,
            )

    def _parse_function(self, remainder: str, line: int) -> None:
        remainder = remainder.strip()
        if remainder.endswith(":"):
            remainder = remainder[:-1].rstrip()
        match = re.match(
            r"^(" + IDENTIFIER + r")\s*\(([^)]*)\)(?:\s*->\s*\(([^)]*)\)|\s*->\s*([A-Za-z_][A-Za-z0-9_$]*(?:\[[^\]]+\])?(?:\s*,\s*[A-Za-z_][A-Za-z0-9_$]*(?:\[[^\]]+\])?)*))?$",
            remainder,
            re.I,
        )
        if not match:
            self.issue("INVALID_FUNCTION_DECLARATION", f"Invalid FUNCTION declaration: {remainder}", line)
            return
        name = match.group(1)
        if name in self.symbols:
            self.issue("DUPLICATE_DECLARATION", f"Duplicate declaration name '{name}'.", line, identifier=name)
            return
        node = AstNode(
            "FUNCTION",
            line,
            "FUNCTION " + remainder,
            attributes={
                "name": name,
                "parameters": [part.strip() for part in match.group(2).split(",") if part.strip()],
                "returns": [
                    part.strip()
                    for part in ((match.group(3) or match.group(4) or "").split(","))
                    if part.strip()
                ],
            },
        )
        self.symbols[name] = Symbol(name, "FUNCTION", None, line)
        self._append(node)
        self.stack.append(node)

    def _parse_assignment(self, text: str) -> Optional[tuple[str, str, str]]:
        match = re.match(r"^\s*((" + IDENTIFIER + r")(?:\[[^\]]+\])?)\s*(<=|=)\s*(.+?)\s*$", text)
        if not match:
            return None
        lhs = match.group(1).strip()
        return lhs, match.group(3), match.group(4).strip()


def _issue(
    issues: list[ValidationIssue],
    code: str,
    severity: str,
    line: Optional[int],
    message: str,
    blocking: bool = True,
    identifier: Optional[str] = None,
) -> None:
    issues.append(
        ValidationIssue(
            code=code,
            severity=severity,
            line=line,
            message=message,
            blocks_rtl_generation=blocking,
            identifier=identifier,
        )
    )


def _valid_identifier(value: str) -> bool:
    return bool(IDENTIFIER_RE.fullmatch(value.strip()))


def _base_identifier(lhs: str) -> str:
    return lhs.split("[", 1)[0].strip()


def _flatten_understanding(understanding: Any) -> list[str]:
    if understanding is None:
        return []
    if isinstance(understanding, Mapping) or isinstance(understanding, dict):
        values: list[str] = []
        for value in understanding.values():
            if isinstance(value, str):
                values.append(value)
            elif isinstance(value, (list, tuple)):
                values.extend(str(item) for item in value)
        return values
    values = []
    for field_name in (
        "system_purpose",
        "major_components",
        "inputs",
        "outputs",
        "functional_requirements",
        "constraints",
        "ambiguities",
    ):
        value = getattr(understanding, field_name, None)
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, (list, tuple)):
            values.extend(str(item) for item in value)
    return values


def _specification_text(
    specification: Optional[Any],
    understanding: Optional[Any],
) -> str:
    parts = []
    if specification is not None:
        parts.append(str(specification))
    parts.extend(_flatten_understanding(understanding))
    return "\n".join(parts).lower()


def validate_pseudocode_detailed(
    pseudocode: Any,
    specification: Optional[Any] = None,
    understanding: Optional[Any] = None,
    **context: Any,
) -> ValidationResult:
    """Deterministically validate pseudocode using Grammar v1."""

    issues: list[ValidationIssue] = []

    if not pseudocode:
        _issue(issues, "EMPTY_PSEUDOCODE", "error", None, "Pseudocode is empty.")
        return ValidationResult(False, issues, [i for i in issues if i.blocks_rtl_generation])
    if not isinstance(pseudocode, list):
        _issue(issues, "INVALID_PSEUDOCODE_TYPE", "error", None, "Pseudocode must be a list of strings.")
        return ValidationResult(False, issues, [i for i in issues if i.blocks_rtl_generation])
    if not all(isinstance(line, str) for line in pseudocode):
        _issue(issues, "INVALID_PSEUDOCODE_LINE_TYPE", "error", None, "Every pseudocode element must be a string.")
        return ValidationResult(False, issues, [i for i in issues if i.blocks_rtl_generation])

    for index, line in enumerate(pseudocode, start=1):
        if len(line) > 500:
            _issue(
                issues,
                "LINE_TOO_LONG",
                "warning",
                index,
                f"Line {index} is too long ({len(line)} characters).",
                blocking=False,
            )
        if "\t" in line:
            _issue(
                issues,
                "TAB_INDENTATION",
                "warning",
                index,
                "Tabs are not part of the canonical indentation format.",
                blocking=False,
            )

    parser = GrammarParser(pseudocode)
    root = parser.parse()
    issues.extend(parser.issues)

    lines = [(index, line.strip()) for index, line in enumerate(pseudocode, start=1) if line.strip()]
    if not lines:
        _issue(issues, "EMPTY_PSEUDOCODE", "error", None, "Pseudocode contains no usable statements.")

    # Structural control-flow and block matching.
    _validate_control_structure(lines, issues)

    # Declaration and interface checks.
    _validate_declarations(lines, parser.symbols, parser.clocks, issues)

    # Clocked and combinational syntax.
    _validate_blocks(lines, parser.clocks, parser.symbols, issues)

    # Clocked assignments and combinational assignments.
    _validate_assignments(lines, parser.symbols, issues)

    # Function declaration, SET and terminal RETURN checks.
    _validate_functions(lines, issues)
    _validate_expression_types(lines, parser.symbols, issues)
    _validate_reset(lines, parser, issues)

    # CDC constructs and unresolved requirements.
    _validate_cdc(lines, parser.symbols, parser.clocks, understanding, specification, issues)
    _validate_unresolved(lines, issues)

    # Specification-aware evidence checks.
    _validate_specification_awareness(
        lines,
        parser.symbols,
        parser.clocks,
        specification,
        understanding,
        context,
        issues,
    )

    blocking = [
        issue
        for issue in issues
        if issue.severity == "error" and issue.blocks_rtl_generation
    ]
    valid = not blocking
    return ValidationResult(valid=valid, issues=issues, blocking_issues=blocking)


def _validate_control_structure(
    lines: Sequence[tuple[int, str]],
    issues: list[ValidationIssue],
) -> None:
    stack: list[tuple[str, int]] = []
    if_states: dict[int, dict[str, Any]] = {}
    case_defaults: dict[int, bool] = {}
    case_default_counts: dict[int, int] = {}
    if_count = end_if_count = 0
    case_count = end_case_count = 0
    function_count = end_function_count = 0
    block_count = end_block_count = 0
    module_count = end_module_count = 0
    reset_count = end_reset_count = 0

    for line_number, text in lines:
        upper = text.upper()

        if upper.startswith("MODULE "):
            module_count += 1
            stack.append(("MODULE", line_number))
        elif upper == "END MODULE":
            end_module_count += 1
            if not stack or stack[-1][0] != "MODULE":
                _issue(issues, "UNMATCHED_END_DELIMITER", "error", line_number, "END MODULE found without matching MODULE.")
            else:
                stack.pop()

        elif upper.startswith("FUNCTION "):
            function_count += 1
            stack.append(("FUNCTION", line_number))
        elif upper == "END FUNCTION":
            end_function_count += 1
            if not stack or stack[-1][0] != "FUNCTION":
                _issue(issues, "UNMATCHED_END_DELIMITER", "error", line_number, "END FUNCTION found without matching FUNCTION.")
            else:
                stack.pop()

        elif upper.startswith("BLOCK "):
            block_count += 1
            stack.append(("BLOCK", line_number))
        elif upper == "END BLOCK":
            end_block_count += 1
            if not stack or stack[-1][0] != "BLOCK":
                _issue(issues, "UNMATCHED_END_DELIMITER", "error", line_number, "END BLOCK found without matching BLOCK.")
            else:
                stack.pop()
        elif re.match(r"^ON\s+(RISING|FALLING)\s+EDGE\s+OF\s+" + IDENTIFIER + r"$", text, re.I):
            _issue(
                issues,
                "LEGACY_CLOCKED_SYNTAX",
                "error",
                line_number,
                "Legacy 'ON RISING|FALLING EDGE OF <clock>' syntax is not valid. Use BLOCK CLOCKED syntax.",
            )
        elif upper == "END ON":
            _issue(
                issues,
                "LEGACY_CLOCKED_END",
                "error",
                line_number,
                "Legacy 'END ON' syntax is not valid. Use END BLOCK.",
            )

        elif upper.startswith("IF ") and upper.endswith(" THEN"):
            if_count += 1
            stack.append(("IF", line_number))
            if_states[line_number] = {"saw_else": False}
        elif upper.startswith("ELSE IF ") and upper.endswith(" THEN"):
            if not stack or stack[-1][0] != "IF":
                _issue(issues, "UNMATCHED_ELSE_IF", "error", line_number, "ELSE IF found without matching IF.")
            else:
                if_line = stack[-1][1]
                if if_states.get(if_line, {}).get("saw_else"):
                    _issue(
                        issues,
                        "ELSE_IF_AFTER_ELSE",
                        "error",
                        line_number,
                        "ELSE IF is not valid after an ELSE branch; add another nested IF or use ELSE IF before ELSE.",
                    )
        elif upper == "ELSE":
            if not stack or stack[-1][0] != "IF":
                _issue(issues, "UNMATCHED_ELSE", "error", line_number, "ELSE found without matching IF or CASE.")
            else:
                if_line = stack[-1][1]
                state = if_states.setdefault(if_line, {"saw_else": False})
                if state["saw_else"]:
                    _issue(
                        issues,
                        "MULTIPLE_ELSE_BRANCHES",
                        "error",
                        line_number,
                        "Multiple ELSE branches are not valid in the same IF statement.",
                    )
                state["saw_else"] = True
        elif upper == "END IF":
            end_if_count += 1
            if not stack or stack[-1][0] != "IF":
                _issue(issues, "UNMATCHED_END_DELIMITER", "error", line_number, "END IF found without matching IF.")
            else:
                stack.pop()

        elif upper.startswith("CASE "):
            expression = text[len("CASE"):].strip()
            if expression.upper().endswith(" OF") or re.search(r"\bOF\s*$", expression, re.I):
                _issue(
                    issues,
                    "LEGACY_CASE_OF_SYNTAX",
                    "error",
                    line_number,
                    "Legacy 'CASE expression OF' syntax is not valid. Use 'CASE expression'.",
                )
            elif expression.endswith(":"):
                _issue(
                    issues,
                    "CASE_COLON_NOT_ALLOWED",
                    "error",
                    line_number,
                    "CASE syntax is 'CASE expression'; do not add a colon.",
                )
            else:
                case_count += 1
                stack.append(("CASE", line_number))
                case_defaults[line_number] = False
                case_default_counts[line_number] = 0
        elif upper.startswith("WHEN "):
            case_stack = [item for item in stack if item[0] == "CASE"]
            if not case_stack:
                _issue(
                    issues,
                    "WHEN_OUTSIDE_CASE",
                    "error",
                    line_number,
                    "WHEN and WHEN DEFAULT branches must appear inside a CASE.",
                )
                continue
            if upper == "WHEN DEFAULT:":
                case_line = case_stack[-1][1]
                case_defaults[case_line] = True
                case_default_counts[case_line] = case_default_counts.get(case_line, 0) + 1
            else:
                branch_match = re.match(r"^WHEN\s+(.+):\s*$", text, re.I)
                if not branch_match:
                    _issue(
                        issues,
                        "INVALID_WHEN_SYNTAX",
                        "error",
                        line_number,
                        "WHEN branches require exactly 'WHEN value:'; use 'WHEN DEFAULT:' for the default branch.",
                    )
        elif upper == "END CASE":
            end_case_count += 1
            if not stack or stack[-1][0] != "CASE":
                _issue(issues, "UNMATCHED_END_DELIMITER", "error", line_number, "END CASE found without matching CASE.")
            else:
                case_line = stack[-1][1]
                if not case_defaults.get(case_line, False):
                    _issue(
                        issues,
                        "CASE_DEFAULT_MISSING",
                        "error",
                        case_line,
                        "CASE must contain exactly one WHEN DEFAULT terminal branch.",
                    )
                if case_default_counts.get(case_line, 0) > 1:
                    _issue(
                        issues,
                        "CASE_DEFAULT_DUPLICATE",
                        "error",
                        case_line,
                        "CASE must contain exactly one WHEN DEFAULT terminal branch.",
                    )
                stack.pop()

        elif upper == "RESET NOT SPECIFIED":
            reset_count += 1
            stack.append(("RESET", line_number))
        elif upper == "END RESET":
            end_reset_count += 1
            if not stack or stack[-1][0] != "RESET":
                _issue(issues, "UNMATCHED_END_DELIMITER", "error", line_number, "END RESET found without matching RESET.")
            else:
                stack.pop()

    if if_count != end_if_count:
        _issue(
            issues,
            "IF_END_IF_MISMATCH",
            "error",
            None,
            f"IF/END IF mismatch: {if_count} IF statements, {end_if_count} END IF statements.",
        )
    if case_count != end_case_count:
        _issue(
            issues,
            "CASE_END_CASE_MISMATCH",
            "error",
            None,
            f"CASE/END CASE mismatch: {case_count} CASE statements, {end_case_count} END CASE statements.",
        )
    if function_count != end_function_count:
        _issue(
            issues,
            "FUNCTION_END_FUNCTION_MISMATCH",
            "error",
            None,
            f"FUNCTION/END FUNCTION mismatch: {function_count} FUNCTION statements, {end_function_count} END FUNCTION statements.",
        )
    if block_count != end_block_count:
        _issue(
            issues,
            "BLOCK_END_BLOCK_MISMATCH",
            "error",
            None,
            f"Clocked or combinational block mismatch: {block_count} opening blocks, {end_block_count} END BLOCK/END ON statements.",
        )
    if module_count != end_module_count:
        _issue(
            issues,
            "MODULE_END_MODULE_MISMATCH",
            "error",
            None,
            f"MODULE/END MODULE mismatch: {module_count} modules, {end_module_count} END MODULE statements.",
        )
    if reset_count != end_reset_count:
        _issue(
            issues,
            "RESET_END_RESET_MISMATCH",
            "error",
            None,
            f"RESET/END RESET mismatch: {reset_count} reset declarations, {end_reset_count} END RESET statements.",
        )
    for kind, line_number in stack:
        _issue(
            issues,
            "MISSING_END_DELIMITER",
            "error",
            line_number,
            f"{kind} opened on line {line_number} is missing its END delimiter.",
        )


def _extract_assignment(text: str) -> Optional[tuple[str, str, str]]:
    candidate = text.strip()
    if candidate.upper().startswith("ASSIGN "):
        candidate = candidate[len("ASSIGN"):].strip()
    elif candidate.upper().startswith("SET "):
        candidate = candidate[len("SET"):].strip()
    match = re.match(
        r"^((" + IDENTIFIER + r")(?:\[[^\]]+\])?)\s*(<=|=)\s*(.+)$",
        candidate,
        re.I,
    )
    if not match:
        return None
    return match.group(1).strip(), match.group(3), match.group(4).strip()


def _matching_control_end(
    body_lines: Sequence[tuple[int, str]],
    start_index: int,
    open_text: str,
    close_text: str,
) -> Optional[int]:
    depth = 0
    for index in range(start_index, len(body_lines)):
        upper = body_lines[index][1].strip().upper()
        if upper.startswith(open_text):
            depth += 1
        elif upper == close_text:
            depth -= 1
            if depth == 0:
                return index
    return None


def _merge_terminal_path(
    existing: dict[str, list[int]],
    branch: dict[str, list[int]],
) -> dict[str, list[int]]:
    merged = {target: list(lines) for target, lines in existing.items()}
    for target, lines in branch.items():
        merged.setdefault(target, []).extend(lines)
    return merged


def _split_if_branches(
    body_lines: Sequence[tuple[int, str]],
    start_index: int,
    end_index: int,
) -> tuple[list[Sequence[tuple[int, str]]], Optional[Sequence[tuple[int, str]]]]:
    segments: list[Sequence[tuple[int, str]]] = []
    markers: list[tuple[str, int]] = []
    nested_if_depth = 0

    for index in range(start_index + 1, end_index):
        upper = body_lines[index][1].strip().upper()
        if upper.startswith("IF ") and upper.endswith(" THEN"):
            nested_if_depth += 1
        elif upper == "END IF":
            nested_if_depth -= 1
        elif nested_if_depth == 0 and (
            upper.startswith("ELSE IF ") and upper.endswith(" THEN")
            or upper == "ELSE"
        ):
            markers.append((upper, index))

    branch_start = start_index + 1
    else_body: Optional[Sequence[tuple[int, str]]] = None
    for marker, marker_index in markers:
        segments.append(body_lines[branch_start:marker_index])
        branch_start = marker_index + 1
        if marker == "ELSE":
            else_body = body_lines[branch_start:end_index]
            branch_start = end_index
            break
    if branch_start < end_index and else_body is None:
        segments.append(body_lines[branch_start:end_index])
    if else_body is not None:
        segments.pop()
        segments.append(body_lines[start_index + 1:markers[0][1]])
    return segments, else_body


def _control_terminal_paths(
    body_lines: Sequence[tuple[int, str]],
) -> list[dict[str, list[int]]]:
    """Expand sequential assignments, IF branches, and CASE branches into terminal paths."""
    paths: list[dict[str, list[int]]] = [{}]
    index = 0

    while index < len(body_lines):
        _, text = body_lines[index]
        upper = text.strip().upper()

        assignment = _extract_assignment(text)
        if assignment:
            target = _base_identifier(assignment[0])
            for path in paths:
                path.setdefault(target, []).append(body_lines[index][0])
            index += 1
            continue

        if upper.startswith("IF ") and upper.endswith(" THEN"):
            end_index = _matching_control_end(body_lines, index, "IF ", "END IF")
            if end_index is None:
                index += 1
                continue

            nested_depth = 0
            markers: list[tuple[str, int]] = []
            for marker_index in range(index + 1, end_index):
                marker_upper = body_lines[marker_index][1].strip().upper()
                if marker_upper.startswith("IF ") and marker_upper.endswith(" THEN"):
                    nested_depth += 1
                elif marker_upper == "END IF":
                    nested_depth -= 1
                elif nested_depth == 0 and (
                    marker_upper.startswith("ELSE IF ") and marker_upper.endswith(" THEN")
                    or marker_upper == "ELSE"
                ):
                    markers.append((marker_upper, marker_index))

            branches: list[Sequence[tuple[int, str]]] = []
            branch_start = index + 1
            else_body: Optional[Sequence[tuple[int, str]]] = None
            for marker, marker_index in markers:
                branches.append(body_lines[branch_start:marker_index])
                branch_start = marker_index + 1
                if marker == "ELSE":
                    else_body = body_lines[branch_start:end_index]
                    break
            if else_body is not None:
                branches.append(else_body)
            else:
                branches.append(body_lines[branch_start:end_index])

            branch_paths: list[dict[str, list[int]]] = []
            for branch_body in branches:
                branch_paths.extend(
                    _control_terminal_paths(branch_body)
                    if branch_body
                    else [{}]
                )
            combined = [
                _merge_terminal_path(path, branch_path)
                for path in paths
                for branch_path in branch_paths
            ]
            if else_body is None:
                combined.extend([dict(path) for path in paths])
            paths = combined
            index = end_index + 1
            continue

        if upper.startswith("CASE "):
            end_index = _matching_control_end(body_lines, index, "CASE ", "END CASE")
            if end_index is None:
                index += 1
                continue
            nested_depth = 0
            branch_markers: list[tuple[str, int]] = []
            for marker_index in range(index + 1, end_index):
                marker_upper = body_lines[marker_index][1].strip().upper()
                if marker_upper.startswith("CASE "):
                    nested_depth += 1
                elif marker_upper == "END CASE":
                    nested_depth -= 1
                elif nested_depth == 0 and marker_upper.startswith("WHEN "):
                    branch_markers.append((marker_upper, marker_index))

            case_paths: list[dict[str, list[int]]] = []
            has_default = False
            for marker_number, (marker, marker_index) in enumerate(branch_markers):
                branch_start = marker_index + 1
                branch_end = (
                    branch_markers[marker_number + 1][1]
                    if marker_number + 1 < len(branch_markers)
                    else end_index
                )
                branch_paths = _control_terminal_paths(body_lines[branch_start:branch_end])
                case_paths.extend(branch_paths)
                if marker == "WHEN DEFAULT:":
                    has_default = True

            combined = []
            for path in paths:
                for branch_path in case_paths:
                    combined.append(_merge_terminal_path(path, branch_path))
            if not has_default:
                combined.extend([dict(path) for path in paths])
            paths = combined
            index = end_index + 1
            continue

        index += 1

    return paths


def _validate_declarations(
    lines: Sequence[tuple[int, str]],
    symbols: dict[str, Symbol],
    clocks: dict[str, dict[str, Any]],
    issues: list[ValidationIssue],
) -> None:
    names_seen: dict[str, tuple[int, str]] = {}
    interface_kinds = {"INPUT", "OUTPUT", "INOUT", "CLOCK"}

    for line_number, text in lines:
        if _extract_assignment(text) is not None:
            continue
        for keyword in ("INPUT", "OUTPUT", "INOUT", "REG", "SIG", "PARAMETER", "CONST", "STATE"):
            match = re.match(r"^" + keyword + r"\s+(.+)$", text, re.I)
            if not match:
                continue
            declaration = match.group(1).strip()
            if declaration.endswith(";"):
                _issue(
                    issues,
                    "LEGACY_DECLARATION_SEMICOLON",
                    "error",
                    line_number,
                    "Declarations with trailing semicolons are not valid in Grammar v1.",
                )
            if declaration.endswith(":"):
                declaration = declaration[:-1].rstrip()
            name_match = re.match(r"^(" + IDENTIFIER + r")(.*)$", declaration, re.I)
            if not name_match:
                _issue(
                    issues,
                    "INVALID_DECLARATION",
                    "error",
                    line_number,
                    f"Invalid {keyword} declaration '{text}'.",
                )
                break
            name = name_match.group(1)
            suffix = name_match.group(2).strip()

            if keyword in interface_kinds:
                if name in clocks and keyword != "CLOCK":
                    _issue(
                        issues,
                        "CLOCK_INPUT_DUPLICATE_DECLARATION",
                        "error",
                        line_number,
                        f"Clock '{name}' is declared by CLOCK and must not also be declared with {keyword}.",
                        identifier=name,
                    )

            if name in names_seen:
                previous_line, previous_kind = names_seen[name]
                _issue(
                    issues,
                    "DUPLICATE_DECLARATION",
                    "error",
                    line_number,
                    f"Duplicate declaration '{name}' on line {line_number}; first declared on line {previous_line} as {previous_kind}.",
                    identifier=name,
                )
            else:
                names_seen[name] = (line_number, keyword)

            width_match = re.match(r"^\s*\[([0-9]+):([0-9]+)\]", suffix, re.I)
            width_text_match = re.search(r"\bWIDTH\s+([0-9]+)\b", suffix, re.I)
            if width_match:
                msb = int(width_match.group(1))
                lsb = int(width_match.group(2))
                if msb < lsb:
                    _issue(
                        issues,
                        "INVALID_WIDTH_RANGE",
                        "error",
                        line_number,
                        f"Invalid width range [{msb}:{lsb}] for '{name}'; MSB must be greater than or equal to LSB.",
                        identifier=name,
                    )
            elif width_text_match:
                width = int(width_text_match.group(1))
                if width <= 0:
                    _issue(
                        issues,
                        "INVALID_WIDTH",
                        "error",
                        line_number,
                        f"Width for '{name}' must be positive.",
                        identifier=name,
                    )
            break

        clock_match = re.match(r"^CLOCK\s+(" + IDENTIFIER + r")\b", text, re.I)
        if clock_match:
            name = clock_match.group(1)
            if name in names_seen and names_seen[name][1] != "CLOCK":
                _issue(
                    issues,
                    "DUPLICATE_DECLARATION",
                    "error",
                    line_number,
                    f"Duplicate declaration '{name}'.",
                    identifier=name,
                )
            else:
                names_seen[name] = (line_number, "CLOCK")

    if not names_seen and not any(text.startswith("MODULE ") for _, text in lines):
        _issue(
            issues,
            "NO_DECLARATIONS",
            "warning",
            None,
            "No module interface or internal declarations were found.",
            blocking=False,
        )


def _validate_blocks(
    lines: Sequence[tuple[int, str]],
    clocks: dict[str, dict[str, Any]],
    symbols: dict[str, Symbol],
    issues: list[ValidationIssue],
) -> None:
    active_clock: Optional[str] = None
    active_kind: Optional[str] = None
    active_line: Optional[int] = None

    for line_number, text in lines:
        upper = text.upper()
        block_match = re.match(
            r"^BLOCK\s+(CLOCKED|COMBINATIONAL)\b(.*)$",
            text,
            re.I,
        )
        if block_match:
            active_kind = block_match.group(1).upper()
            active_line = line_number
            active_clock = None
            remainder = block_match.group(2).strip()
            if active_kind == "COMBINATIONAL":
                if remainder:
                    _issue(
                        issues,
                        "INVALID_BLOCK_DECLARATION",
                        "error",
                        line_number,
                        "COMBINATIONAL block header must be exactly 'BLOCK COMBINATIONAL'.",
                    )
                continue
            if not re.fullmatch(
                r"CLOCK\s+" + IDENTIFIER + r"\s+EDGE\s+(RISING|FALLING)",
                remainder,
                re.I,
            ):
                _issue(
                    issues,
                    "INVALID_BLOCK_DECLARATION",
                    "error",
                    line_number,
                    "CLOCKED block header must be exactly 'BLOCK CLOCKED CLOCK <name> EDGE RISING|FALLING'.",
                )
                continue
            clock_match = re.search(r"\bCLOCK\s+(" + IDENTIFIER + r")\b", remainder, re.I)
            edge_match = re.search(r"\bEDGE\s+(RISING|FALLING)\b", remainder, re.I)

            if active_kind == "CLOCKED":
                if not clock_match:
                    _issue(
                        issues,
                        "CLOCKED_BLOCK_CLOCK_MISSING",
                        "error",
                        line_number,
                        "CLOCKED block must declare CLOCK <name>.",
                    )
                if not edge_match:
                    _issue(
                        issues,
                        "CLOCKED_BLOCK_EDGE_MISSING",
                        "error",
                        line_number,
                        "CLOCKED block must declare EDGE RISING or EDGE FALLING.",
                    )
                active_clock = (
                    clock_match.group(1)
                    if clock_match
                    else None
                )
                active_edge = (
                    edge_match.group(1).upper()
                    if edge_match
                    else None
                )
                if active_clock and active_clock not in clocks:
                    _issue(
                        issues,
                        "CLOCKED_BLOCK_UNKNOWN_CLOCK",
                        "error",
                        line_number,
                        f"CLOCKED block references undeclared clock '{active_clock}'.",
                        identifier=active_clock,
                    )
                elif active_clock and active_edge != clocks[active_clock]["edge"]:
                    _issue(
                        issues,
                        "CLOCK_EDGE_MISMATCH",
                        "error",
                        line_number,
                        f"Clocked block edge {active_edge} does not agree with top-level edge {clocks[active_clock]['edge']} for clock '{active_clock}'.",
                        identifier=active_clock,
                    )
            continue

        legacy_match = re.match(
            r"^ON\s+(RISING|FALLING)\s+EDGE\s+OF\s+(" + IDENTIFIER + r")$",
            text,
            re.I,
        )
        if legacy_match:
            _issue(
                issues,
                "LEGACY_CLOCKED_SYNTAX",
                "error",
                line_number,
                "Legacy clocked-block syntax is not valid in Grammar v1.",
            )
            continue

        if upper == "END BLOCK" or upper == "END ON":
            active_clock = None
            active_kind = None
            active_line = None


def _block_ranges(lines: Sequence[tuple[int, str]]) -> list[dict[str, Any]]:
    ranges: list[dict[str, Any]] = []
    current: Optional[dict[str, Any]] = None
    for line_number, text in lines:
        block_match = re.match(r"^BLOCK\s+(CLOCKED|COMBINATIONAL)\b(.*)$", text, re.I)
        if block_match:
            kind = block_match.group(1).upper()
            remainder = block_match.group(2).strip()
            if kind == "COMBINATIONAL":
                if remainder:
                    current = None
                    continue
            elif not re.fullmatch(
                r"CLOCK\s+" + IDENTIFIER + r"\s+EDGE\s+(RISING|FALLING)",
                remainder,
                re.I,
            ):
                current = None
                continue
            current = {
                "kind": kind,
                "start": line_number,
                "end": None,
                "header": block_match.group(2).strip(),
                "lines": [],
            }
            ranges.append(current)
        elif current is not None and text.upper() == "END BLOCK":
            current["end"] = line_number
            current = None
        elif current is not None:
            current["lines"].append((line_number, text))
    return ranges


def _validate_assignments(
    lines: Sequence[tuple[int, str]],
    symbols: dict[str, Symbol],
    issues: list[ValidationIssue],
) -> None:
    blocks = _block_ranges(lines)

    for block in blocks:
        kind = block["kind"]
        assignments: list[tuple[int, str, str, str]] = []
        for line_number, text in block["lines"]:
            assignment = _extract_assignment(text)
            if assignment:
                lhs, operator, rhs = assignment
                assignments.append((line_number, lhs, operator, rhs))

                base = _base_identifier(lhs)
                if kind == "CLOCKED" and operator != "<=":
                    _issue(
                        issues,
                        "CLOCKED_ASSIGNMENT_OPERATOR",
                        "error",
                        line_number,
                        f"Clocked block assignments to '{base}' must use '<=' nonblocking assignment.",
                        identifier=base,
                    )
                if kind == "COMBINATIONAL" and operator != "=":
                    _issue(
                        issues,
                        "COMBINATIONAL_ASSIGNMENT_OPERATOR",
                        "error",
                        line_number,
                        f"Combinational assignments to '{base}' must use '=' blocking assignment.",
                        identifier=base,
                    )

                if base not in symbols:
                    _issue(
                        issues,
                        "UNDECLARED_ASSIGNMENT_TARGET",
                        "error",
                        line_number,
                        f"Assignment target '{base}' is not declared with REG, SIG, CLOCK, INPUT, OUTPUT, or INOUT.",
                        identifier=base,
                    )

        if kind == "COMBINATIONAL":
            _validate_combinational_completeness(block, assignments, issues)
        else:
            _validate_clocked_assignments(block, assignments, issues)

    for line_number, text in lines:
        if text.upper().startswith("ASSIGN "):
            if not any(
                block["start"] < line_number < (block["end"] or 10**9)
                for block in blocks
            ):
                _issue(
                    issues,
                    "ASSIGN_OUTSIDE_COMBINATIONAL_BLOCK",
                    "error",
                    line_number,
                    "ASSIGN statements are only valid inside BLOCK COMBINATIONAL.",
                )
        else:
            assignment = _extract_assignment(text)
            if assignment and "=" in assignment[1]:
                inside_clocked_or_combinational = any(
                    block["start"] < line_number < (block["end"] or 10**9)
                    for block in blocks
                )
                inside_function = False
                active_function = False
                for other_line, other_text in lines:
                    if other_line <= line_number and re.match(r"^FUNCTION\b", other_text, re.I):
                        active_function = True
                    if active_function and re.match(r"^END\s+FUNCTION$", other_text, re.I):
                        if other_line >= line_number:
                            inside_function = True
                        active_function = False
                if not inside_clocked_or_combinational and not inside_function and not re.match(r"^SET\b", text, re.I):
                    _issue(
                        issues,
                        "ASSIGNMENT_OUTSIDE_BLOCK",
                        "error",
                        line_number,
                        "Combinational assignments must occur inside BLOCK COMBINATIONAL; clocked assignments must occur inside BLOCK CLOCKED.",
                    )

    for line_number, text in lines:
        upper = text.upper()
        if re.match(r"^(REG|SIG)\b", text, re.I):
            continue
        assignment = _extract_assignment(text)
        if assignment and "=" in assignment[1]:
            pass


def _validate_combinational_completeness(
    block: dict[str, Any],
    assignments: list[tuple[int, str, str, str]],
    issues: list[ValidationIssue],
) -> None:
    if not assignments:
        return

    targets = sorted({_base_identifier(lhs) for _, lhs, _, _ in assignments})
    terminal_paths = _control_terminal_paths(block["lines"])
    for target in targets:
        missing_paths = [
            path for path in terminal_paths if target not in path
        ]
        if missing_paths:
            first_line = min(
                line for line, lhs, _, _ in assignments
                if _base_identifier(lhs) == target
            )
            _issue(
                issues,
                "COMBINATIONAL_PATH_INCOMPLETE",
                "error",
                first_line,
                f"Combinational target '{target}' does not receive exactly one final value on every terminal path.",
                identifier=target,
            )


def _validate_clocked_assignments(
    block: dict[str, Any],
    assignments: list[tuple[int, str, str, str]],
    issues: list[ValidationIssue],
) -> None:
    terminal_paths = _control_terminal_paths(block["lines"])
    reported: set[str] = set()
    for path in terminal_paths:
        for target, assignment_lines in path.items():
            if target in reported:
                continue
            if len(assignment_lines) > 1:
                line_number = assignment_lines[1]
                _issue(
                    issues,
                    "MULTIPLE_CLOCKED_ASSIGNMENTS",
                    "error",
                    line_number,
                    f"Register '{target}' is assigned multiple times within one clocked terminal branch. Grammar v1 requires one assignment per terminal path.",
                    identifier=target,
                )
                reported.add(target)


def _validate_functions(
    lines: Sequence[tuple[int, str]],
    issues: list[ValidationIssue],
) -> None:
    current: Optional[dict[str, Any]] = None
    functions: list[dict[str, Any]] = []

    for line_number, text in lines:
        declaration = re.match(
            r"^FUNCTION\s+(" + IDENTIFIER + r")\s*\(([^)]*)\)"
            r"(?:\s*->\s*\(([^)]*)\)|\s*->\s*([A-Za-z_][A-Za-z0-9_$]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_$]*)*))?\s*:?\s*$",
            text,
            re.I,
        )
        if declaration:
            name = declaration.group(1)
            parameters = [
                part.strip() for part in declaration.group(2).split(",") if part.strip()
            ]
            returns_text = declaration.group(3) if declaration.group(3) is not None else declaration.group(4)
            returns = [
                re.match(r"^(" + IDENTIFIER + r")", part.strip(), re.I).group(1)
                if re.match(r"^(" + IDENTIFIER + r")", part.strip(), re.I)
                else ""
                for part in (returns_text or "").split(",")
                if part.strip()
            ]
            current = {
                "name": name,
                "line": line_number,
                "parameters": parameters,
                "returns": returns,
                "assignments": [],
                "returns_seen": [],
                "end": None,
                "body_lines": [],
            }
            functions.append(current)
            continue
        if current is not None and text.upper() == "END FUNCTION":
            current["end"] = line_number
            current = None
            continue
        if current is None:
            continue

        current["body_lines"].append((line_number, text))

        return_match = re.match(r"^RETURN(?:\s+|\s*\()\s*(.*?)\)?\s*$", text, re.I)
        if return_match:
            returned = return_match.group(1).strip()
            values = [
                re.match(r"^(" + IDENTIFIER + r")", part.strip(), re.I).group(1)
                if re.match(r"^(" + IDENTIFIER + r")", part.strip(), re.I)
                else ""
                for part in returned.strip("()").split(",")
                if part.strip()
            ]
            current["returns_seen"].extend(values)
            continue

        assignment_text = text
        if text.upper().startswith("SET "):
            assignment_text = text[len("SET"):].strip()
        assignment = _extract_assignment(assignment_text)
        if assignment:
            lhs, _, _ = assignment
            current["assignments"].append((_base_identifier(lhs), line_number, text.upper()))

    for function in functions:
        if not function["returns"]:
            continue
        if len(function["returns_seen"]) == 0:
            _issue(
                issues,
                "FUNCTION_RETURN_MISSING",
                "error",
                function["line"],
                f"Function '{function['name']}' has declared return variables but no RETURN statement.",
                identifier=function["name"],
            )
        else:
            # Exactly one terminal RETURN is required; tolerate only one
            # occurrence on the flattened body.
            return_count = sum(
                1
                for _, text in lines
                if re.match(r"^RETURN(?:\s|\()", text, re.I)
                and function["line"] < _
                and (function["end"] is None or _ < function["end"])
            )
            if return_count != 1:
                _issue(
                    issues,
                    "FUNCTION_RETURN_COUNT",
                    "error",
                    function["line"],
                    f"Function '{function['name']}' must contain exactly one terminal RETURN statement.",
                    identifier=function["name"],
                )

        assigned = {name for name, _, _ in function["assignments"]}
        for return_name in function["returns"]:
            if return_name not in assigned:
                _issue(
                    issues,
                    "FUNCTION_RETURN_UNASSIGNED",
                    "error",
                    function["line"],
                    f"Declared return variable '{return_name}' in function '{function['name']}' has no final assigned value.",
                    identifier=return_name,
                )
            elif function["returns_seen"]:
                if return_name not in function["returns_seen"]:
                    _issue(
                        issues,
                        "FUNCTION_RETURN_NOT_RETURNED",
                        "error",
                        function["line"],
                        f"Function '{function['name']}' assigns return variable '{return_name}' but RETURN does not include it.",
                        identifier=return_name,
                    )

        terminal_paths = _control_terminal_paths(function["body_lines"])
        for return_name in function["returns"]:
            if any(return_name not in path for path in terminal_paths):
                _issue(
                    issues,
                    "FUNCTION_RETURN_PATH_INCOMPLETE",
                    "error",
                    function["line"],
                    f"Declared return variable '{return_name}' in function '{function['name']}' has no final value on every terminal path.",
                    identifier=return_name,
                )


def _validate_reset_metadata(
    lines: Sequence[tuple[int, str]],
    parser: GrammarParser,
    issues: list[ValidationIssue],
) -> None:
    reset_nodes = []
    # Reset syntax is authoritative in the clocked block.  Top-level RESET
    # declarations, if present, are treated as metadata and do not replace it.
    for line_number, text in lines:
        upper = text.upper()
        if not upper.startswith("RESET "):
            continue
        if upper.startswith("RESET NOT SPECIFIED"):
            reset_nodes.append(("not_specified", line_number, text))
        else:
            reset_match = re.match(
                r"^RESET\s+(SYNCHRONOUS|ASYNCHRONOUS)\s+"
                r"(?:SIGNAL\s+)?(" + IDENTIFIER + r")\s+"
                r"(?:POLARITY\s+(ACTIVE_HIGH|ACTIVE_LOW|HIGH|LOW))?\s*"
                r"(?:VALUE\s+(.+))?$",
                text,
                re.I,
            )
            if not reset_match:
                _issue(
                    issues,
                    "INVALID_RESET_SYNTAX",
                    "error",
                    line_number,
                    "Reset syntax must be RESET SYNCHRONOUS|ASYNCHRONOUS [SIGNAL <name>] [POLARITY ACTIVE_HIGH|ACTIVE_LOW|HIGH|LOW] [VALUE <expression>], or RESET NOT SPECIFIED.",
                )
            else:
                reset_nodes.append(("specified", line_number, text))

    for kind, line_number, text in reset_nodes:
        if kind == "not_specified":
            remainder = lines[max(0, line_number - 1):min(len(lines), line_number + 4)]


def _validate_unresolved(
    lines: Sequence[tuple[int, str]],
    issues: list[ValidationIssue],
) -> None:
    unresolved_targets: list[tuple[str, str, str, int]] = []
    unresolved_seen_line: set[int] = set()

    for line_number, text in lines:
        match = re.match(
            r"^UNRESOLVED\s+([^:]+)\s*:\s*([^-]+)\s*-\s*(.+)$",
            text,
            re.I,
        )
        if match:
            unresolved_seen_line.add(line_number)
            unresolved_targets.append(
                (match.group(1).strip().lower(), match.group(2).strip(), match.group(3).strip(), line_number)
            )
        elif text.upper().startswith("UNRESOLVED"):
            _issue(
                issues,
                "INVALID_UNRESOLVED_SYNTAX",
                "error",
                line_number,
                "UNRESOLVED must use: UNRESOLVED <scope> : <identifier_or_requirement> - <missing_detail>",
            )

    for line_number, text in lines:
        if text.upper().startswith("RESET NOT SPECIFIED"):
            has_reset_unresolved = any(
                scope in {"reset", "module", "clocked", "clocked reset"}
                for scope, _, _, _ in unresolved_targets
            )
            if not has_reset_unresolved:
                _issue(
                    issues,
                    "RESET_NOT_SPECIFIED_MISSING_UNRESOLVED",
                    "error",
                    line_number,
                    "RESET NOT SPECIFIED requires a matching UNRESOLVED entry, such as 'UNRESOLVED RESET : reset behavior - reset type, polarity, and value not specified'.",
                )
        if text.upper().startswith("CDC_"):
            # CDC-specific deterministic validation is performed below.
            pass

    if unresolved_targets:
        for scope, target, detail, line_number in unresolved_targets:
            _issue(
                issues,
                "UNRESOLVED_REQUIREMENT_BLOCKS_RTL",
                "error",
                line_number,
                f"Unresolved {scope} requirement '{target}' blocks RTL generation: {detail}",
                identifier=target,
            )


def _validate_cdc(
    lines: Sequence[tuple[int, str]],
    symbols: dict[str, Symbol],
    clocks: dict[str, dict[str, Any]],
    understanding: Optional[Any],
    specification: Optional[Any],
    issues: list[ValidationIssue],
) -> None:
    for line_number, text in lines:
        sync_match = re.match(
            r"^CDC_SYNC_REG\s+([A-Za-z_][A-Za-z0-9_$]*)"
            r"\s+FROM\s+([A-Za-z_][A-Za-z0-9_$]*)"
            r"\s+TO\s+([A-Za-z_][A-Za-z0-9_$]*)"
            r"\s+STAGES\s+([0-9]+)$",
            text,
            re.I,
        )
        handshake_match = re.match(
            r"^CDC_HANDSHAKE\s+([A-Za-z_][A-Za-z0-9_$]*)"
            r"\s+FROM\s+([A-Za-z_][A-Za-z0-9_$]*)"
            r"\s+TO\s+([A-Za-z_][A-Za-z0-9_$]*)$",
            text,
            re.I,
        )

        if text.upper().startswith("CDC_SYNC_REG"):
            if not sync_match:
                _issue(
                    issues,
                    "INVALID_CDC_SYNC_REG",
                    "error",
                    line_number,
                    "CDC_SYNC_REG syntax requires signal, FROM clock, TO clock, and STAGES count.",
                )
                continue
            signal, source, destination, stages = (
                sync_match.group(1),
                sync_match.group(2),
                sync_match.group(3),
                sync_match.group(4),
            )
        elif text.upper().startswith("CDC_HANDSHAKE"):
            if not handshake_match:
                _issue(
                    issues,
                    "INVALID_CDC_HANDSHAKE",
                    "error",
                    line_number,
                    "CDC_HANDSHAKE syntax requires signal, FROM clock, and TO clock.",
                )
                continue
            signal = handshake_match.group(1)
            source = handshake_match.group(2)
            destination = handshake_match.group(3)
            stages = None
        else:
            continue

        if signal not in symbols:
            _issue(
                issues,
                "CDC_SIGNAL_UNDECLARED",
                "error",
                line_number,
                f"CDC signal '{signal}' must be declared with REG or SIG.",
                identifier=signal,
            )
        elif symbols[signal].kind not in {"REG", "SIG"}:
            _issue(
                issues,
                "CDC_SIGNAL_DECLARATION_INVALID",
                "error",
                line_number,
                f"CDC signal '{signal}' must be declared with REG or SIG, not an interface declaration.",
                identifier=signal,
            )
        for clock_name, role in ((source, "source"), (destination, "destination")):
            if not clock_name:
                _issue(
                    issues,
                    "CDC_CLOCK_MISSING",
                    "error",
                    line_number,
                    f"CDC construct must declare a {role} clock.",
                )
            elif clock_name not in clocks:
                _issue(
                    issues,
                    "CDC_CLOCK_UNDECLARED",
                    "error",
                    line_number,
                    f"CDC {role} clock '{clock_name}' is not declared by CLOCK.",
                    identifier=clock_name,
                )
        if source and destination and source == destination:
            _issue(
                issues,
                "CDC_CLOCKS_NOT_DISTINCT",
                "error",
                line_number,
                "CDC source and destination clocks must be distinct.",
            )
        if stages is not None:
            stage_count = int(stages)
            if stage_count < 1:
                _issue(
                    issues,
                    "CDC_INVALID_STAGE_COUNT",
                    "error",
                    line_number,
                    "CDC_SYNC_REG STAGES must be at least 1.",
                )

        spec_text = _specification_text(specification, understanding)
        evidence_terms = ["cdc", "cross-domain", "cross domain", "clock domain", "synchron", "handshake"]
        if not spec_text or not any(term in spec_text for term in evidence_terms):
            _issue(
                issues,
                "CDC_SPECIFICATION_UNSUPPORTED",
                "error",
                line_number,
                "CDC construct is not supported by the provided specification or Understanding constraints.",
            )


def _validate_reset(
    lines: Sequence[tuple[int, str]],
    parser: GrammarParser,
    issues: list[ValidationIssue],
) -> None:
    active_clocked_block = False
    for line_number, text in lines:
        upper = text.upper()
        block_match = re.match(r"^BLOCK\s+(CLOCKED|COMBINATIONAL)\b(.*)$", text, re.I)
        if block_match:
            active_clocked_block = block_match.group(1).upper() == "CLOCKED"
            continue
        if upper == "END BLOCK":
            active_clocked_block = False
            continue
        if not upper.startswith("RESET "):
            continue

        if not active_clocked_block:
            _issue(
                issues,
                "RESET_OUTSIDE_CLOCKED_BLOCK",
                "error",
                line_number,
                "Reset declarations must belong to a valid CLOCKED block.",
            )
            continue

        if upper.startswith("RESET NOT SPECIFIED"):
            if upper != "RESET NOT SPECIFIED":
                _issue(
                    issues,
                    "RESET_DETAILS_INCOMPLETE",
                    "error",
                    line_number,
                    "RESET NOT SPECIFIED must be written exactly as 'RESET NOT SPECIFIED' and followed by END RESET.",
                )
            continue

        reset_match = re.match(
            r"^RESET\s+(SYNCHRONOUS|ASYNCHRONOUS)\b"
            r"\s+SIGNAL\s+(" + IDENTIFIER + r")"
            r"\s+(ACTIVE_HIGH|ACTIVE_LOW)"
            r"\s+VALUE\s+(.+)$",
            text,
            re.I,
        )
        if not reset_match:
            _issue(
                issues,
                "RESET_DETAILS_INCOMPLETE",
                "error",
                line_number,
                "Specified reset syntax is RESET SYNCHRONOUS|ASYNCHRONOUS SIGNAL <name> ACTIVE_HIGH|ACTIVE_LOW VALUE <expression>.",
            )
            continue

        _, signal, _, _ = reset_match.groups()
        if signal not in parser.symbols:
            _issue(
                issues,
                "RESET_SIGNAL_UNDECLARED",
                "error",
                line_number,
                f"Reset signal '{signal}' is not declared.",
                identifier=signal,
            )


def _validate_expression_types(
    lines: Sequence[tuple[int, str]],
    symbols: dict[str, Symbol],
    issues: list[ValidationIssue],
) -> None:
    binary_literal = re.compile(r"0b([01]+)", re.I)
    for line_number, text in lines:
        assignment = _extract_assignment(text)
        if not assignment:
            continue
        lhs, operator, rhs = assignment
        if "'" in rhs and not re.search(r"\b\d+'[bodh][0-9a-fA-F_]+\b", rhs, re.I):
            _issue(
                issues,
                "INVALID_LITERAL_SYNTAX",
                "error",
                line_number,
                "Sized literals must use <width>'b<digits>, <width>'d<digits>, <width>'h<digits>, or <width>'o<digits>.",
            )
        if re.search(r"0bb[01]+", rhs, re.I):
            _issue(
                issues,
                "INVALID_BINARY_LITERAL",
                "error",
                line_number,
                "Binary literals use '0b' followed by binary digits; '0bb...' is invalid.",
            )
        if re.search(r"\b\d+b[01]+\b", rhs, re.I):
            _issue(
                issues,
                "INVALID_BINARY_LITERAL",
                "error",
                line_number,
                "Grammar v1 uses sized binary literals such as 8'b00000000, not 8b00000000.",
            )

        for literal_match in binary_literal.finditer(rhs):
            pass

        base = _base_identifier(lhs)
        symbol = symbols.get(base)
        if symbol and symbol.width and WIDTH_RE.fullmatch(symbol.width):
            width_match = WIDTH_RE.fullmatch(symbol.width)
            target_width = int(width_match.group(1)) - int(width_match.group(2)) + 1
            sized_literals = re.findall(r"\b([0-9]+)'([bBdDoOhH])([0-9a-fA-F_]+)\b", rhs, re.I)
            for literal_width, _, digits in sized_literals:
                if int(literal_width) != target_width:
                    _issue(
                        issues,
                        "WIDTH_MISMATCH",
                        "error",
                        line_number,
                        f"Literal width {literal_width} does not match target '{base}' width {target_width}.",
                        identifier=base,
                    )
            for bits in re.findall(r"\b0b([01]+)\b", rhs):
                if len(bits) != target_width:
                    _issue(
                        issues,
                        "WIDTH_MISMATCH",
                        "error",
                        line_number,
                        f"Unsized binary literal width {len(bits)} does not match target '{base}' width {target_width}.",
                        identifier=base,
                    )

        if "<=" in operator and text.strip().upper().startswith("BLOCK"):
            _issue(
                issues,
                "CLOCKED_ASSIGNMENT_OPERATOR",
                "error",
                line_number,
                "Clocked assignment syntax is '<='.",
            )


def _validate_specification_awareness(
    lines: Sequence[tuple[int, str]],
    symbols: dict[str, Symbol],
    clocks: dict[str, dict[str, Any]],
    specification: Optional[Any],
    understanding: Optional[Any],
    context: Mapping[str, Any],
    issues: list[ValidationIssue],
) -> None:
    spec_text = _specification_text(specification, understanding)
    if isinstance(understanding, Mapping):
        inputs = understanding.get("inputs", []) or []
        outputs = understanding.get("outputs", []) or []
        constraints = understanding.get("constraints", []) or []
        ambiguities = understanding.get("ambiguities", []) or []
    elif understanding is not None:
        inputs = getattr(understanding, "inputs", []) or []
        outputs = getattr(understanding, "outputs", []) or []
        constraints = getattr(understanding, "constraints", []) or []
        ambiguities = getattr(understanding, "ambiguities", []) or []
    else:
        inputs = []
        outputs = []
        constraints = []
        ambiguities = []

    declared_interfaces: set[str] = set()
    for line_number, text in lines:
        match = re.match(r"^(INPUT|OUTPUT|INOUT)\s+(" + IDENTIFIER + r")\b", text, re.I)
        if match:
            declared_interfaces.add(match.group(2))
        clock_match = re.match(r"^CLOCK\s+(" + IDENTIFIER + r")\b", text, re.I)
        if clock_match:
            declared_interfaces.add(clock_match.group(1))

    expected_names: set[str] = set()
    for item in list(inputs or []) + list(outputs or []):
        first = re.search(r"\b(" + IDENTIFIER + r")\b", str(item))
        if first:
            expected_names.add(first.group(1))
    for expected in sorted(expected_names):
        if expected.lower() not in {name.lower() for name in declared_interfaces}:
            _issue(
                issues,
                "INTERFACE_MISSING_FROM_UNDERSTANDING",
                "error",
                None,
                f"Interface '{expected}' is identified by Understanding but is missing from the pseudocode declarations.",
                identifier=expected,
            )

    for line_number, text in lines:
        for keyword in ("CLOCK", "INPUT", "OUTPUT", "INOUT", "REG", "SIG"):
            match = re.match(r"^" + keyword + r"\s+(" + IDENTIFIER + r")(?:\[([0-9]+):([0-9]+)\])?", text, re.I)
            if not match:
                continue
            name = match.group(1)
            if spec_text and name.lower() not in spec_text and keyword in {"CLOCK", "INPUT", "OUTPUT", "INOUT"}:
                _issue(
                    issues,
                    "INTERFACE_UNSUPPORTED_BY_SPECIFICATION",
                    "error",
                    line_number,
                    f"Interface declaration '{name}' is not supported by the original specification or Understanding evidence.",
                    identifier=name,
                )
            break

    for line_number, text in lines:
        if text.upper().startswith("RESET NOT SPECIFIED"):
            # The unresolved entry is handled by the unresolved/reset passes.
            continue
        if text.upper().startswith("RESET "):
            reset_words = re.findall(r"[A-Za-z_][A-Za-z0-9_$]*", text)
            supported = any(
                word.lower() in spec_text
                for word in reset_words
                if word.upper() in {"SYNCHRONOUS", "ASYNCHRONOUS", "ACTIVE_HIGH", "ACTIVE_LOW"}
            )
            if not supported and spec_text:
                _issue(
                    issues,
                    "RESET_SPECIFICATION_UNSUPPORTED",
                    "error",
                    line_number,
                    "Reset type or polarity is not supported by the provided specification or Understanding evidence.",
                )
            reset_match = re.match(
                r"^RESET\s+(SYNCHRONOUS|ASYNCHRONOUS)\b.*?\b(ACTIVE_HIGH|ACTIVE_LOW)\b",
                text,
                re.I,
            )
            if reset_match:
                reset_mode = reset_match.group(1).upper()
                reset_polarity = reset_match.group(2).upper()
                opposite_mode = "ASYNCHRONOUS" if reset_mode == "SYNCHRONOUS" else "SYNCHRONOUS"
                opposite_polarity = "ACTIVE_LOW" if reset_polarity == "ACTIVE_HIGH" else "ACTIVE_HIGH"
                if re.search(r"\b" + opposite_mode.lower() + r"\b", spec_text):
                    _issue(
                        issues,
                        "RESET_SPECIFICATION_UNSUPPORTED",
                        "error",
                        line_number,
                        f"Reset type '{reset_mode}' conflicts with specification evidence for '{opposite_mode}'.",
                    )
                if re.search(r"\b" + opposite_polarity.lower() + r"\b", spec_text):
                    _issue(
                        issues,
                        "RESET_SPECIFICATION_UNSUPPORTED",
                        "error",
                        line_number,
                        f"Reset polarity '{reset_polarity}' conflicts with specification evidence for '{opposite_polarity}'.",
                    )

    unresolved_entries = []
    for _, text in lines:
        match = re.match(
            r"^UNRESOLVED\s+([^:]+)\s*:\s*([^-]+)\s*-\s*(.+)$",
            text,
            re.I,
        )
        if match:
            unresolved_entries.append(
                (match.group(1).strip().lower(), match.group(2).strip().lower(), match.group(3).strip().lower())
            )

    for ambiguity in ambiguities or []:
        ambiguity_text = str(ambiguity).lower()
        words = {
            word for word in re.findall(r"[a-z][a-z0-9_]+", ambiguity_text)
            if len(word) >= 4 and word not in {"specified", "unspecified", "ambiguous", "behavior", "required", "missing"}
        }
        matched = False
        for scope, target, detail in unresolved_entries:
            unresolved_text = f"{scope} {target} {detail}"
            overlap = words.intersection(set(re.findall(r"[a-z][a-z0-9_]+", unresolved_text)))
            if overlap or any(word in unresolved_text for word in words):
                matched = True
                break
        if not matched:
            _issue(
                issues,
                "AMBIGUITY_UNRESOLVED_MISMATCH",
                "error",
                None,
                f"Implementation ambiguity '{ambiguity}' is not matched to a relevant UNRESOLVED scope/target.",
            )


def validate_pseudocode(
    pseudocode: Any,
    specification: Optional[Any] = None,
    understanding: Optional[Any] = None,
    **context: Any,
) -> list[str]:
    """Compatibility wrapper returning human-readable errors and warnings."""

    result = validate_pseudocode_detailed(
        pseudocode,
        specification=specification,
        understanding=understanding,
        **context,
    )
    return [
        f"Line {issue.line}: {issue.message}" if issue.line is not None else issue.message
        for issue in result.issues
        if issue.severity == "error"
    ]

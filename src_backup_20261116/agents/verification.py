import json
import os
import re
from typing import Any

from langchain.agents import create_agent
from langchain_core.documents import Document

try:
    import openai
except ImportError:
    openai = None

from src.llm.llm import get_llm
from src.schemas import VerificationResult


SYSTEM_PROMPT = """
You are the Verification Agent in the SPEC2RTL system.

For description verification, compare a component description with the
original hardware specification and the supplied component interface.


For RTL verification, compare generated Verilog RTL with the original
hardware specification. The specification is the primary source of truth.
Supporting understanding, decomposition, descriptions and pseudocode must
never override it.

This is static textual review only. Do not execute, compile or simulate RTL.
Do not claim formal verification or proven functional correctness.

Check functional requirements, inputs and outputs, signal widths,
clock/reset behavior, state transitions, combinational/sequential logic,
component integration, RTL structure and specification traceability.
Do not invent requirements or assume unspecified behavior. Distinguish
definite errors from uncertain behavior and unresolved ambiguities.

Set valid=true only when no clear mismatch or missing required behavior is
found through static review. Set valid=false when a clear error, contradiction
or missing required behavior is found. Explain issues and give actionable
suggestions without generating replacement RTL.

The final response must conform strictly to the VerificationResult schema.
"""


def is_free_openrouter_model() -> bool:
    """Return whether the configured model appears to be an OpenRouter free model."""
    model = (
        os.getenv("SPEC2RTL_OPENROUTER_VERIFICATION_MODEL")
        or os.getenv("SPEC2RTL_OPENROUTER_UNDERSTANDING_MODEL")
        or os.getenv("OPENROUTER_MODEL")
        or os.getenv("SPEC2RTL_OPENROUTER_MODEL")
        or ""
    )
    return model.strip().lower().endswith(":free")


def create_verification_agent():
    return create_agent(
        model=get_llm("verification"),
        tools=[],
        response_format=VerificationResult,
        system_prompt=SYSTEM_PROMPT,
    )


def _extract_verification_json(content: Any) -> dict:
    """Extract a JSON verification object from common LLM response formats."""
    if isinstance(content, dict):
        # Structured response may already be a dict.
        if "valid" in content:
            return content
        content = content.get("content", content.get("text", ""))

    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(str(item.get("text", "")))
            elif isinstance(item, str):
                text_parts.append(item)
        content = "\n".join(text_parts)

    if not isinstance(content, str) or not content.strip():
        raise ValueError("Verification agent returned empty response content")

    text = content.strip()
    # Accept fenced JSON while keeping ordinary JSON strict.
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.I | re.S)
    if fenced:
        text = fenced.group(1).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        # Some providers add prose around a JSON object. Extract the outermost
        # object as a conservative compatibility measure.
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Verification agent returned invalid JSON") from exc
        try:
            parsed = json.loads(text[start:end + 1])
        except json.JSONDecodeError as nested_exc:
            raise ValueError("Verification agent returned invalid JSON") from nested_exc

    if not isinstance(parsed, dict):
        raise ValueError("Verification agent returned invalid JSON")
    return parsed


def _field(obj: Any, key: str, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _port_map(ports: Any) -> dict[str, str]:
    """Normalize port strings such as data[7:0] into name -> width."""
    result = {}
    for port in ports or []:
        if isinstance(port, str):
            match = re.fullmatch(r"\s*([A-Za-z_]\w*)\s*(?:\[(\d+)\s*:\s*(\d+)\])?\s*", port)
            if not match:
                continue
            name, msb, lsb = match.groups()
            width = str(abs(int(msb) - int(lsb)) + 1) if msb is not None else "1"
            result[name] = width
        else:
            name = _field(port, "name")
            if name:
                result[str(name)] = str(_field(port, "width", "1"))
    return result


def check_interface_consistency(component: Any, description: Any) -> tuple[bool, list[str]]:
    """Compare the component's declared interface with its description."""
    issues = []
    expected_inputs = _port_map(_field(component, "inputs", []))
    expected_outputs = _port_map(_field(component, "outputs", []))

    described_inputs = _port_map(_field(description, "inputs", []))
    described_outputs = _port_map(_field(description, "outputs", []))

    for name in sorted(set(described_inputs) - set(expected_inputs)):
        issues.append(f"Extra input: {name}")
    for name in sorted(set(described_outputs) - set(expected_outputs)):
        issues.append(f"Extra output: {name}")
    for name in sorted(set(expected_inputs) - set(described_inputs)):
        issues.append(f"Missing input: {name}")
    for name in sorted(set(expected_outputs) - set(described_outputs)):
        issues.append(f"Missing output: {name}")

    for name in sorted(set(expected_inputs) & set(described_inputs)):
        if expected_inputs[name] != described_inputs[name]:
            issues.append(
                f"Input width mismatch for {name}: expected {expected_inputs[name]}, "
                f"described {described_inputs[name]}"
            )
    for name in sorted(set(expected_outputs) & set(described_outputs)):
        if expected_outputs[name] != described_outputs[name]:
            issues.append(
                f"Output width mismatch for {name}: expected {expected_outputs[name]}, "
                f"described {described_outputs[name]}"
            )

    return not issues, issues


def _invoke_verification_agent(
    user_prompt: str,
    raise_on_error: bool = False,
) -> VerificationResult:
    print("[VERIFICATION] Creating agent...")
    try:
        agent = create_verification_agent()
    except Exception as error:
        err_msg = f"Failed to initialize verification agent: {type(error).__name__}: {error}"
        print(f"[VERIFICATION] ERROR: {err_msg}")
        if raise_on_error:
            raise
        return VerificationResult(
            valid=False,
            issues=[err_msg],
            suggestions=["Check model configuration, API credentials, and network connectivity."],
            reasoning=f"Verification agent initialization failed: {type(error).__name__}: {error}",
        )

    print("[VERIFICATION] Sending request to LLM...")
    try:
        response = agent.invoke(
            {"messages": [{"role": "user", "content": user_prompt}]}
        )
        print("[VERIFICATION] LLM response received!")
    except Exception as error:
        if raise_on_error:
            print(f"[VERIFICATION] ERROR: LLM request failed ({type(error).__name__}: {error})")
            raise

        is_timeout = (
            (openai and isinstance(error, openai.APITimeoutError))
            or "timeout" in type(error).__name__.lower()
            or "timeout" in str(error).lower()
        )
        is_rate_limit = (
            (openai and isinstance(error, openai.RateLimitError))
            or "ratelimit" in type(error).__name__.lower()
            or "rate limit" in str(error).lower()
            or "429" in str(error)
        )
        is_connection = (
            (openai and isinstance(error, openai.APIConnectionError))
            or "connection" in type(error).__name__.lower()
            or "connection" in str(error).lower()
        )

        if is_timeout:
            prefix = "TIMEOUT_ERROR"
            print(f"[VERIFICATION] TIMEOUT ERROR: LLM request timed out ({error})")
            suggestion = "The LLM provider timed out. Check network latency or increase timeout."
        elif is_rate_limit:
            prefix = "RATE_LIMIT_ERROR"
            print(f"[VERIFICATION] RATE LIMIT ERROR: OpenRouter rate limit exceeded ({error})")
            suggestion = "OpenRouter rate limit reached. Wait before retrying or use a different model key."
        elif is_connection:
            prefix = "CONNECTION_ERROR"
            print(f"[VERIFICATION] CONNECTION ERROR: Connection to LLM provider failed ({error})")
            suggestion = "Could not reach OpenRouter. Check internet connectivity and proxy settings."
        else:
            prefix = "LLM_ERROR"
            print(f"[VERIFICATION] ERROR: LLM request failed ({type(error).__name__}: {error})")
            suggestion = "Check LLM configuration and OpenRouter status."

        return VerificationResult(
            valid=False,
            issues=[f"{prefix}: {type(error).__name__}: {error}"],
            suggestions=[suggestion],
            reasoning=f"RTL verification could not complete because the LLM call failed: {type(error).__name__}: {error}",
        )

    print("[VERIFICATION] Parsing verification result...")
    try:
        structured = response.get("structured_response") if isinstance(response, dict) else None
        if isinstance(structured, VerificationResult):
            print("[VERIFICATION] Verification completed!")
            return structured
        if structured is not None:
            res = VerificationResult(**structured) if isinstance(structured, dict) else structured
            print("[VERIFICATION] Verification completed!")
            return res

        content = response.get("messages", response) if isinstance(response, dict) else response
        parsed = _extract_verification_json(content)
        res = VerificationResult(**parsed)
        print("[VERIFICATION] Verification completed!")
        return res
    except Exception as error:
        err_msg = f"Failed to parse verification result: {type(error).__name__}: {error}"
        print(f"[VERIFICATION] PARSING ERROR: {err_msg}")
        if raise_on_error:
            raise
        return VerificationResult(
            valid=False,
            issues=[f"PARSING_ERROR: {err_msg}"],
            suggestions=["The model response did not conform to the expected VerificationResult schema."],
            reasoning=f"RTL verification output could not be parsed: {type(error).__name__}: {error}",
        )


def verify_description(
    source_chunks: list[Document],
    description: Any,
    component: Any = None,
    interactions: Any = None,
) -> VerificationResult:
    """Verify a component description against source specification evidence."""
    if not source_chunks:
        raise ValueError("Cannot verify description: original specification is empty.")

    specification = "\n\n".join(
        getattr(chunk, "page_content", str(chunk)) for chunk in source_chunks
    )
    interface_context = ""
    if component is not None:
        interface_context += f"\nCOMPONENT INTERFACE:\n{component}"
    if interactions is not None:
        interface_context += f"\nCOMPONENT INTERACTIONS:\n{interactions}"

    prompt = f"""
Verify the following component description against the original specification.
The specification is authoritative. Check purpose, inputs, outputs, state,
constraints and behavior. Identify unsupported assumptions, omissions and
contradictions. This is static textual review only.

ORIGINAL HARDWARE SPECIFICATION:
{specification}

COMPONENT DESCRIPTION:
{description}
{interface_context}

Return a VerificationResult with valid, issues, suggestions and reasoning.
"""
    return _invoke_verification_agent(prompt, raise_on_error=True)

def get_value(obj: Any, key: str, default=None):
    """Get a field from either a dictionary or a Pydantic model."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def serialize_rtl(generated_rtl: Any) -> str:
    """Extract integrated RTL, component RTL, connections and generation notes.

    When integrated RTL is available, it is used as the primary RTL input and
    individual component code is not duplicated, reducing prompt size while
    preserving full verification context.
    """
    parts = []
    module_name = get_value(generated_rtl, "module_name", "Unknown")
    language = get_value(generated_rtl, "language", "Verilog")
    parts.append(f"Top-level module: {module_name}")
    parts.append(f"RTL language: {language}")

    integrated_code = (
        get_value(generated_rtl, "rtl_code")
        or get_value(generated_rtl, "code")
    )
    has_integrated = bool(integrated_code and str(integrated_code).strip())

    if has_integrated:
        parts.append("INTEGRATED RTL:\n" + str(integrated_code).strip())
    else:
        # Integrated RTL is unavailable; fall back to individual component RTL
        component_modules = get_value(generated_rtl, "component_modules", []) or []
        for component in component_modules:
            code = get_value(component, "rtl_code", get_value(component, "code", ""))
            parts.append(
                "\n".join([
                    f"COMPONENT: {get_value(component, 'component_name', 'Unknown')}",
                    f"MODULE NAME: {get_value(component, 'module_name', 'Unknown')}",
                    f"INPUTS: {get_value(component, 'inputs', [])}",
                    f"OUTPUTS: {get_value(component, 'outputs', [])}",
                    f"GENERATION STATUS: {get_value(component, 'generation_status', 'Unknown')}",
                    f"RTL CODE:\n{code}",
                ])
            )

    # When integrated RTL is available, provide lightweight component module interface summaries
    # without duplicating the Verilog source code.
    if has_integrated:
        component_modules = get_value(generated_rtl, "component_modules", []) or []
        if component_modules:
            comp_summaries = []
            for component in component_modules:
                comp_summaries.append(
                    f"- Component '{get_value(component, 'component_name', 'Unknown')}' "
                    f"(Module: {get_value(component, 'module_name', 'Unknown')}, "
                    f"Inputs: {get_value(component, 'inputs', [])}, "
                    f"Outputs: {get_value(component, 'outputs', [])}, "
                    f"Status: {get_value(component, 'generation_status', 'Unknown')})"
                )
            parts.append("COMPONENT MODULE INTERFACES:\n" + "\n".join(comp_summaries))

    for key, heading in [
        ("component_instances", "COMPONENT INSTANCES AND CONNECTIONS"),
        ("interactions", "COMPONENT INTERACTIONS"),
        ("assumptions", "RTL GENERATION ASSUMPTIONS"),
        ("unresolved_issues", "UNRESOLVED ISSUES"),
        ("generation_issues", "RTL GENERATION ISSUES"),
    ]:
        value = get_value(generated_rtl, key, []) or []
        if value:
            parts.append(f"{heading}:\n" + "\n".join(str(item) for item in value))

    return "\n\n".join(parts)


def verify_rtl(
    source_chunks: list[Document],
    generated_rtl: Any,
    understanding: Any = None,
    decomposition: Any = None,
    descriptions: list[Any] | None = None,
    pseudocode: Any = None,
) -> VerificationResult:
    """Statically verify generated RTL against the original hardware specification."""
    if not source_chunks:
        raise ValueError("Cannot verify RTL: original specification is empty.")
    if generated_rtl is None:
        raise ValueError("Cannot verify RTL: generated RTL output is missing.")

    print("[VERIFICATION] Preparing verification prompt...")
    specifications = "\n\n".join(
        getattr(doc, "page_content", str(doc)) for doc in source_chunks
    )
    rtl_content = serialize_rtl(generated_rtl)

    supporting_context = []
    if understanding is not None:
        supporting_context.append(f"UNDERSTANDING AGENT OUTPUT:\n{understanding}")
    if decomposition is not None:
        supporting_context.append(f"DECOMPOSER AGENT OUTPUT:\n{decomposition}")
    if descriptions:
        supporting_context.append(
            "DESCRIPTION AGENT OUTPUT:\n" +
            "\n\n".join(str(item) for item in descriptions)
        )
    if pseudocode is not None:
        supporting_context.append(f"PSEUDOCODE AGENT OUTPUT:\n{pseudocode}")

    context = "\n\n".join(supporting_context)
    prompt = f"""
ORIGINAL HARDWARE SPECIFICATION:
{specifications}

GENERATED VERILOG RTL:
{rtl_content}

SUPPORTING AGENT INFORMATION:
{context if context else "No additional context provided."}

Perform static textual review only. Verify individual component modules and
integrated RTL against the original specification. Check functionality,
interfaces, clock/reset behavior, state transitions, connections and
traceability. Distinguish definite errors, missing behavior, unsupported
assumptions and unresolved ambiguities. Do not execute, compile or simulate
the RTL. Return a VerificationResult.
"""
    spec_chars = len(specifications)
    rtl_chars = len(rtl_content)
    context_chars = len(context)
    total_chars = len(prompt)

    print(f"[VERIFICATION] Original specification: {spec_chars} characters")
    print(f"[VERIFICATION] Generated RTL: {rtl_chars} characters")
    print(f"[VERIFICATION] Supporting context: {context_chars} characters")
    print(f"[VERIFICATION] Total verification prompt: {total_chars} characters")

    return _invoke_verification_agent(prompt, raise_on_error=False)
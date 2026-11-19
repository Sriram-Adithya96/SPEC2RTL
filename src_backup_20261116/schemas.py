from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
class Understanding(BaseModel):

    system_purpose: str = Field(
        description="Concise description of the hardware system's purpose."
    )

    major_components: List[str] = Field(
        description=(
            "Explicitly named components and meaningful functional groupings "
            "supported by the specification. Do not invent physical modules."
        )
    )

    inputs: List[str] = Field(
        description=(
            "All explicitly defined input signals and interfaces, "
            "preserving exact names, widths and stated behavior."
        )
    )

    outputs: List[str] = Field(
        description=(
            "All explicitly defined output signals and interfaces, "
            "preserving exact names, widths and stated behavior."
        )
    )

    functional_requirements: List[str] = Field(
        description=(
            "All explicitly stated functional behaviors, including "
            "operations, opcode mappings, reset behavior, error handling "
            "and timing-dependent behavior."
        )
    )

    constraints: List[str] = Field(
        description=(
            "All explicitly stated clock, timing, reset, synchronization, "
            "resource, performance and implementation constraints."
        )
    )

    ambiguities: List[str] = Field(
        description=(
            "Explicit contradictions, unclear requirements and missing "
            "information necessary to understand specified behavior."
        )
    )


# -------------------------
# Specification
# -------------------------
class Component(BaseModel):
    name: str
    purpose: str
    inputs: List[str]
    outputs: List[str]


class ImplementationStep(BaseModel):
    step_number: int
    title: str
    description: str



class DecompositionOutput(BaseModel):
    components: List[Component]
    interactions: List[str]
    implementation_plan: List[ImplementationStep]


class Signal(BaseModel):
    name: str
    direction: str
    width: str
    description: str


class StateElement(BaseModel):
    name: str
    type: str
    width: str
    reset_value: str
    description: str


class DescriptionOutput(BaseModel):
    module_name: str
    purpose: str
    inputs: List[Signal]
    outputs: List[Signal]
    state_elements: List[StateElement]
    constraints: List[str]
    behavior: List[str]
    spec_references: List[str]



class VerificationResult(BaseModel):
    valid: bool
    issues: List[str]
    suggestions: List[str]
    reasoning: str


class CodeOuput(BaseModel):
    component_name: str = ""
    code: str = ""
    assumptions: List[str] = Field(default_factory=list)


class ReflectionOutput(BaseModel):
    needs_revision: bool = False
    feedback: List[str] = Field(default_factory=list)
    reasoning: str = ""
    corrected_code: Optional[Any] = None


class RTLReflectionOutput(BaseModel):
    needs_revision: bool = Field(
        default=False,
        description="Whether the generated RTL requires revision based on verification issues.",
    )
    feedback: List[str] = Field(
        default_factory=list,
        description="Actionable, specific correction instructions for the RTL generation agent.",
    )
    component_feedback: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Actionable correction instructions mapped by component or module name.",
    )
    reasoning: str = Field(
        default="",
        description="Detailed analysis of why revision is needed based strictly on the specification.",
    )



class DescriptionRevisionInput(BaseModel):
    description: DescriptionOutput
    verification: VerificationResult


class ImplementationPlan(BaseModel):
    module_name: str
    objective: str
    steps: List[ImplementationStep]

class ComponentPseudocodeOutput(BaseModel):
    component_name: str
    module_name: str
    inputs: List[str]
    outputs: List[str]
    pseudocode: List[str]
    assumptions: List[str]
    unresolved_issues: List[str]
    generation_status: str = "completed"
    validation_status: str = "not_run"
    validation_issues: List[dict] = Field(default_factory=list)


class PseudocodeGenerationOutput(BaseModel):
    components: List[ComponentPseudocodeOutput]
    assumptions: List[str] = Field(default_factory=list)
    unresolved_issues: List[str] = Field(default_factory=list)
    generation_status: str = "completed"
    validation_status: str = "not_run"
    validation_issues: List[dict] = Field(default_factory=list)
    execution_status: str = "not_attempted"
    execution_output: str = "No execution has been attempted."
    execution_errors: List[str] = Field(default_factory=list)


class ComponentRTLModuleOutput(BaseModel):
    component_name: str
    module_name: str
    inputs: List[str]
    outputs: List[str]
    rtl_code: str = ""
    generation_status: str = "not_run"
    generation_error: Optional[str] = None


class ComponentRTLInstanceOutput(BaseModel):
    component_name: str
    module_name: str
    instance_name: str
    port_connections: Dict[str, str] = Field(default_factory=dict)


class RTLGenerationOutput(BaseModel):
    module_name: str = "system_top"
    language: str = "Verilog"
    rtl_code: str = ""
    component_modules: List[ComponentRTLModuleOutput] = Field(default_factory=list)
    component_instances: List[ComponentRTLInstanceOutput] = Field(default_factory=list)
    interactions: List[str] = Field(default_factory=list)
    generation_status: str = "not_run"
    generation_issues: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    unresolved_issues: List[str] = Field(default_factory=list)

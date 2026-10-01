from pydantic import BaseModel 
from typing import List, Optional, Dict 



class Understanding(BaseModel):
    system_purpose: str
    major_components: List[str] 
    inputs: List[str]
    outputs: List[str]
    functional_requirements: List[str]
    constraints: List[str]
    ambiguities: List[str]




from pydantic import BaseModel
from typing import List


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
    width: int
    description: str


class DescriptionOutput(BaseModel):
    module_name: str
    purpose: str
    inputs: List[Signal]
    outputs: List[Signal]
    internal_signals: List[Signal]
    behavior: List[str]



class VerificationResult(BaseModel):
    valid: bool
    issues: List[str]
    suggestions: List[str]
    reasoning: str



class DescriptionRevisionInput(BaseModel):
    description: DescriptionOutput
    verification: VerificationResult


class ImplementationStep(BaseModel):
    step_number: int
    title: str
    description: str


class ImplementationPlan(BaseModel):
    module_name: str
    objective: str
    steps: List[ImplementationStep]
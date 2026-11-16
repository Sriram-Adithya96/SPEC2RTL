from typing import Any

from pydantic import BaseModel, Field


class ComponentProgress(BaseModel):
    name: str
    status: str
    generation_status: str | None = None
    interface_validation_status: str | None = None
    errors: list[str] = Field(default_factory=list)


class AgentState(BaseModel):
    status: str
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    message: str | None = None
    components: list[ComponentProgress] = Field(default_factory=list)
    component_generation_status: str | None = None
    interface_validation_status: str | None = None
    integration_status: str | None = None
    compilation_status: str | None = None


class RunSummary(BaseModel):
    run_id: str | None = None
    overall_status: str | None = None
    input_document: str | None = None
    original_documents: int | None = None
    parent_chunks: int | None = None
    child_chunks: int | None = None
    extracted_characters: int | None = None
    components_described: int | None = None
    verification_passed: int | None = None
    verification_failed: int | None = None
    reflection: str | None = None
    pseudocode: str | None = None
    pseudocode_validation: str | None = None
    pseudocode_execution: str | None = None
    rtl_generation: str | None = None
    rtl_agent_status: str | None = None
    rtl_module_name: str | None = None
    rtl_component_modules: int | None = None
    pseudocode_generation_status: str | None = None
    pseudocode_validation_status: str | None = None
    pseudocode_validation_errors: list[Any] = Field(default_factory=list)
    unresolved_requirements: list[str] = Field(default_factory=list)
    interface_validation: str | None = None
    integration_status: str | None = None
    compilation_status: str | None = None
    functional_simulation_status: str | None = None
    production_verified: bool = False
    experimental: bool = True
    stages: dict[str, str] = Field(default_factory=dict)
    components: list[dict[str, Any]] = Field(default_factory=list)
    artifact_paths: dict[str, Any] = Field(default_factory=dict)


class RunMetadata(BaseModel):
    run_id: str
    filename: str
    file_size: int
    file_type: str
    started_at: str
    finished_at: str | None = None
    status: str
    error: str | None = None
    failed_stage: str | None = None
    ingestion: str = "pending"
    agents: dict[str, AgentState]
    summary: RunSummary | None = None
    source: str | None = None


class RunListResponse(BaseModel):
    runs: list[RunMetadata]


class CreateRunResponse(BaseModel):
    run_id: str
    status: str


class OutputIndex(BaseModel):
    files: list[str]
    agents: dict[str, str]
    artifacts: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str


class ErrorDetail(BaseModel):
    detail: Any

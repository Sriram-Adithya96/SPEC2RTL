from typing import Any, Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]


class RunResponse(BaseModel):
    run_id: str
    filename: str
    file_size: int
    file_type: str
    started_at: str
    finished_at: str | None = None
    status: str
    error: str | None = None
    failed_stage: str | None = None
    ingestion: str
    source: str
    agents: dict[str, dict[str, Any]]
    summary: dict[str, Any] | None = None
    token_usage: dict[str, Any] | None = None


class RunListResponse(BaseModel):
    runs: list[RunResponse]


class OutputIndexResponse(BaseModel):
    files: list[str]
    agents: dict[str, str]
    artifacts: list[str]

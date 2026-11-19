import json
from pathlib import Path
from queue import Empty

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from api.schemas.runs import OutputIndexResponse, RunListResponse, RunResponse
from api.services.runner import AGENT_FILES, manager

router = APIRouter()
ALLOWED_EXTENSIONS = {".pdf", ".docx"}


@router.get("/runs", response_model=RunListResponse)
def list_runs() -> dict:
    return {"runs": manager.list_runs()}


@router.post("/runs", response_model=RunResponse, status_code=202)
async def create_run(file: UploadFile = File(...)) -> dict:
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Upload a PDF or DOCX specification.")
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    return manager.create_run(filename, payload)


@router.get("/runs/{run_id}", response_model=RunResponse)
def get_run(run_id: str) -> dict:
    try:
        metadata = manager.get_run(run_id)
    except KeyError:
        metadata = None
    if metadata is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return metadata


@router.get("/runs/{run_id}/events")
def run_events(run_id: str) -> StreamingResponse:
    try:
        subscriber = manager.subscribe(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found.") from None

    def stream():
        try:
            while True:
                try:
                    event = subscriber.get(timeout=15)
                except Empty:
                    yield ": heartbeat\n\n"
                    continue
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                metadata = event.get("metadata", {})
                if metadata.get("status") in {"completed", "failed"}:
                    return
        finally:
            manager.unsubscribe(run_id, subscriber)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/runs/{run_id}/outputs", response_model=OutputIndexResponse)
def list_outputs(run_id: str) -> dict:
    try:
        return manager.output_index(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found.") from None


@router.get("/runs/{run_id}/outputs/{agent_id}")
def get_agent_output(run_id: str, agent_id: str) -> FileResponse:
    filename = AGENT_FILES.get(agent_id)
    if filename is None:
        raise HTTPException(status_code=404, detail="Unknown output agent.")
    try:
        path = manager.output_file(run_id, filename)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found.") from None
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Output is not available yet.") from None
    return FileResponse(path, media_type="application/json", filename=filename)


@router.get("/runs/{run_id}/download/{filename}")
def download_output(run_id: str, filename: str) -> FileResponse:
    try:
        path = manager.output_file(run_id, filename)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found.") from None
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Output is not available.") from None
    return FileResponse(path, filename=filename)

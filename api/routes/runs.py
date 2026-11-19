import asyncio
import json
import queue

from fastapi import APIRouter, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse

from api.schemas.runs import (
    CreateRunResponse,
    OutputIndex,
    RunListResponse,
    RunMetadata,
)
from api.services.auth import get_current_user_from_header
from api.services.runner import AGENT_FILES, manager

router = APIRouter(prefix="/runs", tags=["runs"])

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
ALLOWED_SUFFIXES = {".pdf", ".docx"}


def _extract_user_id(authorization: str | None) -> str | None:
    if not authorization:
        return None
    user = get_current_user_from_header(authorization)
    return user["sub"] if user else None


def _require_run(run_id: str, user_id: str | None = None) -> dict:
    try:
        metadata = manager.get_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found.") from None
    if metadata is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    run_owner = metadata.get("user_id")
    # If run has an assigned user_id and caller is not that user, block access
    if run_owner and user_id and run_owner != user_id:
        raise HTTPException(status_code=403, detail="Access denied to this run.")
    return metadata


@router.get("", response_model=RunListResponse)
def list_runs(authorization: str | None = Header(None)) -> dict:
    user_id = _extract_user_id(authorization)
    return {"runs": manager.list_runs(user_id=user_id)}


@router.post("", response_model=CreateRunResponse, status_code=201)
async def create_run(
    file: UploadFile,
    authorization: str | None = Header(None),
) -> dict:
    user_id = _extract_user_id(authorization)
    filename = (file.filename or "").strip()
    suffix = "." + filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail="Upload a PDF or DOCX hardware specification.",
        )

    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="The selected file is empty.")
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File exceeds the 20 MB limit.")

    metadata = manager.create_run(filename, payload, user_id=user_id)
    return {"run_id": metadata["run_id"], "status": metadata["status"]}


@router.get("/{run_id}", response_model=RunMetadata)
def get_run(run_id: str, authorization: str | None = Header(None)) -> dict:
    user_id = _extract_user_id(authorization)
    return _require_run(run_id, user_id=user_id)


@router.post("/{run_id}/cancel", response_model=RunMetadata)
def cancel_run(run_id: str, authorization: str | None = Header(None)) -> dict:
    user_id = _extract_user_id(authorization)
    _require_run(run_id, user_id=user_id)
    try:
        return manager.cancel_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found.")


@router.get("/{run_id}/events")
async def run_events(
    run_id: str,
    authorization: str | None = Header(None),
) -> StreamingResponse:
    user_id = _extract_user_id(authorization)
    _require_run(run_id, user_id=user_id)
    try:
        subscriber = manager.subscribe(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found.") from None

    async def stream():
        try:
            while True:
                try:
                    event = await asyncio.to_thread(subscriber.get, True, 15)
                except queue.Empty:
                    yield "data: {\"type\": \"heartbeat\"}\n\n"
                    continue
                yield f"data: {json.dumps(event)}\n\n"
                metadata = event.get("metadata") or {}
                if metadata.get("status") in {"completed", "failed"}:
                    break
        finally:
            manager.unsubscribe(run_id, subscriber)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{run_id}/outputs", response_model=OutputIndex)
def list_outputs(run_id: str, authorization: str | None = Header(None)) -> dict:
    user_id = _extract_user_id(authorization)
    _require_run(run_id, user_id=user_id)
    try:
        return manager.output_index(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found.") from None


@router.get("/{run_id}/outputs/{agent_name}")
def get_agent_output(
    run_id: str,
    agent_name: str,
    authorization: str | None = Header(None),
) -> Response:
    user_id = _extract_user_id(authorization)
    _require_run(run_id, user_id=user_id)
    filename = AGENT_FILES.get(agent_name)
    if filename is None:
        raise HTTPException(status_code=404, detail="Unknown agent.")
    try:
        path = manager.output_file(run_id, filename)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="This agent output is not available yet.",
        ) from None
    return Response(
        content=path.read_bytes(),
        media_type="application/json",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/{run_id}/download/{filename}")
def download_output(
    run_id: str,
    filename: str,
    authorization: str | None = Header(None),
) -> FileResponse:
    user_id = _extract_user_id(authorization)
    _require_run(run_id, user_id=user_id)
    try:
        path = manager.output_file(run_id, filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found.") from None
    media = "application/json" if filename.endswith(".json") else "text/plain"
    return FileResponse(path, filename=filename, media_type=media)

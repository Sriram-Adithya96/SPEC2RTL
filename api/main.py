import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

from api.routes.runs import router as runs_router
from api.routes.auth import router as auth_router
from api.schemas.runs import HealthResponse
from api.services.runner import get_agent_model
from src.pipeline import AGENT_ORDER

app = FastAPI(title="SPEC2RTL", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://spec2rtl.vercel.app",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(runs_router, prefix="/api")
app.include_router(auth_router, prefix="/api")


@app.get("/health", response_model=HealthResponse)
@app.get("/api/health", response_model=HealthResponse)
def health() -> dict:
    return {"status": "ok"}


@app.get("/config/models")
@app.get("/api/config/models")
def config_models() -> dict:
    mode = os.getenv("SPEC2RTL_MODE", "free").strip().lower()
    return {
        "mode": mode,
        "agents": {name: get_agent_model(name) for name in AGENT_ORDER},
    }

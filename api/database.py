"""MongoDB database connection and collection accessors."""

import os
from typing import Any
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

_client: MongoClient | None = None
_db: Database | None = None
_last_error: str | None = None

DB_NAME = "spec2rtl"


def get_connection_error() -> str | None:
    return _last_error


def get_db() -> Database | None:
    """Return the active MongoDB database instance, or None if not configured."""
    global _client, _db, _last_error
    if _db is not None:
        return _db

    uri = os.getenv("MONGODB_URI", "").strip().strip("'\"")
    if not uri:
        _last_error = "MONGODB_URI environment variable is not set."
        return None

    try:
        _client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        # Verify connection
        _client.admin.command("ping")
        _db = _client[DB_NAME]
        _last_error = None
        return _db
    except Exception as exc:
        _last_error = f"{type(exc).__name__}: {exc}"
        print(f"[MongoDB Warning] Could not connect to MongoDB: {_last_error}")
        _client = None
        _db = None
        return None


def get_users_collection() -> Collection | None:
    db = get_db()
    if db is not None:
        col = db["users"]
        # Ensure email index is unique
        try:
            col.create_index("email", unique=True)
        except Exception:
            pass
        return col
    return None


def get_runs_collection() -> Collection | None:
    db = get_db()
    if db is not None:
        col = db["runs"]
        try:
            col.create_index("run_id", unique=True)
            col.create_index("user_id")
        except Exception:
            pass
        return col
    return None


def get_artifacts_collection() -> Collection | None:
    db = get_db()
    if db is not None:
        col = db["run_artifacts"]
        try:
            col.create_index([("run_id", 1), ("filename", 1)], unique=True)
        except Exception:
            pass
        return col
    return None

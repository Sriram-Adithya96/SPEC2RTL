"""MongoDB database connection and collection accessors."""

import os
from typing import Any
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

_client: MongoClient | None = None
_db: Database | None = None

DB_NAME = "spec2rtl"


def get_db() -> Database | None:
    """Return the active MongoDB database instance, or None if not configured."""
    global _client, _db
    if _db is not None:
        return _db

    uri = os.getenv("MONGODB_URI", "").strip()
    if not uri:
        return None

    try:
        _client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        # Verify connection
        _client.admin.command("ping")
        _db = _client[DB_NAME]
        return _db
    except Exception as exc:
        print(f"[MongoDB Warning] Could not connect to MongoDB: {exc}")
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

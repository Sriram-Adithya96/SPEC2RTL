import uuid
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, HTTPException, status, Header

from api.database import get_users_collection
from api.schemas.auth import TokenResponse, UserLogin, UserRegister, UserResponse
from api.services.auth import (
    create_access_token,
    decode_access_token,
    get_current_user_from_header,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_to_response(doc: dict) -> UserResponse:
    return UserResponse(
        id=str(doc.get("_id", doc.get("id", ""))),
        email=doc["email"],
        username=doc.get("username", doc["email"].split("@")[0]),
        created_at=doc.get("created_at", datetime.now(timezone.utc).isoformat()),
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: UserRegister) -> dict:
    users = get_users_collection()
    if users is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is not configured or unavailable.",
        )

    email = payload.email.strip().lower()
    if "@" not in email or "." not in email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a valid email address.",
        )
    existing = users.find_one({"email": email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )

    now = datetime.now(timezone.utc).isoformat()
    user_doc = {
        "email": email,
        "username": payload.username.strip(),
        "password_hash": hash_password(payload.password),
        "created_at": now,
    }
    result = users.insert_one(user_doc)
    user_id = str(result.inserted_id)
    user_doc["_id"] = user_id

    token = create_access_token(user_id, email, user_doc["username"])
    return {
        "token": token,
        "user": _user_to_response(user_doc),
    }


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin) -> dict:
    users = get_users_collection()
    if users is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is not configured or unavailable.",
        )

    email = payload.email.strip().lower()
    user_doc = users.find_one({"email": email})
    if not user_doc or not verify_password(payload.password, user_doc.get("password_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    user_id = str(user_doc["_id"])
    token = create_access_token(user_id, email, user_doc.get("username", email))
    return {
        "token": token,
        "user": _user_to_response(user_doc),
    }


@router.get("/me", response_model=UserResponse)
def get_me(authorization: str | None = Header(None)) -> UserResponse:
    payload = get_current_user_from_header(authorization)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated or token has expired.",
        )

    users = get_users_collection()
    if users is not None:
        try:
            user_doc = users.find_one({"_id": ObjectId(payload["sub"])})
            if user_doc:
                return _user_to_response(user_doc)
        except Exception:
            pass

    return UserResponse(
        id=payload["sub"],
        email=payload.get("email", ""),
        username=payload.get("username", ""),
        created_at=datetime.now(timezone.utc).isoformat(),
    )

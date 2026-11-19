from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.core.db import get_db
from app.core.deps import CurrentUser, get_current_user
from app.core.security import decode_token, hash_password, make_token, verify_password
from app.models.schemas import Credentials, RefreshIn, TokenPair

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _tokens(user_id: str) -> TokenPair:
    return TokenPair(
        access_token=make_token(user_id, "access"),
        refresh_token=make_token(user_id, "refresh"),
    )


@router.post("/register", response_model=TokenPair, status_code=201)
async def register(body: Credentials):
    email = body.email.lower()
    role = "admin" if settings.admin_email and email == settings.admin_email.lower() else "user"
    try:
        res = await get_db().users.insert_one(
            {"email": email, "password_hash": hash_password(body.password), "role": role}
        )
    except DuplicateKeyError:
        raise HTTPException(409, "That email is already registered")
    return _tokens(str(res.inserted_id))


@router.post("/login", response_model=TokenPair)
async def login(body: Credentials):
    user = await get_db().users.find_one({"email": body.email.lower()})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Wrong email or password")
    return _tokens(str(user["_id"]))


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshIn):
    uid = decode_token(body.refresh_token, "refresh")
    if uid is None or not ObjectId.is_valid(uid):
        raise HTTPException(401, "Session expired, sign in again")
    if not await get_db().users.find_one({"_id": ObjectId(uid)}, {"_id": 1}):
        raise HTTPException(401, "User no longer exists")
    return _tokens(uid)


@router.get("/me")
async def me(user: CurrentUser = Depends(get_current_user)):
    return user

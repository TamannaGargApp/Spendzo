from bson import ObjectId
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.core.db import get_db
from app.core.security import decode_token

bearer = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    id: str
    email: str
    role: str = "user"


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> CurrentUser:
    if creds is None:
        raise HTTPException(401, "Not authenticated")
    uid = decode_token(creds.credentials, "access")
    if uid is None or not ObjectId.is_valid(uid):
        raise HTTPException(401, "Invalid or expired token")
    doc = await get_db().users.find_one({"_id": ObjectId(uid)})
    if doc is None:
        raise HTTPException(401, "User no longer exists")
    return CurrentUser(id=str(doc["_id"]), email=doc["email"], role=doc.get("role", "user"))


async def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "admin":
        raise HTTPException(403, "Admin only")
    return user


def owner_filter(
    user: CurrentUser, *, all_accounts: bool = False, owner_id: str | None = None
) -> dict:
    """The single place that decides which records a request may touch.

    Normal routes always get {"owner_id": me}. Only admin routes (later) pass
    all_accounts=True, and only a real admin is allowed to widen the scope.
    """
    if all_accounts and user.role == "admin":
        return {"owner_id": owner_id} if owner_id else {}
    return {"owner_id": user.id}

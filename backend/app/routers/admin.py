"""Admin scope (stub). Everything here is already protected by require_admin.

To build admin features later, call the same repositories with
owner_filter(user, all_accounts=True[, owner_id=...]) - no other code changes.
"""
from fastapi import APIRouter, Depends

from app.core.db import get_db
from app.core.deps import CurrentUser, require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users")
async def list_users(_: CurrentUser = Depends(require_admin)):
    users = await get_db().users.find({}, {"password_hash": 0}).to_list()
    return [{"id": str(u["_id"]), "email": u["email"], "role": u.get("role", "user")} for u in users]

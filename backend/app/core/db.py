from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException
from pymongo import ASCENDING, DESCENDING, AsyncMongoClient

from app.core.config import settings

_client: AsyncMongoClient | None = None


def get_db():
    assert _client is not None, "database not connected"
    return _client[settings.mongo_db]


async def connect() -> None:
    global _client
    _client = AsyncMongoClient(settings.mongo_url)
    db = get_db()
    await db.users.create_index("email", unique=True)
    await db.expenses.create_index([("owner_id", ASCENDING), ("date", DESCENDING)])
    await db.expenses.create_index([("owner_id", ASCENDING), ("category", ASCENDING)])
    await db.bills.create_index([("owner_id", ASCENDING), ("expense_id", ASCENDING)])


async def close() -> None:
    if _client is not None:
        await _client.close()


def oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise HTTPException(404, "Not found")


def public(doc: dict | None) -> dict | None:
    """Mongo document -> JSON-friendly dict (string id, rupees next to paise)."""
    if doc is None:
        return None
    d = dict(doc)
    d["id"] = str(d.pop("_id"))
    if "amount_paise" in d:
        d["amount"] = d["amount_paise"] / 100
    if d.get("expense_id") is not None:
        d["expense_id"] = str(d["expense_id"])
    return d

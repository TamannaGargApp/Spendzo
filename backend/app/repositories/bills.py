from datetime import datetime, timezone

from bson import ObjectId

from app.core.db import get_db, oid


def _col():
    return get_db().bills


async def create(owner_id: str, expense_id: str | None, meta: dict) -> dict:
    doc = {
        "owner_id": owner_id,
        "expense_id": ObjectId(expense_id) if expense_id else None,
        **meta,
        "uploaded_at": datetime.now(timezone.utc),
    }
    res = await _col().insert_one(doc)
    doc["_id"] = res.inserted_id
    return doc


async def list_(flt: dict, expense_ids: list[ObjectId] | None = None) -> list[dict]:
    q = dict(flt)
    if expense_ids is not None:
        q["expense_id"] = {"$in": expense_ids}
    return await _col().find(q).sort("uploaded_at", -1).to_list()


async def get(flt: dict, bill_id: str) -> dict | None:
    return await _col().find_one({**flt, "_id": oid(bill_id)})


async def delete(flt: dict, bill_id: str) -> dict | None:
    return await _col().find_one_and_delete({**flt, "_id": oid(bill_id)})

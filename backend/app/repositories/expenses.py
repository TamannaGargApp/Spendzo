"""All expense queries. Every function takes `flt` (from owner_filter) so a
query can never run without an ownership scope."""
import re
from datetime import datetime, timezone

from app.core.db import get_db, oid


def _col():
    return get_db().expenses


def _query(flt: dict, date_from=None, date_to=None, category=None, search=None) -> dict:
    q: dict = {**flt, "deleted_at": None}
    if date_from or date_to:
        q["date"] = {}
        if date_from:
            q["date"]["$gte"] = date_from
        if date_to:
            q["date"]["$lte"] = date_to
    if category:
        q["category"] = {"$regex": f"^{re.escape(category)}$", "$options": "i"}
    if search:
        q["$or"] = [
            {"description": {"$regex": re.escape(search), "$options": "i"}},
            {"tags": {"$regex": re.escape(search), "$options": "i"}},
        ]
    return q


def _now():
    return datetime.now(timezone.utc)


async def create(owner_id: str, data: dict) -> dict:
    doc = {
        "owner_id": owner_id,
        **data,
        "bill_ids": [],
        "created_at": _now(),
        "updated_at": _now(),
        "deleted_at": None,
    }
    res = await _col().insert_one(doc)
    doc["_id"] = res.inserted_id
    return doc


async def get(flt: dict, expense_id: str) -> dict | None:
    return await _col().find_one({**flt, "_id": oid(expense_id), "deleted_at": None})


async def list_(flt: dict, *, skip=0, limit=20, **filters) -> tuple[list[dict], int]:
    q = _query(flt, **filters)
    total = await _col().count_documents(q)
    cur = _col().find(q).sort([("date", -1), ("_id", -1)]).skip(skip).limit(limit)
    return await cur.to_list(), total


async def update(flt: dict, expense_id: str, data: dict) -> dict | None:
    return await _col().find_one_and_update(
        {**flt, "_id": oid(expense_id), "deleted_at": None},
        {"$set": {**data, "updated_at": _now()}},
        return_document=True,
    )


async def soft_delete(flt: dict, expense_id: str) -> bool:
    res = await _col().update_one(
        {**flt, "_id": oid(expense_id), "deleted_at": None},
        {"$set": {"deleted_at": _now()}},
    )
    return res.modified_count == 1


async def categories(flt: dict) -> list[str]:
    return sorted(await _col().distinct("category", {**flt, "deleted_at": None}))


async def summary(
    flt: dict, *, group_by="category", date_from=None, date_to=None, category=None
) -> dict:
    """Totals in rupees plus a breakdown by category, month (YYYY-MM) or day."""
    q = _query(flt, date_from, date_to, category)
    key = "$category" if group_by == "category" else {
        "$substrBytes": ["$date", 0, 7 if group_by == "month" else 10]
    }
    pipeline = [
        {"$match": q},
        {"$group": {"_id": key, "total": {"$sum": "$amount_paise"}, "count": {"$sum": 1}}},
        {"$sort": {"total": -1} if group_by == "category" else {"_id": 1}},
    ]
    cur = await _col().aggregate(pipeline)
    groups = [
        {"key": g["_id"], "total": g["total"] / 100, "count": g["count"]}
        for g in await cur.to_list()
    ]
    return {
        "total": sum(g["total"] for g in groups),
        "count": sum(g["count"] for g in groups),
        "groups": groups,
    }

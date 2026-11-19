"""Ledger assistant: Ollama (qwen3:4b) + a fixed whitelist of read-only tools.

Safety comes from code, not the prompt:
  * the model never writes queries, it only picks a tool and arguments
  * every argument is validated by Pydantic
  * owner_id comes from the logged-in user, the model cannot set or see it
  * if the model answers without calling a tool, the answer is discarded
"""
import json
import re
from datetime import date

from ollama import AsyncClient
from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings
from app.core.deps import CurrentUser, owner_filter
from app.models.schemas import ChatTurn
from app.repositories import bills as bills_repo
from app.repositories import expenses as repo

REFUSAL = (
    "I can only answer questions about your expense data. "
    "Try: \"How much did I spend on food this month?\""
)

SYSTEM = """You are the assistant inside a personal expense ledger. Today is {today}. Currency is Indian rupees.
Rules:
- Answer only about the user's own expenses and bills, using tool results only.
- Always call a tool to get data. Never guess or compute numbers yourself.
- Turn relative dates (this month, last week, yesterday) into YYYY-MM-DD using today's date.
- If the question is not about the ledger data, do not call any tool and reply with: {refusal}
- Keep answers short. Write amounts like ₹1,250.00."""

DATE = r"^\d{4}-\d{2}-\d{2}$"


class RangeArgs(BaseModel):
    date_from: str | None = Field(None, pattern=DATE)
    date_to: str | None = Field(None, pattern=DATE)
    category: str | None = None


class ListArgs(RangeArgs):
    search: str | None = None
    limit: int = Field(10, ge=1, le=25)


class TopArgs(RangeArgs):
    limit: int = Field(5, ge=1, le=10)


class MonthArgs(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")


class BillArgs(BaseModel):
    search: str | None = None
    date_from: str | None = Field(None, pattern=DATE)
    date_to: str | None = Field(None, pattern=DATE)


def _fn(name: str, desc: str, props: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required or []},
        },
    }


_D = {"type": "string", "description": "YYYY-MM-DD"}
_CAT = {"type": "string", "description": "category name, e.g. Food"}
_SEARCH = {"type": "string", "description": "word to match in the description or tags"}

TOOLS = [
    _fn("total_spent", "Total amount spent and number of expenses, optionally for a date range and category.",
        {"date_from": _D, "date_to": _D, "category": _CAT}),
    _fn("list_expenses", "List individual expenses, newest first, with optional filters.",
        {"date_from": _D, "date_to": _D, "category": _CAT, "search": _SEARCH,
         "limit": {"type": "integer", "description": "max rows, default 10"}}),
    _fn("top_categories", "Categories ranked by spending, highest first.",
        {"date_from": _D, "date_to": _D, "limit": {"type": "integer"}}),
    _fn("monthly_summary", "Total and per-category breakdown for one month.",
        {"month": {"type": "string", "description": "YYYY-MM"}}, ["month"]),
    _fn("find_bills", "List uploaded bills, optionally only those attached to expenses matching a search or date range.",
        {"search": _SEARCH, "date_from": _D, "date_to": _D}),
]


async def _run_tool(name: str, raw: dict, user: CurrentUser) -> dict:
    flt = owner_filter(user)  # injected here, never by the model
    try:
        if name == "total_spent":
            a = RangeArgs(**raw)
            s = await repo.summary(flt, date_from=a.date_from, date_to=a.date_to, category=a.category)
            return {"total_inr": s["total"], "expense_count": s["count"]}

        if name == "list_expenses":
            a = ListArgs(**raw)
            rows, total = await repo.list_(
                flt, limit=a.limit, date_from=a.date_from, date_to=a.date_to,
                category=a.category, search=a.search,
            )
            return {
                "matching_count": total,
                "expenses": [
                    {"date": r["date"], "amount_inr": r["amount_paise"] / 100,
                     "category": r["category"], "description": r["description"],
                     "bills_attached": len(r.get("bill_ids", []))}
                    for r in rows
                ],
            }

        if name == "top_categories":
            a = TopArgs(**raw)
            s = await repo.summary(flt, date_from=a.date_from, date_to=a.date_to)
            return {"total_inr": s["total"], "categories": [
                {"category": g["key"], "total_inr": g["total"], "count": g["count"]}
                for g in s["groups"][: a.limit]]}

        if name == "monthly_summary":
            a = MonthArgs(**raw)
            s = await repo.summary(flt, date_from=f"{a.month}-01", date_to=f"{a.month}-31")
            return {"month": a.month, "total_inr": s["total"], "expense_count": s["count"],
                    "by_category": [{"category": g["key"], "total_inr": g["total"]} for g in s["groups"]]}

        if name == "find_bills":
            a = BillArgs(**raw)
            ids = None
            if a.search or a.date_from or a.date_to:
                rows, _ = await repo.list_(flt, limit=100, date_from=a.date_from,
                                           date_to=a.date_to, search=a.search)
                ids = [r["_id"] for r in rows]
            bills = await bills_repo.list_(flt, ids)
            by_id = {}
            if bills:
                exp_ids = [b["expense_id"] for b in bills if b.get("expense_id")]
                rows, _ = await repo.list_(flt, limit=100)
                by_id = {r["_id"]: r for r in rows if r["_id"] in exp_ids}
            return {"bill_count": len(bills), "bills": [
                {"filename": b["filename"],
                 "expense_date": by_id.get(b.get("expense_id"), {}).get("date"),
                 "expense_description": by_id.get(b.get("expense_id"), {}).get("description")}
                for b in bills[:25]]}
    except ValidationError as e:
        return {"error": f"Invalid arguments: {e.errors()[0]['msg']}"}
    return {"error": f"Unknown tool {name}"}


_client = AsyncClient(host=settings.ollama_host)


def _clean(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()


async def answer(user: CurrentUser, question: str, history: list[ChatTurn]) -> str:
    messages: list = [
        {"role": "system", "content": SYSTEM.format(today=date.today().isoformat(), refusal=REFUSAL)}
    ]
    for turn in history[-6:]:
        if turn.role in ("user", "assistant"):
            messages.append({"role": turn.role, "content": turn.content})
    messages.append({"role": "user", "content": question})

    used_tool = False
    for _ in range(4):
        resp = await _client.chat(
            model=settings.ollama_model,
            messages=messages,
            tools=TOOLS,
            think=False,
            options={"temperature": 0.1},
        )
        msg = resp.message
        if not msg.tool_calls:
            # No tool used = not grounded in the database, so we do not trust it.
            return (_clean(msg.content) or REFUSAL) if used_tool else REFUSAL
        used_tool = True
        messages.append(msg)
        for call in msg.tool_calls:
            result = await _run_tool(call.function.name, dict(call.function.arguments or {}), user)
            messages.append(
                {"role": "tool", "tool_name": call.function.name, "content": json.dumps(result)}
            )
    return "I could not finish that. Try a more specific question."

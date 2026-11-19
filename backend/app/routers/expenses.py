from datetime import date as Date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.db import public
from app.core.deps import CurrentUser, get_current_user, owner_filter
from app.models.schemas import ExpenseIn
from app.repositories import expenses as repo
from app.routers.bills import delete_bills_of_expense

router = APIRouter(prefix="/api/expenses", tags=["expenses"])


def _doc(body: ExpenseIn) -> dict:
    return {
        "date": body.date.isoformat(),
        "amount_paise": int((body.amount * 100).to_integral_value()),
        "category": body.category,
        "description": body.description,
        "tags": body.tags,
    }


def _iso(d: Date | None) -> str | None:
    return d.isoformat() if d else None


@router.get("/summary")
async def summary(
    group_by: str = Query("category", pattern="^(category|month|day)$"),
    date_from: Date | None = None,
    date_to: Date | None = None,
    category: str | None = None,
    user: CurrentUser = Depends(get_current_user),
):
    return await repo.summary(
        owner_filter(user),
        group_by=group_by,
        date_from=_iso(date_from),
        date_to=_iso(date_to),
        category=category,
    )


@router.get("/categories")
async def categories(user: CurrentUser = Depends(get_current_user)):
    return await repo.categories(owner_filter(user))


@router.get("")
async def list_expenses(
    date_from: Date | None = None,
    date_to: Date | None = None,
    category: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(15, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
):
    items, total = await repo.list_(
        owner_filter(user),
        skip=(page - 1) * page_size,
        limit=page_size,
        date_from=_iso(date_from),
        date_to=_iso(date_to),
        category=category,
        search=search,
    )
    return {"items": [public(i) for i in items], "total": total, "page": page, "page_size": page_size}


@router.post("", status_code=201)
async def create_expense(body: ExpenseIn, user: CurrentUser = Depends(get_current_user)):
    return public(await repo.create(user.id, _doc(body)))


@router.get("/{expense_id}")
async def get_expense(expense_id: str, user: CurrentUser = Depends(get_current_user)):
    doc = await repo.get(owner_filter(user), expense_id)
    if not doc:
        raise HTTPException(404, "Expense not found")
    return public(doc)


@router.put("/{expense_id}")
async def update_expense(
    expense_id: str, body: ExpenseIn, user: CurrentUser = Depends(get_current_user)
):
    doc = await repo.update(owner_filter(user), expense_id, _doc(body))
    if not doc:
        raise HTTPException(404, "Expense not found")
    return public(doc)


@router.delete("/{expense_id}", status_code=204)
async def delete_expense(expense_id: str, user: CurrentUser = Depends(get_current_user)):
    flt = owner_filter(user)
    if not await repo.soft_delete(flt, expense_id):
        raise HTTPException(404, "Expense not found")
    await delete_bills_of_expense(flt, expense_id)

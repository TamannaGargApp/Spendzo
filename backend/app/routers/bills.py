import io
import zipfile
from pathlib import Path

from bson import ObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.db import get_db, oid, public
from app.core.deps import CurrentUser, get_current_user, owner_filter
from app.repositories import bills as repo
from app.repositories import expenses as expenses_repo
from app.services.storage import storage

router = APIRouter(prefix="/api/bills", tags=["bills"])

MIME = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".doc": "application/msword",
    ".xls": "application/vnd.ms-excel",
}
OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # legacy .doc / .xls container


def _sniff(data: bytes, filename: str) -> str | None:
    """Work out the real file type from its bytes (never trust the filename alone)."""
    if data.startswith(b"%PDF"):
        return ".pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"PK\x03\x04"):  # modern Office files are zip archives
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                names = z.namelist()
        except zipfile.BadZipFile:
            return None
        if any(n.lower().endswith("vbaproject.bin") for n in names):
            return None  # macro-enabled documents are refused
        if "word/document.xml" in names:
            return ".docx"
        if "xl/workbook.xml" in names:
            return ".xlsx"
        return None
    if data.startswith(OLE):
        ext = Path(filename or "").suffix.lower()
        return ext if ext in (".doc", ".xls") else None
    return None


async def delete_bills_of_expense(flt: dict, expense_id: str) -> None:
    for b in await repo.list_(flt, [ObjectId(expense_id)]):
        storage.delete(b["storage_key"])
        await repo.delete(flt, str(b["_id"]))


@router.post("", status_code=201)
async def upload_bill(
    file: UploadFile = File(...),
    expense_id: str | None = Form(None),
    user: CurrentUser = Depends(get_current_user),
):
    flt = owner_filter(user)
    if expense_id and not await expenses_repo.get(flt, expense_id):
        raise HTTPException(404, "Expense not found")

    limit = settings.max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"File is larger than {settings.max_upload_mb} MB")
    ext = _sniff(data, file.filename or "")
    if not ext:
        raise HTTPException(415, "Only PDF, Word, Excel, JPG or PNG files are accepted")
    ctype = MIME[ext]

    key = storage.save(user.id, data, ext)
    bill = await repo.create(
        user.id,
        expense_id,
        {
            "filename": (file.filename or f"bill{ext}")[:120],
            "content_type": ctype,
            "size": len(data),
            "storage_key": key,
        },
    )
    if expense_id:
        await get_db().expenses.update_one(
            {**flt, "_id": oid(expense_id)}, {"$addToSet": {"bill_ids": str(bill["_id"])}}
        )
    return public(bill)


@router.get("")
async def list_bills(expense_id: str | None = None, user: CurrentUser = Depends(get_current_user)):
    ids = [oid(expense_id)] if expense_id else None
    return [public(b) for b in await repo.list_(owner_filter(user), ids)]


@router.get("/{bill_id}/download")
async def download_bill(bill_id: str, user: CurrentUser = Depends(get_current_user)):
    bill = await repo.get(owner_filter(user), bill_id)
    if not bill:
        raise HTTPException(404, "Bill not found")
    return FileResponse(
        storage.path(bill["storage_key"]),
        media_type=bill["content_type"],
        filename=bill["filename"],
        # only PDFs and images open in the browser; Office files are downloaded
        content_disposition_type=(
            "inline"
            if bill["content_type"] == "application/pdf" or bill["content_type"].startswith("image/")
            else "attachment"
        ),
    )


@router.delete("/{bill_id}", status_code=204)
async def delete_bill(bill_id: str, user: CurrentUser = Depends(get_current_user)):
    flt = owner_filter(user)
    bill = await repo.delete(flt, bill_id)
    if not bill:
        raise HTTPException(404, "Bill not found")
    storage.delete(bill["storage_key"])
    if bill.get("expense_id"):
        await get_db().expenses.update_one(
            {**flt, "_id": bill["expense_id"]}, {"$pull": {"bill_ids": str(bill["_id"])}}
        )

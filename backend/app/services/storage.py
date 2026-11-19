from pathlib import Path
from uuid import uuid4

from app.core.config import settings


class LocalStorage:
    """Swap this class for S3/MinIO later; routers only use save/path/delete."""

    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, owner_id: str, data: bytes, ext: str) -> str:
        key = f"{owner_id}/{uuid4().hex}{ext}"
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if not p.is_relative_to(self.root):
            raise ValueError("bad storage key")
        return p

    def delete(self, key: str) -> None:
        self.path(key).unlink(missing_ok=True)


storage = LocalStorage(settings.upload_dir)

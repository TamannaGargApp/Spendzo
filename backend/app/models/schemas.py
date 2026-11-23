from datetime import date as Date
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models.constants import CATEGORIES


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RefreshIn(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class ExpenseIn(BaseModel):
    date: Date
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    category: str = Field(min_length=1, max_length=50)
    subcategory: str | None = Field(None, max_length=50)
    start_use_date: Date | None = None
    finished_on: Date | None = None
    description: str = Field("", max_length=300)
    tags: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("category")
    @classmethod
    def clean_category(cls, v: str) -> str:
        wanted = v.strip().lower()
        for c in CATEGORIES:
            if c.lower() == wanted:
                return c
        raise ValueError("category must be one of: " + ", ".join(CATEGORIES))

    @field_validator("subcategory")
    @classmethod
    def clean_subcategory(cls, v: str | None) -> str | None:
        return (v or "").strip() or None

    @model_validator(mode="after")
    def check_usage_dates(self):
        if self.start_use_date and self.finished_on and self.finished_on < self.start_use_date:
            raise ValueError("Finished date cannot be before the start use date")
        return self

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, v: list[str]) -> list[str]:
        return [t.strip()[:30] for t in v if t.strip()]


class ChatTurn(BaseModel):
    role: str
    content: str = Field(max_length=2000)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    history: list[ChatTurn] = Field(default_factory=list, max_length=10)

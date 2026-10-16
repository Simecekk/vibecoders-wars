"""Input validation area: a user signup API that rejects bad input before it reaches any logic.

Shows the three places FastAPI validates input with Pydantic:
- the request body (`SignupRequest` with field constraints and validators),
- path parameters (`Path(pattern=...)`),
- query parameters (`Query(ge=..., le=...)`).
Invalid input never reaches the function body: FastAPI answers 422 with the reason.
"""

from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import BaseModel, Field, field_validator, model_validator

router = APIRouter()

USERNAME_PATTERN = r"^[a-z0-9_]{3,20}$"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.IGNORECASE)

_USERS: dict[str, UserOut] = {}


class SignupRequest(BaseModel):
    username: str = Field(pattern=USERNAME_PATTERN, description="3-20 chars: lowercase letters, digits, underscore")
    email: str = Field(max_length=254)
    age: int = Field(ge=13, le=120)
    password: str = Field(min_length=8, max_length=128)
    password_confirm: str

    @field_validator("email")
    @classmethod
    def email_looks_valid(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_RE.match(value):
            raise ValueError("email must look like name@example.com")
        return value

    @field_validator("password")
    @classmethod
    def password_is_strong(cls, value: str) -> str:
        if not any(ch.isdigit() for ch in value) or not any(ch.isalpha() for ch in value):
            raise ValueError("password must contain at least one letter and one digit")
        return value

    @model_validator(mode="after")
    def passwords_match(self) -> SignupRequest:
        if self.password != self.password_confirm:
            raise ValueError("passwords do not match")
        return self


class UserOut(BaseModel):
    """What the API returns: never the password."""

    username: str
    email: str
    age: int


@router.post("/users", status_code=status.HTTP_201_CREATED, response_model=UserOut)
def signup(body: SignupRequest) -> UserOut:
    if body.username in _USERS:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")
    user = UserOut(username=body.username, email=body.email, age=body.age)
    _USERS[user.username] = user
    return user


@router.get("/users/{username}", response_model=UserOut)
def get_user(username: Annotated[str, Path(pattern=USERNAME_PATTERN)]) -> UserOut:
    if username not in _USERS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _USERS[username]


@router.get("/users", response_model=list[UserOut])
def list_users(
    min_age: Annotated[int, Query(ge=13, le=120)] = 13,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[UserOut]:
    return [u for u in _USERS.values() if u.age >= min_age][:limit]

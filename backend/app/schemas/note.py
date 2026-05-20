"""Pydantic schemas for the Note resource.

Three schemas per resource — Create (POST body), Update (PATCH body,
all fields optional), Response (everything the client sees). Splitting
them keeps the API contract from accidentally accepting `id` or
`created_at` in a POST body later.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1)


class NoteUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    body: str | None = Field(default=None, min_length=1)


class NoteResponse(BaseModel):
    id: str
    user_id: str
    title: str
    body: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

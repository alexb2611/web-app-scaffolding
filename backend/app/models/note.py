"""SQLAlchemy Note model.

A user-owned, auth-protected text resource. Serves as the canonical
example of "add a CRUD feature" in `docs/adding-a-feature.md` — the
shape (UUID-string PK, user FK with CASCADE delete, indexed FK,
Python-side timestamp defaults) is what new features should imitate.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # CASCADE so deleting a user takes their notes with them. The index
    # is required — every read query filters by user_id and the planner
    # won't add the index for us.
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

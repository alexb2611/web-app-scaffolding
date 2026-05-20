"""Note service — data-access layer.

Authorization is **baked into the query**, not added as a separate
check after-the-fact. `get_note_for_user(note_id=..., user_id=...)`
returns None whether the note doesn't exist or belongs to someone
else — the route then 404s in both cases without leaking existence
via a 403/404 distinction.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.note import Note
from app.schemas.note import NoteCreate, NoteUpdate


async def create_note(db: AsyncSession, *, user_id: str, data: NoteCreate) -> Note:
    note = Note(user_id=user_id, title=data.title, body=data.body)
    db.add(note)
    await db.flush()
    await db.refresh(note)
    return note


async def list_notes_for_user(db: AsyncSession, *, user_id: str) -> list[Note]:
    """Newest first — most-recent-edit feels like the right default for a
    notes-style resource. Switch to alphabetical or pinned-first when the
    real product asks for it."""
    result = await db.execute(
        select(Note).where(Note.user_id == user_id).order_by(Note.created_at.desc())
    )
    return list(result.scalars().all())


async def get_note_for_user(
    db: AsyncSession, *, note_id: str, user_id: str
) -> Note | None:
    """Returns None for both "not found" and "belongs to someone else".
    Callers should 404 either way — the distinction would leak existence."""
    result = await db.execute(
        select(Note).where(Note.id == note_id, Note.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def update_note(db: AsyncSession, *, note: Note, data: NoteUpdate) -> Note:
    if data.title is not None:
        note.title = data.title
    if data.body is not None:
        note.body = data.body
    await db.flush()
    await db.refresh(note)
    return note


async def delete_note(db: AsyncSession, *, note: Note) -> None:
    await db.delete(note)
    await db.flush()

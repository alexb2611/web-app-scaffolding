"""Note CRUD routes — all auth-protected.

Routes follow the recipe convention:
  - `Depends(get_current_user)` for the auth requirement
  - `Depends(get_db)` for the session
  - Thin handlers that delegate to the service layer
  - 404 (never 403) for both missing and unauthorized resources
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.note import NoteCreate, NoteResponse, NoteUpdate
from app.services import note_service

router = APIRouter(prefix="/notes", tags=["notes"])
_log = structlog.get_logger()


@router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    payload: NoteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteResponse:
    note = await note_service.create_note(db, user_id=current_user.id, data=payload)
    _log.info("note.created", note_id=note.id)
    return NoteResponse.model_validate(note)


@router.get("", response_model=list[NoteResponse])
async def list_notes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[NoteResponse]:
    notes = await note_service.list_notes_for_user(db, user_id=current_user.id)
    return [NoteResponse.model_validate(n) for n in notes]


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteResponse:
    note = await note_service.get_note_for_user(
        db, note_id=note_id, user_id=current_user.id
    )
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return NoteResponse.model_validate(note)


@router.patch("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: str,
    payload: NoteUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteResponse:
    note = await note_service.get_note_for_user(
        db, note_id=note_id, user_id=current_user.id
    )
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    updated = await note_service.update_note(db, note=note, data=payload)
    _log.info("note.updated", note_id=note_id)
    return NoteResponse.model_validate(updated)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    note = await note_service.get_note_for_user(
        db, note_id=note_id, user_id=current_user.id
    )
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await note_service.delete_note(db, note=note)
    _log.info("note.deleted", note_id=note_id)

"""
GET    /api/v1/journal          — list the current user's entries
POST   /api/v1/journal          — create an entry
GET    /api/v1/journal/{id}     — read one entry (must be yours)
PUT    /api/v1/journal/{id}     — update one entry (must be yours)
DELETE /api/v1/journal/{id}     — delete one entry (must be yours)

Unlike the profile, journal entries ARE addressed by id in the URL, so
a client *could* put someone else's entry id in the path. This is
exactly where ownership has to be enforced: every single-entry route
loads the row and calls ensure_owner() before doing anything with it.
ensure_owner raises 404 (not 403) for a row that isn't yours, so an
entry belonging to another user is indistinguishable from one that
doesn't exist — no information leaks about other users' data.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import ensure_owner, get_current_user
from app.database.connection import get_db
from app.database.models import JournalEntry, User
from app.schemas.journal_schema import (
    JournalEntryCreate,
    JournalEntryOut,
    JournalEntryUpdate,
)

router = APIRouter(prefix="/journal", tags=["journal"])


def _get_entry_or_404(db: Session, entry_id: int, current_user: User) -> JournalEntry:
    """Load an entry by id, then verify it belongs to the caller.
    Returns the entry or raises 404 — both for 'no such entry' and for
    'exists but not yours', deliberately indistinguishable."""
    entry = db.get(JournalEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found.")
    ensure_owner(entry.user_id, current_user)  # raises 404 if not the owner
    return entry


@router.get("", response_model=list[JournalEntryOut])
def list_my_entries(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[JournalEntry]:
    """Only ever returns the caller's own entries — the query is scoped
    by user_id, so there's no page or filter that could surface another
    user's data."""
    return (
        db.query(JournalEntry)
        .filter(JournalEntry.user_id == current_user.id)
        .order_by(JournalEntry.entry_date.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.post("", response_model=JournalEntryOut, status_code=status.HTTP_201_CREATED)
def create_entry(
    payload: JournalEntryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JournalEntry:
    entry = JournalEntry(
        user_id=current_user.id,
        entry_date=payload.entry_date,
        notes=payload.notes,
        skin_feeling_tags=payload.skin_feeling_tags,
    )
    db.add(entry)
    try:
        db.commit()
    except IntegrityError:
        # The (user_id, entry_date) unique constraint: one entry per day.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a journal entry for that date. Update it instead.",
        )
    db.refresh(entry)
    return entry


@router.get("/{entry_id}", response_model=JournalEntryOut)
def get_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JournalEntry:
    return _get_entry_or_404(db, entry_id, current_user)


@router.put("/{entry_id}", response_model=JournalEntryOut)
def update_entry(
    entry_id: int,
    payload: JournalEntryUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JournalEntry:
    entry = _get_entry_or_404(db, entry_id, current_user)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    entry = _get_entry_or_404(db, entry_id, current_user)
    db.delete(entry)
    db.commit()

"""
POST   /api/v1/routines                  — create a routine (morning/night) with items
GET    /api/v1/routines                  — list your routines
GET    /api/v1/routines/{id}             — one routine with its items
DELETE /api/v1/routines/{id}             — delete a routine
POST   /api/v1/routines/{id}/log         — log completion for one date (upsert)

SCOPE NOTE: the original Phase 7 brief covers "products catalog" and
"reports from logged data." The `routines` / `routine_items` /
`routine_logs` tables already existed (Phase 2) but had NO endpoints —
meaning there was no way for a user to ever create a routine or log a
day as completed. Reports item 3 ("routine completion") is impossible
to build meaningfully without this. This minimal CRUD is added as a
necessary, justified prerequisite — not scope creep for its own sake.

Ownership: routines are addressed by id, so every single-routine route
loads it and calls ensure_owner() first — same pattern as journal.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import ensure_owner, get_current_user
from app.database.connection import get_db
from app.database.models import Routine, RoutineItem, RoutineLog, User
from app.schemas.catalog_schema import (
    RoutineCreate,
    RoutineLogOut,
    RoutineLogRequest,
    RoutineOut,
)

router = APIRouter(prefix="/routines", tags=["routines"])


def _get_owned_routine(db: Session, routine_id: int, user: User) -> Routine:
    routine = db.get(Routine, routine_id)
    if routine is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Routine not found.")
    ensure_owner(routine.user_id, user)
    return routine


@router.post("", response_model=RoutineOut, status_code=status.HTTP_201_CREATED)
def create_routine(
    payload: RoutineCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Routine:
    routine = Routine(user_id=current_user.id, routine_type=payload.routine_type)
    db.add(routine)
    db.flush()  # assign routine.id before attaching items
    for item in payload.items:
        db.add(
            RoutineItem(
                routine_id=routine.id,
                product_id=item.product_id,
                step_order=item.step_order,
                notes=item.notes,
            )
        )
    db.commit()
    db.refresh(routine)
    return routine


@router.get("", response_model=list[RoutineOut])
def list_my_routines(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Routine]:
    return (
        db.query(Routine)
        .filter(Routine.user_id == current_user.id)
        .order_by(Routine.created_at.desc())
        .all()
    )


@router.get("/{routine_id}", response_model=RoutineOut)
def get_routine(
    routine_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Routine:
    return _get_owned_routine(db, routine_id, current_user)


@router.delete("/{routine_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_routine(
    routine_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    routine = _get_owned_routine(db, routine_id, current_user)
    db.delete(routine)  # cascades to items and logs
    db.commit()


@router.post("/{routine_id}/log", response_model=RoutineLogOut)
def log_routine_day(
    routine_id: int,
    payload: RoutineLogRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RoutineLog:
    """Upsert: logging the same routine + date again updates the
    existing row instead of erroring, so a user can correct a mistaken
    log entry without deleting it first."""
    routine = _get_owned_routine(db, routine_id, current_user)

    existing = (
        db.query(RoutineLog)
        .filter(RoutineLog.routine_id == routine.id, RoutineLog.log_date == payload.log_date)
        .first()
    )
    if existing is not None:
        existing.completed = payload.completed
        db.commit()
        db.refresh(existing)
        return existing

    log = RoutineLog(routine_id=routine.id, log_date=payload.log_date, completed=payload.completed)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log

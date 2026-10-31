"""
GET /api/v1/reports/summary?days=30  — the current user's own activity

Per the project brief: "Build reports from logged data only; do not
imply journal tags prove clinical improvement." This endpoint reports
counts and rates of what the user actually logged — it never
interprets, scores, or claims that any pattern means skin is
"improving" or "worsening." The disclaimer field is always present and
always says so.

Scoped entirely to the caller's own data via user_id filters — there is
no id parameter here for another user's data to leak through.
"""
from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.connection import get_db
from app.database.models import JournalEntry, Routine, RoutineLog, User
from app.schemas.catalog_schema import ReportSummary, RoutineCompletionStat

router = APIRouter(prefix="/reports", tags=["reports"])

REPORT_DISCLAIMER = (
    "This report summarizes what you logged — it is not a measure of "
    "clinical improvement or skin health, and no claim is made about "
    "whether your skin is getting better or worse."
)


@router.get("/summary", response_model=ReportSummary)
def get_report_summary(
    days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportSummary:
    since = datetime.date.today() - datetime.timedelta(days=days)

    entries = (
        db.query(JournalEntry)
        .filter(JournalEntry.user_id == current_user.id, JournalEntry.entry_date >= since)
        .all()
    )

    tag_counts: dict[str, int] = {}
    for entry in entries:
        for tag in entry.skin_feeling_tags or []:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    routines = db.query(Routine).filter(Routine.user_id == current_user.id).all()
    completion_stats: list[RoutineCompletionStat] = []
    for routine in routines:
        logs = [log for log in routine.logs if log.log_date >= since]
        days_logged = len(logs)
        days_completed = sum(1 for log in logs if log.completed)
        rate = (days_completed / days_logged) if days_logged else 0.0
        completion_stats.append(
            RoutineCompletionStat(
                routine_id=routine.id,
                routine_type=routine.routine_type,
                days_logged=days_logged,
                days_completed=days_completed,
                completion_rate=round(rate, 4),
            )
        )

    return ReportSummary(
        period_days=days,
        journal_entry_count=len(entries),
        feeling_tag_counts=tag_counts,
        routine_completion=completion_stats,
        disclaimer=REPORT_DISCLAIMER,
    )

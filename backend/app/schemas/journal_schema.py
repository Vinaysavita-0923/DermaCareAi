"""
Request/response shapes for the skin-journal endpoints.

Note on photos: `photo_path` exists on the model but is deliberately
NOT part of any request or response schema in Phase 4. Photo upload
needs private storage, validation, explicit consent, and deletion
controls (project brief), which is its own later piece of work — so
there is no way, through this API, to set or read a photo path yet.
"""
from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict, field_validator

# A small closed vocabulary again — user-selected descriptive tags for
# how skin felt that day, not clinical terms.
ALLOWED_FEELING_TAGS = {
    "calm", "irritated", "dry", "oily", "breakout", "improving", "itchy", "normal",
}


def _clean_notes(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value) > 2000:
        raise ValueError("Notes must be 2000 characters or fewer.")
    return value or None


def _clean_tags(value: list[str] | None) -> list[str] | None:
    if value is None:
        return None
    cleaned = [t.strip().lower() for t in value if t.strip()]
    invalid = [t for t in cleaned if t not in ALLOWED_FEELING_TAGS]
    if invalid:
        raise ValueError(
            f"Unknown tag(s): {invalid}. Allowed values: {sorted(ALLOWED_FEELING_TAGS)}"
        )
    return list(dict.fromkeys(cleaned))


class JournalEntryCreate(BaseModel):
    entry_date: datetime.date
    notes: str | None = None
    skin_feeling_tags: list[str] | None = None

    @field_validator("entry_date")
    @classmethod
    def _not_in_the_future(cls, value: datetime.date) -> datetime.date:
        if value > datetime.date.today():
            raise ValueError("Journal entry date cannot be in the future.")
        return value

    @field_validator("notes")
    @classmethod
    def _v_notes(cls, value: str | None) -> str | None:
        return _clean_notes(value)

    @field_validator("skin_feeling_tags")
    @classmethod
    def _v_tags(cls, value: list[str] | None) -> list[str] | None:
        return _clean_tags(value)


class JournalEntryUpdate(BaseModel):
    """The date is intentionally NOT updatable — changing an entry's
    date could collide with another day's entry (there's one entry per
    user per day) and muddles the "log of what happened on this day"
    meaning. To move an entry, delete it and create a new one."""

    notes: str | None = None
    skin_feeling_tags: list[str] | None = None

    @field_validator("notes")
    @classmethod
    def _v_notes(cls, value: str | None) -> str | None:
        return _clean_notes(value)

    @field_validator("skin_feeling_tags")
    @classmethod
    def _v_tags(cls, value: list[str] | None) -> list[str] | None:
        return _clean_tags(value)


class JournalEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    entry_date: datetime.date
    notes: str | None
    skin_feeling_tags: list[str] | None
    created_at: datetime.datetime

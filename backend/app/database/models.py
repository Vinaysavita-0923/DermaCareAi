"""
ORM table definitions.

This is the schema only — no API routes, no password hashing logic, no
endpoint that writes to these tables yet. Those come in later phases
(auth in Phase 3, profile/journal CRUD in Phase 4, etc.). Phase 2's job
is just to have a schema that's correct, tested, and migratable.

Privacy decisions baked into the schema itself (not just comments):
  * `JournalEntry.photo_path` is nullable and unused until a later
    phase implements private storage + consent + deletion. The column
    exists now so the migration doesn't have to change shape later, but
    nothing in Phase 2 ever writes to it.
  * `AIAnalysisHistory` has no image column at all — per the project
    brief, uploaded images are not persisted by default. Only the
    prediction metadata is ever stored, and only once Phase 6 actually
    implements opt-in saving.
"""
from __future__ import annotations

import datetime
import enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


# ---------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------
class User(Base):
    """The schema includes a password hash column now, but nothing in
    Phase 2 populates it — signup/login/hashing is Phase 3's job. A
    nullable `google_sub` is included so Google OAuth (also Phase 3,
    per the project brief: "only after basic authentication works") can
    be added without another migration."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    # Nullable at the database level so adding this column to an
    # existing table is a safe migration even if rows already exist;
    # the signup endpoint (Phase 3) always requires and sets a real
    # value, so in practice it is never left empty for real users.
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    skin_profile: Mapped["SkinProfile | None"] = relationship(back_populates="user", uselist=False)
    chat_sessions: Mapped[list["ChatSession"]] = relationship(back_populates="user")
    journal_entries: Mapped[list["JournalEntry"]] = relationship(back_populates="user")
    routines: Mapped[list["Routine"]] = relationship(back_populates="user")
    analysis_history: Mapped[list["AIAnalysisHistory"]] = relationship(back_populates="user")
    assessment_history: Mapped[list["SkinAssessmentHistory"]] = relationship(back_populates="user")


# ---------------------------------------------------------------------
# Skin profile (preferences, not a diagnosis)
# ---------------------------------------------------------------------
class SkinType(str, enum.Enum):
    dry = "dry"
    oily = "oily"
    combination = "combination"
    balanced = "balanced"
    unsure = "unsure"


class SkinProfile(Base):
    """One row per user — the CURRENT live profile, read by every
    existing consumer (chat agent, recommendations, routines,
    dashboard). `concerns` and `avoid_ingredients` are stored as JSON
    lists rather than separate tables — this is user-selected
    preference data to personalize educational content, not a clinical
    record, so a normalized schema isn't needed yet.

    `age`/`age_group`/`skin_subtype`/`is_sensitive` were added for the
    dataset-backed assessment engine (see
    app/knowledge_base/skin_assessment_dataset.py). They are all
    nullable so existing rows from before this feature remain valid.
    `is_sensitive` is a tri-state: True="Yes", False="No", None="Not
    sure" — the assessment dataset only has Yes/No rows, so "not sure"
    is handled at the lookup layer, not invented here.
    Each submission also appends an immutable row to
    SkinAssessmentHistory, so history survives even though this table
    only ever holds the latest state (matches the existing one-row-
    per-user shape every other feature already depends on)."""

    __tablename__ = "skin_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    skin_type: Mapped[SkinType] = mapped_column(Enum(SkinType), default=SkinType.unsure)
    concerns: Mapped[list | None] = mapped_column(JSON, nullable=True)  # e.g. ["acne", "redness"]
    sensitivity_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    avoid_ingredients: Mapped[list | None] = mapped_column(JSON, nullable=True)
    age: Mapped[int | None] = mapped_column(nullable=True)
    age_group: Mapped[str | None] = mapped_column(String(10), nullable=True)
    skin_subtype: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_sensitive: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    user: Mapped["User"] = relationship(back_populates="skin_profile")


class SkinAssessmentHistory(Base):
    """An immutable snapshot of a skin assessment at the time it was
    submitted. `SkinProfile` above is overwritten on every save (it's
    the "current" profile every other feature reads); this table is
    the append-only history the assessment spec asks for, so past
    answers are never lost. `concerns` is a JSON list, matching the
    existing SkinProfile.concerns convention rather than introducing a
    separate per-concern table."""

    __tablename__ = "skin_assessment_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    age: Mapped[int | None] = mapped_column(nullable=True)
    age_group: Mapped[str | None] = mapped_column(String(10), nullable=True)
    skin_type: Mapped[SkinType] = mapped_column(Enum(SkinType), nullable=False)
    skin_subtype: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_sensitive: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    concerns: Mapped[list | None] = mapped_column(JSON, nullable=True)
    sensitivity_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="assessment_history")


# ---------------------------------------------------------------------
# Chat (Phase 5 will add the actual endpoint + LLM service)
# ---------------------------------------------------------------------
class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="chat_sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class ChatRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"), nullable=False)
    role: Mapped[ChatRole] = mapped_column(Enum(ChatRole), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Set when a mock/placeholder provider answered instead of a real
    # LLM, so the frontend can label it honestly (per the project brief:
    # "Clearly indicate when mock responses are used").
    is_mock_response: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    session: Mapped["ChatSession"] = relationship(back_populates="messages")


# ---------------------------------------------------------------------
# Journal
# ---------------------------------------------------------------------
class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    entry_date: Mapped[datetime.date] = mapped_column(nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    skin_feeling_tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # NOT populated by Phase 2 or any current phase. Reserved for a
    # later phase that implements private storage, validation, explicit
    # consent, and deletion controls, per the project brief. A column
    # existing here is not permission to write to it.
    photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="journal_entries")

    __table_args__ = (UniqueConstraint("user_id", "entry_date", name="uq_journal_user_date"),)


# ---------------------------------------------------------------------
# Routines
# ---------------------------------------------------------------------
class RoutineType(str, enum.Enum):
    morning = "morning"
    night = "night"


class Routine(Base):
    __tablename__ = "routines"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    routine_type: Mapped[RoutineType] = mapped_column(Enum(RoutineType), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="routines")
    items: Mapped[list["RoutineItem"]] = relationship(
        back_populates="routine", cascade="all, delete-orphan"
    )
    logs: Mapped[list["RoutineLog"]] = relationship(
        back_populates="routine", cascade="all, delete-orphan"
    )


class RoutineItem(Base):
    __tablename__ = "routine_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    routine_id: Mapped[int] = mapped_column(ForeignKey("routines.id"), nullable=False)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    step_order: Mapped[int] = mapped_column(default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    routine: Mapped["Routine"] = relationship(back_populates="items")
    product: Mapped["Product | None"] = relationship()


class RoutineLog(Base):
    __tablename__ = "routine_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    routine_id: Mapped[int] = mapped_column(ForeignKey("routines.id"), nullable=False)
    log_date: Mapped[datetime.date] = mapped_column(nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    routine: Mapped["Routine"] = relationship(back_populates="logs")

    __table_args__ = (UniqueConstraint("routine_id", "log_date", name="uq_routinelog_routine_date"),)


# ---------------------------------------------------------------------
# Products & ingredients
# ---------------------------------------------------------------------
class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Per the project brief: "Do not invent availability, prices, or
    # medical effectiveness." Anything not backed by a real source must
    # be flagged as sample/demo data so it's never confused with a
    # verified product claim.
    is_sample_data: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    # Real rating from the uploaded catalogue (never invented by us) and the
    # raw INCI ingredient string, kept here (rather than exploded into
    # Ingredient/ProductIngredient rows) so the searchable catalogue can be
    # bulk-loaded without polluting the curated Ingredient table that the
    # assessment/recommendation engine relies on for precaution text.
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    ingredients_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Same ingredient list, but "|"-delimited (the catalogue's own
    # pre-split column) so the UI can render individual ingredient chips
    # without re-splitting ingredients_text on "," - which breaks names
    # that contain a comma themselves, e.g. "1,2-Hexanediol".
    ingredients_list: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Skin-type suitability and ingredient count, straight from the
    # uploaded catalogue's own columns (suitable_dry/normal/oily/
    # sensitive/combination, ingredient_count) - null means "not stated
    # in the source data", never inferred.
    ingredient_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    suitable_dry: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    suitable_normal: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    suitable_oily: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    suitable_combination: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    suitable_sensitive: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    ingredients: Mapped[list["ProductIngredient"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    precautions: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(500), nullable=True)

    products: Mapped[list["ProductIngredient"]] = relationship(back_populates="ingredient")


class ProductIngredient(Base):
    """Association table between products and ingredients."""

    __tablename__ = "product_ingredients"

    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"), primary_key=True)

    product: Mapped["Product"] = relationship(back_populates="ingredients")
    ingredient: Mapped["Ingredient"] = relationship(back_populates="products")


# ---------------------------------------------------------------------
# AI analysis history (Phase 6) — metadata only, never the image itself
# ---------------------------------------------------------------------
class AIAnalysisHistory(Base):
    """Deliberately has no image/photo column. Per the project brief,
    uploaded images are not persisted by default, and this table is
    only ever written to if a later phase adds explicit user opt-in —
    the table's existence here does not mean every analysis gets
    recorded automatically."""

    __tablename__ = "ai_analysis_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    predicted_class: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_score: Mapped[float] = mapped_column(Float, nullable=False)
    is_diagnosis: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="analysis_history")


# ---------------------------------------------------------------------
# Revoked tokens (Phase 3) — makes logout actually mean something
# ---------------------------------------------------------------------
class RevokedToken(Base):
    """A JWT access token is stateless by design — the server doesn't
    normally know it exists until it's presented. That means "logout"
    for a plain JWT does nothing server-side unless we keep a small
    denylist of tokens that have been explicitly logged out before
    their natural expiry. Every protected request checks this table by
    the token's `jti` (a random ID minted into each token); the login
    endpoint doesn't need it, since no token has been issued yet.

    Rows can be deleted after `expires_at` has passed (the token would
    be rejected as expired anyway by then) — Phase 3 does not implement
    that cleanup job, which is a noted limitation, not an oversight."""

    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    revoked_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

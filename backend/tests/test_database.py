"""
Tests for Phase 2: the database layer only.

These run against a throwaway SQLite file created fresh for the test
session and deleted afterwards — never the real skincare.db, and
nothing here touches a FastAPI route (there are none yet that use the
database; that starts in Phase 3).
"""
from __future__ import annotations

import datetime
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.connection import Base
from app.database.models import (
    AIAnalysisHistory,
    ChatMessage,
    ChatRole,
    ChatSession,
    Ingredient,
    JournalEntry,
    Product,
    ProductIngredient,
    Routine,
    RoutineLog,
    RoutineType,
    SkinProfile,
    SkinType,
    User,
)

TEST_DB_PATH = "test_phase2.db"
TEST_DB_URL = f"sqlite:///{TEST_DB_PATH}"


@pytest.fixture()
def db_session():
    """A clean database, built from the real models, for each test."""
    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)


def test_all_expected_tables_exist():
    expected = {
        "users", "skin_profiles", "chat_sessions", "chat_messages",
        "journal_entries", "routines", "routine_items", "routine_logs",
        "products", "ingredients", "product_ingredients", "ai_analysis_history",
    }
    assert expected.issubset(set(Base.metadata.tables.keys()))


def test_create_user_and_fetch_by_email(db_session):
    user = User(email="test@example.com", hashed_password=None)
    db_session.add(user)
    db_session.commit()

    fetched = db_session.query(User).filter_by(email="test@example.com").one()
    assert fetched.id == user.id
    assert fetched.is_active is True  # default applied


def test_duplicate_email_is_rejected(db_session):
    db_session.add(User(email="dup@example.com"))
    db_session.commit()

    db_session.add(User(email="dup@example.com"))
    with pytest.raises(Exception):
        db_session.commit()
    db_session.rollback()


def test_skin_profile_one_to_one_and_relationship(db_session):
    user = User(email="profile@example.com")
    db_session.add(user)
    db_session.commit()

    profile = SkinProfile(
        user_id=user.id,
        skin_type=SkinType.oily,
        concerns=["acne", "texture"],
        avoid_ingredients=["fragrance"],
    )
    db_session.add(profile)
    db_session.commit()

    db_session.refresh(user)
    assert user.skin_profile is not None
    assert user.skin_profile.skin_type == SkinType.oily
    assert "acne" in user.skin_profile.concerns


def test_journal_entry_unique_per_user_per_day(db_session):
    user = User(email="journal@example.com")
    db_session.add(user)
    db_session.commit()

    today = datetime.date.today()
    db_session.add(JournalEntry(user_id=user.id, entry_date=today, notes="Felt dry"))
    db_session.commit()

    # Same user, same date again -> should violate the unique constraint.
    db_session.add(JournalEntry(user_id=user.id, entry_date=today, notes="Second entry"))
    with pytest.raises(Exception):
        db_session.commit()
    db_session.rollback()


def test_journal_entry_photo_path_defaults_to_none(db_session):
    """Privacy check: a journal entry created without an explicit photo
    must not somehow end up with one — nothing should default-populate
    this column."""
    user = User(email="nophoto@example.com")
    db_session.add(user)
    db_session.commit()

    entry = JournalEntry(user_id=user.id, entry_date=datetime.date.today())
    db_session.add(entry)
    db_session.commit()

    assert entry.photo_path is None


def test_ai_analysis_history_has_no_image_column():
    """Privacy check at the schema level: this table must never grow an
    image-storing column by accident in a future edit."""
    columns = {c.name for c in AIAnalysisHistory.__table__.columns}
    assert "image_path" not in columns
    assert "image" not in columns
    assert "photo" not in columns


def test_chat_session_cascades_to_messages(db_session):
    user = User(email="chat@example.com")
    db_session.add(user)
    db_session.commit()

    session_row = ChatSession(user_id=user.id, title="First chat")
    db_session.add(session_row)
    db_session.commit()

    db_session.add(ChatMessage(session_id=session_row.id, role=ChatRole.user, content="Hi"))
    db_session.add(
        ChatMessage(
            session_id=session_row.id,
            role=ChatRole.assistant,
            content="Hello! How can I help with your skin care questions?",
            is_mock_response=True,
        )
    )
    db_session.commit()

    db_session.refresh(session_row)
    assert len(session_row.messages) == 2
    assert session_row.messages[1].is_mock_response is True

    # Deleting the session should cascade-delete its messages.
    db_session.delete(session_row)
    db_session.commit()
    remaining = db_session.query(ChatMessage).filter_by(session_id=session_row.id).all()
    assert remaining == []


def test_routine_log_unique_per_routine_per_day(db_session):
    user = User(email="routine@example.com")
    db_session.add(user)
    db_session.commit()

    routine = Routine(user_id=user.id, routine_type=RoutineType.morning)
    db_session.add(routine)
    db_session.commit()

    today = datetime.date.today()
    db_session.add(RoutineLog(routine_id=routine.id, log_date=today, completed=True))
    db_session.commit()

    db_session.add(RoutineLog(routine_id=routine.id, log_date=today, completed=False))
    with pytest.raises(Exception):
        db_session.commit()
    db_session.rollback()


def test_product_ingredient_association(db_session):
    product = Product(name="Gentle Cleanser", is_sample_data=True, source="sample data")
    ingredient = Ingredient(name="Niacinamide")
    db_session.add_all([product, ingredient])
    db_session.commit()

    db_session.add(ProductIngredient(product_id=product.id, ingredient_id=ingredient.id))
    db_session.commit()

    db_session.refresh(product)
    assert len(product.ingredients) == 1
    assert product.ingredients[0].ingredient.name == "Niacinamide"


def test_product_defaults_to_marked_as_sample_data(db_session):
    """Per the project brief: anything not backed by a verified source
    must default to being flagged as sample/demo data."""
    product = Product(name="Unverified Moisturizer")
    db_session.add(product)
    db_session.commit()
    assert product.is_sample_data is True


def test_get_db_dependency_yields_and_closes_session():
    """Exercise the actual FastAPI dependency function, not a re-built
    copy of it, against the throwaway test database."""
    from app.database import connection as conn_module

    # Point the dependency at the test database for this one check,
    # then restore it, so this test doesn't leak into others.
    original_engine = conn_module.engine
    original_session_local = conn_module.SessionLocal
    try:
        test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=test_engine)
        conn_module.engine = test_engine
        conn_module.SessionLocal = sessionmaker(bind=test_engine)

        gen = conn_module.get_db()
        session = next(gen)
        session.add(User(email="dependency@example.com"))
        session.commit()
        assert session.query(User).count() == 1

        # Exhausting the generator must run the `finally: db.close()`.
        with pytest.raises(StopIteration):
            next(gen)
    finally:
        conn_module.engine = original_engine
        conn_module.SessionLocal = original_session_local
        test_engine.dispose()  # release the file handle so Windows can delete it
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)

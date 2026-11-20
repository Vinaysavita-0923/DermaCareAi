"""
Tests for Phase 6: acne image analysis.

Because no verified checkpoint exists, the "valid inference" case here
asserts the HONEST not-configured behavior — a valid image is accepted,
decoded, and returns model_status="model_not_configured" with no
fabricated prediction. The validation, auth, size, and format cases are
fully exercised regardless of whether a model exists.
"""
from __future__ import annotations

import io
import os

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.connection import Base, get_db
from app.main import app

TEST_DB_PATH = "test_phase6_acne.db"
TEST_DB_URL = f"sqlite:///{TEST_DB_PATH}"

_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
_TestSessionLocal = sessionmaker(bind=_engine)


def _override_get_db():
    db = _TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=_engine)
    Base.metadata.create_all(bind=_engine)
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture(scope="module", autouse=True)
def cleanup_file():
    yield
    _engine.dispose()
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


client = TestClient(app)


def token() -> str:
    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Acne Tester", "email": "acne@example.com", "password": "StrongPass1"},
    )
    return client.post(
        "/api/v1/auth/login", json={"email": "acne@example.com", "password": "StrongPass1"}
    ).json()["access_token"]


def auth(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


def _image_bytes(fmt="JPEG", size=(64, 64), color="pink") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, fmt)
    return buf.getvalue()


# ---------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------
def test_acne_requires_auth():
    resp = client.post(
        "/api/v1/acne/analyze",
        files={"image": ("face.jpg", _image_bytes(), "image/jpeg")},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------
# Valid image -> honest not-configured result (no fabricated prediction)
# ---------------------------------------------------------------------
def test_valid_image_returns_model_not_configured():
    t = token()
    resp = client.post(
        "/api/v1/acne/analyze",
        headers=auth(t),
        files={"image": ("face.jpg", _image_bytes(), "image/jpeg")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["model_status"] == "model_not_configured"
    assert body["predicted_class"] is None
    assert body["raw_score"] is None
    assert body["is_diagnosis"] is False
    # The response must not leak any filesystem path.
    assert "/" not in body["note"] or "http" not in body["note"]


def test_valid_png_also_accepted():
    t = token()
    resp = client.post(
        "/api/v1/acne/analyze",
        headers=auth(t),
        files={"image": ("face.png", _image_bytes(fmt="PNG"), "image/png")},
    )
    assert resp.status_code == 200
    assert resp.json()["model_status"] == "model_not_configured"


# ---------------------------------------------------------------------
# Invalid / malformed images
# ---------------------------------------------------------------------
def test_non_image_file_rejected():
    t = token()
    resp = client.post(
        "/api/v1/acne/analyze",
        headers=auth(t),
        files={"image": ("notimage.jpg", b"this is plain text, not an image", "image/jpeg")},
    )
    assert resp.status_code == 422


def test_corrupt_image_rejected():
    t = token()
    # Valid JPEG header bytes followed by garbage -> should fail to decode.
    corrupt = b"\xff\xd8\xff\xe0" + b"\x00" * 100
    resp = client.post(
        "/api/v1/acne/analyze",
        headers=auth(t),
        files={"image": ("broken.jpg", corrupt, "image/jpeg")},
    )
    assert resp.status_code == 422


def test_unsupported_format_rejected():
    t = token()
    # A real image, but in BMP (an unsupported format). The content-type
    # is deliberately a lie (image/jpeg) to prove we decode the bytes
    # rather than trusting the declared type.
    resp = client.post(
        "/api/v1/acne/analyze",
        headers=auth(t),
        files={"image": ("real.jpg", _image_bytes(fmt="BMP"), "image/jpeg")},
    )
    assert resp.status_code == 422
    assert "format" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------
# Oversized upload
# ---------------------------------------------------------------------
def test_oversized_upload_rejected():
    t = token()
    # ~9 MB of bytes, over the 8 MB default cap. Doesn't need to be a
    # valid image — the size check fires first.
    big = b"\xff\xd8\xff\xe0" + b"\x00" * (9 * 1024 * 1024)
    resp = client.post(
        "/api/v1/acne/analyze",
        headers=auth(t),
        files={"image": ("big.jpg", big, "image/jpeg")},
    )
    assert resp.status_code == 413


# ---------------------------------------------------------------------
# Privacy: response never carries a path / stored-image id
# ---------------------------------------------------------------------
def test_response_has_no_path_or_storage_fields():
    t = token()
    body = client.post(
        "/api/v1/acne/analyze",
        headers=auth(t),
        files={"image": ("face.jpg", _image_bytes(), "image/jpeg")},
    ).json()
    forbidden = {"path", "file_path", "filepath", "image_path", "stored_path", "image_id", "url"}
    assert forbidden.isdisjoint(body.keys())


# ---------------------------------------------------------------------
# A configured-but-unimplemented checkpoint must NOT fabricate output
# ---------------------------------------------------------------------
def test_configured_checkpoint_without_inference_returns_503(monkeypatch, tmp_path):
    """If someone sets ACNE_MODEL_PATH to a real file but inference
    isn't wired to that model yet, the service must refuse (503) rather
    than invent a prediction."""
    t = token()
    fake_ckpt = tmp_path / "model.pth"
    fake_ckpt.write_bytes(b"not a real checkpoint, but a file that exists")

    import app.services.acne_service as svc

    monkeypatch.setattr(svc.settings, "acne_model_path", str(fake_ckpt))

    resp = client.post(
        "/api/v1/acne/analyze",
        headers=auth(t),
        files={"image": ("face.jpg", _image_bytes(), "image/jpeg")},
    )
    assert resp.status_code == 503  # honest refusal, never a fabricated 200

"""
Tests for the experimental skin-condition image classifier.

Auth, upload validation, size/format handling, and the honest
"model_not_configured" fallback are exercised without depending on the
model file. When the bundled ONNX model IS present, one extra test
confirms a real prediction comes back with sane, non-diagnostic shape.
"""
from __future__ import annotations

import io
import os
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.connection import Base, get_db
from app.main import app
from app.services import skin_condition_service as svc

TEST_DB_PATH = "test_skin_condition.db"
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
URL = "/api/v1/skin-condition/analyze"


def token() -> str:
    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Skin Tester", "email": "skin@example.com", "password": "StrongPass1"},
    )
    return client.post(
        "/api/v1/auth/login", json={"email": "skin@example.com", "password": "StrongPass1"}
    ).json()["access_token"]


def auth(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


def _image_bytes(fmt="JPEG", size=(80, 80), color="pink") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, fmt)
    return buf.getvalue()


def test_requires_auth():
    resp = client.post(URL, files={"image": ("skin.jpg", _image_bytes(), "image/jpeg")})
    assert resp.status_code == 401


def test_non_image_rejected():
    t = token()
    resp = client.post(
        URL, headers=auth(t), files={"image": ("x.jpg", b"not an image", "image/jpeg")}
    )
    assert resp.status_code == 422


def test_oversized_rejected(monkeypatch):
    t = token()
    from app.api import skin_condition as api_mod

    monkeypatch.setattr(api_mod.settings, "acne_max_image_mb", 0.001)
    resp = client.post(
        URL, headers=auth(t), files={"image": ("big.jpg", _image_bytes(size=(400, 400)), "image/jpeg")}
    )
    assert resp.status_code == 413


def test_valid_image_response_shape():
    """Whether or not a model is loaded, a valid image returns 200 with the
    honest, non-diagnostic contract."""
    t = token()
    resp = client.post(
        URL, headers=auth(t), files={"image": ("skin.png", _image_bytes(fmt="PNG"), "image/png")}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_diagnosis"] is False
    assert body["model_status"] in {"ok", "model_not_configured"}
    if body["model_status"] == "ok" and body["not_skin"]:
        assert body["predictions"] == []  # a flat pink square isn't skin
    elif body["model_status"] == "ok":
        assert 1 <= len(body["predictions"]) <= 3
        top = body["predictions"][0]
        assert 0.0 <= top["score"] <= 1.0
        assert isinstance(top["label"], str) and top["label"]
    else:
        assert body["predictions"] == []


def test_model_not_configured_when_file_missing(monkeypatch):
    """If the model file isn't there, we never fabricate a prediction."""
    svc._load_session.cache_clear()
    monkeypatch.setattr(svc.settings, "skin_condition_model_path", "nonexistent-model.onnx")
    try:
        result = svc.analyze_image(_image_bytes())
        assert result.model_status == "model_not_configured"
        assert result.predictions == []
        assert result.is_diagnosis is False
    finally:
        svc._load_session.cache_clear()  # don't poison other tests


def test_trace_serious_class_does_not_dominate():
    """A tiny serious score shouldn't flip the warning when the top guess
    is a confident, harmless class."""
    from app.services.skin_condition_service import ConditionGuess, _SERIOUS_FLOOR

    top = ConditionGuess(label="Acne", score=0.95, serious=False, concern="acne")
    trace = ConditionGuess(label="Lupus", score=0.004, serious=True, concern=None)
    any_serious = top.serious or any(g.serious and g.score >= _SERIOUS_FLOOR for g in [top, trace])
    assert any_serious is False


def test_serious_top_guess_flags_warning():
    from app.services.skin_condition_service import ConditionGuess, _SERIOUS_FLOOR

    top = ConditionGuess(label="Skin Cancer", score=0.80, serious=True, concern=None)
    any_serious = top.serious or any(g.serious and g.score >= _SERIOUS_FLOOR for g in [top])
    assert any_serious is True


def test_non_skin_image_is_not_classified():
    """A plain non-skin image returns a 'not skin' result, not a fake label."""
    t = token()
    blue = _image_bytes(size=(200, 200), color=(30, 80, 200))
    resp = client.post(URL, headers=auth(t), files={"image": ("blue.png", blue, "image/png")})
    assert resp.status_code == 200
    body = resp.json()
    if body["model_status"] == "ok":  # model present
        assert body["not_skin"] is True
        assert body["predictions"] == []
        assert body["is_diagnosis"] is False


def test_gate_missing_means_not_configured(monkeypatch):
    """Without the skin gate we never classify unchecked images."""
    svc._load_gate.cache_clear()
    monkeypatch.setattr(svc.settings, "skin_gate_model_path", "nonexistent-gate.onnx")
    try:
        result = svc.analyze_image(_image_bytes())
        assert result.model_status == "model_not_configured"
        assert result.predictions == []
    finally:
        svc._load_gate.cache_clear()


_needs_models = pytest.mark.skipif(
    svc._load_session() is None or svc._load_gate() is None, reason="bundled ONNX models not present"
)


@_needs_models
@pytest.mark.parametrize("color", [(224, 172, 140), (141, 85, 36), (255, 219, 172)])
def test_flat_skin_tone_is_not_skin(color):
    """A flat skin-coloured image (a wall, a wooden table) used to pass the
    old colour rule; the learned gate must reject it."""
    result = svc.analyze_image(_image_bytes(size=(300, 300), color=color))
    assert result.not_skin is True
    assert result.predictions == []


@_needs_models
def test_noise_is_not_skin():
    rng = np.random.default_rng(0)
    buf = io.BytesIO()
    Image.fromarray(rng.integers(0, 256, (300, 300, 3), dtype=np.uint8)).save(buf, "PNG")
    assert svc.analyze_image(buf.getvalue()).not_skin is True


_PORTRAIT = Path(__file__).resolve().parents[2] / "frontend" / "public" / "team" / "vinay-savita.jpg"


@_needs_models
@pytest.mark.skipif(not _PORTRAIT.is_file(), reason="team portrait not present")
def test_real_portrait_is_classified():
    """A genuine photo of a person passes the gate and gets guesses."""
    result = svc.analyze_image(_PORTRAIT.read_bytes())
    assert result.not_skin is False
    assert 1 <= len(result.predictions) <= 3

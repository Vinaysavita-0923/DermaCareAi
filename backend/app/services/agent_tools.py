"""
Tools the chat agent may call.

Design rules (these are the safety properties of the agent):
  * The user is fixed by the server (ToolContext.user). No tool takes a
    user id from the model, so the model cannot read or touch another
    user's data no matter what it is told.
  * Read tools return small, truncated JSON. Their output is DATA — the
    system prompt tells the model never to follow instructions found in
    it (journal notes and product text are user/third-party text).
  * Tools that would CHANGE data never do so. They return a signed,
    short-lived proposal the user must confirm in the UI; only the
    confirm endpoint (execute_action) writes anything.
"""
from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field

import jwt
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.reports import get_report_summary
from app.core.config import get_settings
from app.services.recommendation_service import NoProfileError, build_recommendations
from app.database.models import (
    JournalEntry,
    Product,
    Routine,
    RoutineItem,
    RoutineLog,
    RevokedToken,
    RoutineType,
    User,
)

settings = get_settings()

_ACTION_ALG = "HS256"
_ACTION_TYP = "agent_action"


@dataclass
class ProposedAction:
    token: str
    kind: str
    summary: str


@dataclass
class ToolContext:
    db: Session
    user: User
    proposals: list[ProposedAction] = field(default_factory=list)
    use_profile: bool = True


def _clip(text: str | None, n: int = 300) -> str | None:
    if text is None:
        return None
    return text if len(text) <= n else text[: n - 1] + "…"


# ---------------------------------------------------------------------
# Signed action tokens (stateless, so no extra DB table is needed)
# ---------------------------------------------------------------------
def _action_key() -> str:
    # Separate key from login tokens so an action token can never be
    # accepted as an auth token (or vice versa).
    return settings.secret_key + ":agent-action"


def _sign_action(user: User, kind: str, params: dict) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "jti": "act-" + uuid.uuid4().hex,
        "typ": _ACTION_TYP,
        "uid": user.id,
        "kind": kind,
        "params": params,
        "exp": now + datetime.timedelta(minutes=settings.agent_action_ttl_minutes),
    }
    return jwt.encode(payload, _action_key(), algorithm=_ACTION_ALG)


class ActionError(Exception):
    """Bad, expired, tampered or foreign action token / invalid params."""


# ---------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------
_NO_CONSENT = {
    "consent": False,
    "note": "The user has switched off use of their saved skin assessment for this chat. "
    "Do not guess their skin details; answer generally or ask them.",
}


def _get_my_profile(ctx: ToolContext, **_: object) -> dict:
    if not ctx.use_profile:
        return _NO_CONSENT
    p = ctx.user.skin_profile
    if p is None:
        return {"profile": None, "note": "The user has not filled in a skin profile yet."}
    return {
        "skin_type": p.skin_type.value,
        "skin_subtype": p.skin_subtype,
        "age_group": p.age_group,
        "is_sensitive": p.is_sensitive,
        "concerns": p.concerns or [],
        "avoid_ingredients": p.avoid_ingredients or [],
        "sensitivity_notes": _clip(p.sensitivity_notes),
    }


def _get_recent_journal(ctx: ToolContext, limit: int = 5, **_: object) -> dict:
    limit = max(1, min(int(limit), 10))
    rows = (
        ctx.db.query(JournalEntry)
        .filter(JournalEntry.user_id == ctx.user.id)
        .order_by(JournalEntry.entry_date.desc(), JournalEntry.id.desc())
        .limit(limit)
        .all()
    )
    return {
        "entries": [
            {
                "date": r.entry_date.isoformat(),
                "feeling_tags": r.skin_feeling_tags or [],
                "notes": _clip(r.notes),
            }
            for r in rows
        ]
    }


def _routine_dict(r: Routine) -> dict:
    return {
        "routine_id": r.id,
        "type": r.routine_type.value,
        "steps": [
            {
                "order": i.step_order,
                "product": i.product.name if i.product else None,
                "notes": _clip(i.notes, 120),
            }
            for i in sorted(r.items, key=lambda x: x.step_order)
        ],
    }


def _get_my_routines(ctx: ToolContext, **_: object) -> dict:
    rows = ctx.db.query(Routine).filter(Routine.user_id == ctx.user.id).all()
    return {"routines": [_routine_dict(r) for r in rows]}


def _get_report_summary(ctx: ToolContext, days: int = 30, **_: object) -> dict:
    days = max(1, min(int(days), 365))
    rep = get_report_summary(days=days, current_user=ctx.user, db=ctx.db)
    return rep.model_dump(mode="json")


def _search_products(ctx: ToolContext, query: str = "", category: str | None = None, **_: object) -> dict:
    q = ctx.db.query(Product)
    if query:
        like = f"%{query}%"
        q = q.filter(
            or_(
                Product.name.ilike(like),
                Product.brand.ilike(like),
                Product.description.ilike(like),
                Product.ingredients_text.ilike(like),
            )
        )
    if category:
        q = q.filter(Product.category.ilike(category))
    return {
        "products": [
            {
                "product_id": p.id,
                "name": p.name,
                "brand": p.brand,
                "category": p.category,
                "rating": p.rating,
                "is_sample_data": p.is_sample_data,
            }
            for p in q.order_by(Product.name).limit(10).all()
        ]
    }


def _get_product_details(ctx: ToolContext, product_id: int, **_: object) -> dict:
    p = ctx.db.get(Product, int(product_id))
    if p is None:
        return {"error": "No product with that id."}
    return {
        "product_id": p.id,
        "name": p.name,
        "brand": p.brand,
        "description": _clip(p.description),
        "category": p.category,
        "rating": p.rating,
        "suitable_for": {
            "dry": p.suitable_dry,
            "normal": p.suitable_normal,
            "oily": p.suitable_oily,
            "combination": p.suitable_combination,
            "sensitive": p.suitable_sensitive,
        },
        "ingredient_list": _clip(p.ingredients_list, 600),
        "is_sample_data": p.is_sample_data,
        "source": p.source,
        "ingredients": [
            {
                "name": link.ingredient.name,
                "description": _clip(link.ingredient.description, 200),
                "precautions": _clip(link.ingredient.precautions, 200),
            }
            for link in p.ingredients
        ],
    }


def _get_product_recommendations(ctx: ToolContext, pregnant_or_trying: bool = False, **_: object) -> dict:
    if not ctx.use_profile:
        return _NO_CONSENT
    try:
        rec = build_recommendations(ctx.db, ctx.user, bool(pregnant_or_trying))
    except NoProfileError:
        return {"error": "The user has not saved a skin profile yet; ask them to complete the Skin Assessment."}

    def brief(p) -> dict:
        return {
            "product_id": p.product_id,
            "name": p.name,
            "brand": p.brand,
            "category": p.category,
            "why": p.match_reasons,
            "ingredient_info": p.ingredient_status,  # verified | partial | unverified | sample
            "warnings": [_clip(w, 150) for w in p.warnings],
            "cautions": _clip(p.cautions, 150),
        }

    return {
        "skin_type": rec.skin_type,
        "notes": rec.notes,
        "morning_routine": [brief(p) for p in rec.routine.morning],
        "evening_routine": [brief(p) for p in rec.routine.evening],
        "other_matches": [p.name for p in rec.matches[:10]],
    }


# ---------------------------------------------------------------------
# Propose tools (never write)
# ---------------------------------------------------------------------
def _propose_create_routine(ctx: ToolContext, routine_type: str, steps: list | None = None, **_: object) -> dict:
    try:
        rtype = RoutineType(str(routine_type).lower())
    except ValueError:
        return {"error": "routine_type must be 'morning' or 'night'."}
    clean: list[dict] = []
    for i, s in enumerate((steps or [])[:10], start=1):
        if not isinstance(s, dict):
            continue
        pid = s.get("product_id")
        if pid is not None:
            if ctx.db.get(Product, int(pid)) is None:
                return {"error": f"Product {pid} does not exist."}
            pid = int(pid)
        clean.append({"product_id": pid, "step_order": i, "notes": _clip(s.get("notes"), 200)})
    params = {"routine_type": rtype.value, "steps": clean}
    summary = f"Create a {rtype.value} routine with {len(clean)} step(s)"
    ctx.proposals.append(ProposedAction(_sign_action(ctx.user, "create_routine", params), "create_routine", summary))
    return {"status": "awaiting_user_confirmation", "note": "Nothing has been saved yet. Tell the user to press Confirm."}


def _propose_log_routine(
    ctx: ToolContext, routine_id: int, completed: bool = True, log_date: str | None = None, **_: object
) -> dict:
    routine = ctx.db.get(Routine, int(routine_id))
    if routine is None or routine.user_id != ctx.user.id:
        return {"error": "No routine with that id."}
    try:
        day = datetime.date.fromisoformat(log_date) if log_date else datetime.date.today()
    except ValueError:
        return {"error": "log_date must be YYYY-MM-DD."}
    if day > datetime.date.today():
        return {"error": "Cannot log a future date."}
    params = {"routine_id": routine.id, "completed": bool(completed), "log_date": day.isoformat()}
    word = "completed" if completed else "skipped"
    summary = f"Log your {routine.routine_type.value} routine as {word} on {day.isoformat()}"
    ctx.proposals.append(ProposedAction(_sign_action(ctx.user, "log_routine", params), "log_routine", summary))
    return {"status": "awaiting_user_confirmation", "note": "Nothing has been saved yet. Tell the user to press Confirm."}


# ---------------------------------------------------------------------
# Registry: schema shown to the model + the function that runs it
# ---------------------------------------------------------------------
def _schema(name: str, description: str, props: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": props, "required": required or []},
        },
    }


TOOLS: dict[str, tuple[dict, callable]] = {
    "get_my_profile": (
        _schema("get_my_profile", "Get the user's skin type, concerns and ingredients to avoid.", {}),
        _get_my_profile,
    ),
    "get_recent_journal": (
        _schema(
            "get_recent_journal",
            "Get the user's most recent skin journal entries (date, feeling tags, notes).",
            {"limit": {"type": "integer", "description": "How many entries, 1-10"}},
        ),
        _get_recent_journal,
    ),
    "get_my_routines": (
        _schema("get_my_routines", "List the user's morning/night routines and their steps.", {}),
        _get_my_routines,
    ),
    "get_report_summary": (
        _schema(
            "get_report_summary",
            "Summary of what the user logged over the last N days (journal count, tags, routine completion).",
            {"days": {"type": "integer", "description": "Period in days, 1-365"}},
        ),
        _get_report_summary,
    ),
    "search_products": (
        _schema(
            "search_products",
            "Search the product catalog by name, brand or keyword.",
            {"query": {"type": "string"}, "category": {"type": "string"}},
        ),
        _search_products,
    ),
    "get_product_details": (
        _schema(
            "get_product_details",
            "Get a product's description and its ingredients, including ingredient precautions.",
            {"product_id": {"type": "integer"}},
            ["product_id"],
        ),
        _get_product_details,
    ),
    "get_product_recommendations": (
        _schema(
            "get_product_recommendations",
            "Get catalog products and a basic morning/evening routine matched to the user's saved skin "
            "profile (same results as the Skin Assessment page). Hides products with ingredients the "
            "user avoids; pregnancy caution hides common actives.",
            {"pregnant_or_trying": {"type": "boolean", "description": "Only true if the user said so"}},
        ),
        _get_product_recommendations,
    ),
    "propose_create_routine": (
        _schema(
            "propose_create_routine",
            "Propose creating a routine. The user must confirm before it is saved.",
            {
                "routine_type": {"type": "string", "enum": ["morning", "night"]},
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"product_id": {"type": "integer"}, "notes": {"type": "string"}},
                    },
                },
            },
            ["routine_type"],
        ),
        _propose_create_routine,
    ),
    "propose_log_routine": (
        _schema(
            "propose_log_routine",
            "Propose logging a routine as done or skipped for a date (default today). The user must confirm.",
            {
                "routine_id": {"type": "integer"},
                "completed": {"type": "boolean"},
                "log_date": {"type": "string", "description": "YYYY-MM-DD, not in the future"},
            },
            ["routine_id"],
        ),
        _propose_log_routine,
    ),
}

TOOL_SCHEMAS: list[dict] = [schema for schema, _ in TOOLS.values()]


def run_tool(ctx: ToolContext, name: str, arguments: dict) -> dict:
    entry = TOOLS.get(name)
    if entry is None:
        return {"error": f"Unknown tool '{name}'."}
    try:
        return entry[1](ctx, **arguments)
    except (TypeError, ValueError) as exc:  # bad arguments from the model
        return {"error": f"Invalid arguments: {type(exc).__name__}"}


# ---------------------------------------------------------------------
# Execute a confirmed action (called only from the confirm endpoint)
# ---------------------------------------------------------------------
def execute_action(db: Session, user: User, token: str) -> str:
    try:
        data = jwt.decode(token, _action_key(), algorithms=[_ACTION_ALG])
    except jwt.PyJWTError as exc:
        raise ActionError("This action is invalid or has expired. Please ask again.") from exc
    if data.get("typ") != _ACTION_TYP or data.get("uid") != user.id:
        raise ActionError("This action is invalid or has expired. Please ask again.")

    # Single use: a confirmed token is recorded so pressing Confirm twice
    # (or replaying the request) cannot repeat the action.
    jti = data.get("jti", "")
    if not jti or db.get(RevokedToken, jti) is not None:
        raise ActionError("This action was already used. Please ask again.")
    db.add(
        RevokedToken(
            jti=jti,
            expires_at=datetime.datetime.fromtimestamp(data["exp"], datetime.timezone.utc),
        )
    )

    kind, params = data.get("kind"), data.get("params") or {}
    if kind == "create_routine":
        routine = Routine(user_id=user.id, routine_type=RoutineType(params["routine_type"]))
        db.add(routine)
        db.flush()
        for s in params.get("steps", []):
            db.add(
                RoutineItem(
                    routine_id=routine.id,
                    product_id=s.get("product_id"),
                    step_order=s.get("step_order", 0),
                    notes=s.get("notes"),
                )
            )
        db.commit()
        return f"Done - your {routine.routine_type.value} routine has been created."

    if kind == "log_routine":
        routine = db.get(Routine, params["routine_id"])
        if routine is None or routine.user_id != user.id:
            raise ActionError("That routine no longer exists.")
        day = datetime.date.fromisoformat(params["log_date"])
        log = (
            db.query(RoutineLog)
            .filter(RoutineLog.routine_id == routine.id, RoutineLog.log_date == day)
            .first()
        )
        if log is None:
            db.add(RoutineLog(routine_id=routine.id, log_date=day, completed=bool(params["completed"])))
        else:
            log.completed = bool(params["completed"])
        db.commit()
        return "Done - your routine log has been saved."

    raise ActionError("Unknown action.")

"""Fills the product catalogue tables from data/catalog.json.

Safe to run on every deploy: does nothing if the products table already
has rows. Run after `alembic upgrade head`.

    python -m scripts.load_catalog
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import DateTime, Table, func, select, text

from app.database.connection import Base, SessionLocal, engine
from app.database import models  # noqa: F401  (registers the tables)

SRC = Path(__file__).resolve().parent.parent / "data" / "catalog.json"
TABLES = ["ingredients", "products", "product_ingredients"]  # parents first


def _coerce(table: Table, row: dict) -> dict:
    """SQLite stores datetimes as text; other databases want datetime objects."""
    out = dict(row)
    for col in table.columns:
        if isinstance(col.type, DateTime) and isinstance(out.get(col.name), str):
            out[col.name] = datetime.fromisoformat(out[col.name])
    return out


def main() -> None:
    products = Base.metadata.tables["products"]
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(products)):
            print("Catalogue already loaded - nothing to do.")
            return
        data = json.loads(SRC.read_text(encoding="utf-8"))
        for name in TABLES:
            table = Base.metadata.tables[name]
            rows = [_coerce(table, r) for r in data[name]]
            for i in range(0, len(rows), 500):
                db.execute(table.insert(), rows[i : i + 500])
        db.commit()
        if engine.dialect.name == "postgresql":  # ids were inserted explicitly
            for name in ("ingredients", "products"):  # product_ingredients has no id
                db.execute(
                    text(
                        f"SELECT setval(pg_get_serial_sequence('{name}', 'id'), "
                        f"(SELECT COALESCE(MAX(id), 1) FROM {name}))"
                    )
                )
            db.commit()
        print({n: len(data[n]) for n in TABLES}, "loaded.")


if __name__ == "__main__":
    main()

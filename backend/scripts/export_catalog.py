"""Writes the product catalogue tables from a SQLite database to
data/catalog.json, so a fresh (e.g. PostgreSQL) database can be filled by
scripts/load_catalog.py without shipping any user data.

    python -m scripts.export_catalog [path/to/skincare.db]
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

TABLES = ["ingredients", "products", "product_ingredients"]
OUT = Path(__file__).resolve().parent.parent / "data" / "catalog.json"


def main() -> None:
    src = sys.argv[1] if len(sys.argv) > 1 else str(OUT.parent.parent / "skincare.db")
    con = sqlite3.connect(src)
    con.row_factory = sqlite3.Row
    data = {t: [dict(r) for r in con.execute(f'SELECT * FROM "{t}" ORDER BY rowid')] for t in TABLES}
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print({t: len(rows) for t, rows in data.items()}, "->", OUT)


if __name__ == "__main__":
    main()

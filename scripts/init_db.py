from __future__ import annotations

import sqlite3
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DB_DIR = ROOT_DIR / "db"
SCHEMA_PATH = DB_DIR / "schema.sql"
DB_PATH = DB_DIR / "forge_install.db"


def init_db() -> Path:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(schema_sql)
        conn.commit()

    return DB_PATH


if __name__ == "__main__":
    db_path = init_db()
    print(f"Database initialized: {db_path}")

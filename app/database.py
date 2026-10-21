from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from .paths import DB_DIR, DB_PATH, SCHEMA_PATH


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, column_sql: str) -> None:
    if not _column_exists(conn, table, column):
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_sql}")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc):
                raise


def _apply_migrations(conn: sqlite3.Connection) -> None:
    _ensure_column(conn, "job_install_input", "base_plate_no_5", "base_plate_no_5 TEXT")
    _ensure_column(conn, "job_install_input", "die_hit_count", "die_hit_count INTEGER DEFAULT 0")
    for table in [
        "master_product_process",
        "master_die_version",
        "master_die_seat",
        "master_block",
        "master_base_plate",
    ]:
        _ensure_column(conn, table, "invalid_reason", "invalid_reason TEXT")
    _ensure_column(conn, "master_die_version", "total_hit_count", "total_hit_count INTEGER DEFAULT 0")
    _ensure_column(conn, "master_die_version", "after_repair_hit_count", "after_repair_hit_count INTEGER DEFAULT 0")
    _ensure_column(conn, "master_die_seat", "base_template_wear", "base_template_wear REAL DEFAULT 0")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS master_option (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          category TEXT NOT NULL,
          option_value TEXT NOT NULL,
          sort_order INTEGER NOT NULL DEFAULT 0,
          is_active INTEGER NOT NULL DEFAULT 1,
          remark TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(category, option_value)
        )
        """
    )
    # Demo edition: canonical values are English.  Only the legacy
    # die-version marker still needs normalizing on old databases.
    conn.execute("UPDATE master_die_version SET die_version = 'v1.00' WHERE die_version = 'legacy_import'")
    conn.execute("UPDATE job_install SET die_version = 'v1.00' WHERE die_version = 'legacy_import'")


def _seed_options(conn: sqlite3.Connection) -> None:
    now = datetime.now().replace(microsecond=0).isoformat(sep=" ")
    defaults = {
        "Product Type": ["Structural Part", "Compressor Blade", "Turbine Blade R", "Turbine Blade L", "Diaphragm Blade R", "Diaphragm Blade L", "Tool-holder Blade"],
        "Blade Direction": ["R", "L", "Forward", "Reverse", "/"],
        "Size Grade": ["Small", "Medium", "Large"],
        "Crown Angle Grade": ["Small Angle", "Medium Angle", "Large Angle"],
        "Energy Grade": ["Low", "Medium", "High"],
        "Shift": ["Day Shift", "Swing Shift", "Night Shift", "Day 12h Shift", "Night 12h Shift"],
        "Process Name": ["Pre-forging", "Finish Forging", "Die Forging", "Hot Sizing", "First-heat Forging", "Second-heat Forging"],
    }
    for category, options in defaults.items():
        for index, option in enumerate(options, start=1):
            conn.execute(
                """
                INSERT OR IGNORE INTO master_option (
                  category, option_value, sort_order, is_active, remark, created_at, updated_at
                ) VALUES (?, ?, ?, 1, NULL, ?, ?)
                """,
                (category, option, index, now, now),
            )


def ensure_database() -> Path:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(schema)
        _apply_migrations(conn)
        _seed_options(conn)
        conn.commit()
    return DB_PATH


def get_connection() -> sqlite3.Connection:
    ensure_database()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

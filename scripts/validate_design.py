from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT_DIR / "docs"
DB_DIR = ROOT_DIR / "db"

REQUIRED_FILES = [
    ROOT_DIR / "README.md",
    ROOT_DIR / "requirements.txt",
    DOCS_DIR / "01-architecture.md",
    DOCS_DIR / "02-ui-flow.md",
    DOCS_DIR / "03-recommendation-and-import.md",
    DOCS_DIR / "04-testing.md",
    DB_DIR / "schema.sql",
]

REQUIRED_TABLES = {
    "master_product_process",
    "master_die_version",
    "master_die_seat",
    "master_block",
    "master_base_plate",
    "master_compensation_rule",
    "job_install",
    "job_install_input",
    "job_calc_snapshot",
    "job_first_piece_feedback",
    "job_sample_grade",
    "job_adjustment",
    "job_attachment",
    "sys_import_log",
    "sys_backup_log",
}


def assert_required_files() -> None:
    missing = [str(path) for path in REQUIRED_FILES if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing design docs:\n" + "\n".join(missing))


def assert_schema_buildable() -> None:
    schema = (DB_DIR / "schema.sql").read_text(encoding="utf-8")
    with sqlite3.connect(":memory:") as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(schema)
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table';"
        ).fetchall()
        tables = {row[0] for row in rows}

    missing_tables = sorted(REQUIRED_TABLES - tables)
    if missing_tables:
        raise RuntimeError("schema.sql does not create these tables:\n" + "\n".join(missing_tables))


def main() -> int:
    assert_required_files()
    assert_schema_buildable()
    print("Design validation passed:")
    print("- Key design docs present")
    print("- schema.sql builds a database")
    print("- Core tables exist")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Design validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)

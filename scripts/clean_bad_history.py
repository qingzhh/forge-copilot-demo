from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DB_DIR = ROOT_DIR / "db"
DB_PATH = DB_DIR / "forge_install.db"
BACKUP_DIR = DB_DIR / "backups"


def backup_database() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"forge_install_before_clean_{timestamp}.db"
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def find_bad_job_ids(conn: sqlite3.Connection) -> list[int]:
    sql = """
    SELECT j.id
    FROM job_install j
    LEFT JOIN job_first_piece_feedback f ON f.job_id = j.id
    -- Demo edition: the original script targeted two specific legacy
    -- import batches.  Generalized here to any imported job whose
    -- first-piece feedback is missing or has empty/non-positive key fields.
    WHERE
      j.job_no LIKE 'IMP-%'
      AND (
        f.job_id IS NULL
        OR f.actual_template_thickness IS NULL
        OR f.actual_lower_x_pad_root IS NULL
        OR f.actual_lower_y_pad IS NULL
        OR f.measured_x_offset_root IS NULL
        OR f.measured_y_offset IS NULL
        OR COALESCE(f.actual_template_thickness, 0) <= 0
      )
    """
    return [row[0] for row in conn.execute(sql).fetchall()]


def clean_database() -> tuple[Path, int]:
    backup_path = backup_database()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        job_ids = find_bad_job_ids(conn)
        if not job_ids:
            return backup_path, 0
        placeholders = ",".join("?" for _ in job_ids)
        for table in [
            "job_adjustment",
            "job_attachment",
            "job_sample_grade",
            "job_first_piece_feedback",
            "job_calc_snapshot",
            "job_install_input",
            "job_install",
        ]:
            conn.execute(f"DELETE FROM {table} WHERE job_id IN ({placeholders})" if table != "job_install" else f"DELETE FROM {table} WHERE id IN ({placeholders})", job_ids)
        conn.commit()
    return backup_path, len(job_ids)


if __name__ == "__main__":
    backup_path, removed = clean_database()
    print(f"Database backed up to: {backup_path}")
    print(f"Removed obviously incomplete/incorrect history rows: {removed}")

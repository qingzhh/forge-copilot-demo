from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.excel_importer import import_workbook
from app.services import ForgeRepository


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    schema = (root / "db" / "schema.sql").read_text(encoding="utf-8")
    workbook = next(p for p in root.parent.glob("*.xlsx") if not p.name.startswith("~$"))

    fd, temp_name = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    temp_db = Path(temp_name)
    temp_db.unlink(missing_ok=True)

    conn = sqlite3.connect(temp_db)
    conn.executescript(schema)
    summary = import_workbook(conn, workbook)
    conn.close()

    os.environ["PYTHONUTF8"] = "1"
    repo = ForgeRepository()
    try:
        stats = repo.get_success_stats()
        export_path = root / "exports" / "deep_check_export.csv"
        exported = repo.export_analysis_csv(export_path)
        print("Deep check passed:")
        print("Import summary:", summary)
        print("All-time success rates:", stats["alltime"])
        print("Monthly data points:", len(stats["monthly"]))
        print("Exported file:", exported)
    finally:
        repo.close()
        temp_db.unlink(missing_ok=True)


if __name__ == "__main__":
    main()

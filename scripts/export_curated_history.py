from __future__ import annotations

import shutil
from pathlib import Path

import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services import ForgeRepository


ROOT_DIR = Path(__file__).resolve().parents[1]
EXPORT_DIR = ROOT_DIR / "exports"
DIST_DATA_DIR = ROOT_DIR / "dist" / "ForgeCopilot" / "sample_data"


def main() -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    repo = ForgeRepository()
    try:
        rows = repo.list_history_rows()
        count = len(rows)
        output = EXPORT_DIR / f"curated_history_{count}.csv"
        repo.export_analysis_csv(output)
        print(f"Exported curated history: {output}")
        if DIST_DATA_DIR.parent.exists():
            DIST_DATA_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(output, DIST_DATA_DIR / output.name)
            print(f"Copied to the portable bundle: {DIST_DATA_DIR / output.name}")
    finally:
        repo.close()


if __name__ == "__main__":
    main()

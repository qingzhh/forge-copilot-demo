from __future__ import annotations

import shutil
from pathlib import Path

import PyInstaller.__main__


ROOT_DIR = Path(__file__).resolve().parents[1]


def main() -> None:
    build_dir = ROOT_DIR / "build"
    dist_dir = ROOT_DIR / "dist"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    if dist_dir.exists():
        shutil.rmtree(dist_dir)

    PyInstaller.__main__.run(
        [
            "--noconfirm",
            "--clean",
            "--windowed",
            "--onedir",
            "--name",
            "ForgeCopilot",
            "--add-data",
            "db\\schema.sql;db",
            "app\\main.py",
        ]
    )

    # Copy the current database into the portable bundle so a fresh install
    # starts with the bundled master data and (demo) history right away.
    db_source_dir = ROOT_DIR / "db"
    db_source_file = db_source_dir / "forge_install.db"
    if db_source_file.exists():
        target_db_dir = ROOT_DIR / "dist" / "ForgeCopilot" / "db"
        target_db_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(db_source_file, target_db_dir / "forge_install.db")

    export_dir = ROOT_DIR / "exports"
    if export_dir.exists():
        target_dir = ROOT_DIR / "dist" / "ForgeCopilot" / "sample_data"
        target_dir.mkdir(parents=True, exist_ok=True)
        for file in export_dir.glob("*.csv"):
            shutil.copy2(file, target_dir / file.name)


if __name__ == "__main__":
    main()

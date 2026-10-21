from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent

if getattr(sys, "frozen", False):
    ROOT_DIR = Path(sys.executable).resolve().parent
    INTERNAL_DIR = Path(getattr(sys, "_MEIPASS", ROOT_DIR))
else:
    ROOT_DIR = APP_DIR.parent
    INTERNAL_DIR = ROOT_DIR

DB_DIR = ROOT_DIR / "db"
DB_PATH = DB_DIR / "forge_install.db"
SCHEMA_PATH = INTERNAL_DIR / "db" / "schema.sql"
CONFIG_PATH = DB_DIR / "app_config.json"

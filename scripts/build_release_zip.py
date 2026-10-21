from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from build_portable_exe import main as build_portable_exe


ROOT_DIR = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT_DIR / "dist" / "ForgeCopilot"
DOC_TXT = ROOT_DIR / "docs" / "USER_GUIDE.md"
README_FILE = ROOT_DIR / "README.md"
RELEASE_DIR = ROOT_DIR / "release"


def copy_release_docs() -> None:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DOC_TXT, DIST_DIR / "USER_GUIDE.md")
    shutil.copy2(README_FILE, DIST_DIR / "README.md")


def build_zip() -> Path:
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = RELEASE_DIR / "ForgeCopilot_v1.30_portable.zip"
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in DIST_DIR.rglob("*"):
            if file.is_file():
                zf.write(file, file.relative_to(DIST_DIR.parent))
    return zip_path


def main() -> None:
    build_portable_exe()
    copy_release_docs()
    zip_path = build_zip()
    print(f"Release zip created: {zip_path}")


if __name__ == "__main__":
    main()

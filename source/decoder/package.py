"""Build the submission ZIP: output/, source/, optional demo/. Excludes secrets and caches."""

from __future__ import annotations

import zipfile
from pathlib import Path

EXCLUDE_DIRS = {".cache", "__pycache__", ".venv", "venv", ".git", ".idea", ".vscode", "node_modules"}
EXCLUDE_FILES = {".env", ".DS_Store"}
MAX_BYTES = 15 * 1024 * 1024


def _skip(path: Path, include_debug: bool) -> bool:
    if any(part in EXCLUDE_DIRS for part in path.parts):
        return True
    if path.name in EXCLUDE_FILES or (path.name.startswith(".env") and path.name != ".env.example"):
        return True
    if not include_debug and "debug" in path.parts:
        return True
    return path.suffix in {".pyc", ".zip"}


def build_zip(root: Path, zip_path: Path, include_debug: bool = True) -> tuple[int, list[str]]:
    """root contains output/, source/ and optionally demo/. Returns (size, warnings)."""
    warnings: list[str] = []
    for required in ("output/level1.csv", "output/level2.csv", "source/README.md", "source/.env.example"):
        if not (root / required).exists():
            warnings.append(f"missing {required}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for top in ("output", "source", "demo"):
            base = root / top
            if not base.exists():
                continue
            for p in sorted(base.rglob("*")):
                rel = p.relative_to(root)
                if p.is_file() and not _skip(rel, include_debug):
                    zf.write(p, rel.as_posix())
    size = zip_path.stat().st_size
    if size > MAX_BYTES:
        warnings.append(f"ZIP is {size / 1e6:.1f} MB (> 15 MB). Re-run with --no-debug or shrink the demo.")
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if name.endswith("/.env") or name == ".env":
                warnings.append("a .env file is inside the ZIP!")
    return size, warnings

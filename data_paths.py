from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
LEGACY_FILES = {
    "eventos.json",
    "enviados.json",
    "credentials.json",
    "token.json",
    "ideias.db",
    "ideias_verify.json",
    "ideias_verify.db",
}


def _root_path() -> Path:
    return Path(ROOT).resolve()


def _data_dir_path() -> Path:
    return Path(DATA_DIR).resolve()


def ensure_data_dir() -> Path:
    data_dir = _data_dir_path()
    data_dir.mkdir(parents=True, exist_ok=True)
    global DATA_DIR
    DATA_DIR = data_dir
    return data_dir


def resolve_data_path(name: str) -> Path:
    """Resolve the file path inside data/ and migrate any legacy root-level file automatically."""
    file_name = Path(str(name).strip().lstrip("/")).name
    data_dir = ensure_data_dir()

    destination = data_dir / file_name
    legacy = _root_path() / file_name

    if destination.exists():
        return destination

    if legacy.exists():
        try:
            shutil.copy2(legacy, destination)
        except OSError:
            pass

    return destination


def migrate_legacy_data_files() -> None:
    """Move root-level data files to data/ while keeping compatibility with old paths."""
    data_dir = ensure_data_dir()
    root = _root_path()
    for file_name in sorted(LEGACY_FILES):
        legacy = root / file_name
        destination = data_dir / file_name

        if not legacy.exists() or destination.exists():
            continue

        try:
            shutil.move(str(legacy), str(destination))
        except OSError:
            try:
                shutil.copy2(legacy, destination)
            except OSError:
                continue

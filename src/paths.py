"""Caminhos centrais do projeto.

`data/raw/` está no .gitignore, então os diretórios são criados sob demanda
pelos coletores em vez de versionados com .gitkeep.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DATA = ROOT / "data"
RAW = DATA / "raw"
RAW_FBREF = RAW / "fbref"

DB_PATH = DATA / "internacional_2025.db"


def ensure_raw_dirs() -> None:
    """Cria data/raw/ e data/raw/fbref/ se ainda não existirem."""
    RAW_FBREF.mkdir(parents=True, exist_ok=True)

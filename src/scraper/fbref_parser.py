"""Lê tabelas do FBref a partir de HTML salvo manualmente em data/raw/fbref/.

O FBref fica atrás de um desafio JavaScript do Cloudflare: requisições com
`requests` recebem 403 ("Just a moment..."), inclusive em /robots.txt e através
de proxies de renderização. Não há coleta automática possível — por isso este
módulo é um *parser* de arquivos locais, e não um scraper.

Duas particularidades do HTML do FBref guiam a implementação:

1. **Tabelas dentro de comentários.** Só a primeira tabela da página vem no DOM;
   as demais ficam embrulhadas em `<!-- ... -->` e são montadas por JavaScript.
   Um BeautifulSoup ingênuo enxerga apenas uma tabela.
2. **Colunas lidas por `data-stat`.** Cada célula carrega um atributo estável
   (`goals`, `xg`, `shots`, ...) que independe do idioma da página e da ordem
   das colunas. Os cabeçalhos visíveis mudam entre a versão pt e en; os
   `data-stat`, não.

Uso:
    poetry run python -m src.scraper.fbref_parser --list   # inspeciona o que foi salvo
    poetry run python -m src.scraper.fbref_parser
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup, Comment, Tag

from src.paths import RAW, RAW_FBREF, ensure_raw_dirs

SEASON_YEAR = 2025
TEAM_URL = "https://fbref.com/pt/equipes/6f7e1f03/Internacional-Estatisticas"

# Prefixo do id da tabela -> nome do CSV de saída. O sufixo do id varia com a
# competição (ex.: stats_shooting_24), então casamos por prefixo.
TABLES = {
    "matchlogs_for": "fixtures",
    "stats_shooting": "shooting",
    "stats_standard": "standard",
    "stats_passing": "passing",
    "stats_possession": "possession",
    "stats_keeper": "keeper",
    "shots_all": "shots",
}

INSTRUCTIONS = f"""
Nenhum HTML do FBref encontrado em {RAW_FBREF}

O FBref bloqueia coleta automática (Cloudflare), então as páginas precisam ser
salvas manualmente uma única vez:

  1. Abra no navegador: {TEAM_URL}
  2. Salve a página (Ctrl+S, "Página completa" ou "Somente HTML") em:
       {RAW_FBREF}
  3. Repita para as seções Scores & Fixtures, Shooting, Passing e Possession.

O nome dos arquivos não importa — o parser identifica as tabelas pelo id.
Depois rode de novo:  poetry run python -m src.scraper.fbref_parser --list
""".strip()


class FbrefDataMissing(FileNotFoundError):
    """Levantada quando não há HTML do FBref salvo para ler."""


def _iter_soups(html: str):
    """Produz o DOM principal e o de cada comentário que contenha uma tabela.

    O FBref esconde a maioria das tabelas em comentários; sem isso o parser
    enxergaria apenas a primeira tabela da página.
    """
    soup = BeautifulSoup(html, "lxml")
    yield soup
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        if "<table" in comment:
            yield BeautifulSoup(comment, "lxml")


def find_tables(html: str) -> dict[str, Tag]:
    """Mapeia id -> tabela, incluindo as escondidas em comentários."""
    tables: dict[str, Tag] = {}
    for soup in _iter_soups(html):
        for table in soup.find_all("table"):
            table_id = table.get("id")
            if table_id and table_id not in tables:
                tables[table_id] = table
    return tables


def table_to_frame(table: Tag) -> pd.DataFrame:
    """Converte uma tabela do FBref em DataFrame usando os `data-stat`.

    Ignora as linhas de cabeçalho repetidas no meio do corpo e o rodapé de
    totais, e converte para número o que for numérico.
    """
    body = table.find("tbody")
    rows = (body or table).find_all("tr")

    records = []
    for row in rows:
        classes = row.get("class") or []
        if "thead" in classes or "spacer" in classes or "over_header" in classes:
            continue
        cells = row.find_all(["th", "td"])
        record = {
            cell["data-stat"]: cell.get_text(" ", strip=True)
            for cell in cells
            if cell.has_attr("data-stat")
        }
        if record and any(record.values()):
            records.append(record)

    frame = pd.DataFrame(records)
    for column in frame.columns:
        converted = pd.to_numeric(frame[column], errors="coerce")
        # só troca a coluna se a conversão preservar a informação
        if converted.notna().sum() >= frame[column].str.strip().ne("").sum():
            frame[column] = converted
    return frame


def load_saved_html(directory: Path = RAW_FBREF) -> dict[Path, str]:
    """Lê todos os .html/.htm salvos no diretório."""
    if not directory.exists():
        raise FbrefDataMissing(INSTRUCTIONS)
    files = sorted(p for p in directory.rglob("*") if p.suffix.lower() in {".html", ".htm"})
    if not files:
        raise FbrefDataMissing(INSTRUCTIONS)
    return {path: path.read_text(encoding="utf-8", errors="replace") for path in files}


def collect_tables(directory: Path = RAW_FBREF) -> dict[str, tuple[Path, Tag]]:
    """Reúne todas as tabelas encontradas nos arquivos salvos."""
    found: dict[str, tuple[Path, Tag]] = {}
    for path, html in load_saved_html(directory).items():
        for table_id, table in find_tables(html).items():
            found.setdefault(table_id, (path, table))
    return found


def match_expected(table_ids) -> dict[str, str]:
    """Casa os ids encontrados com os prefixos conhecidos: id -> nome de saída."""
    matched = {}
    for table_id in table_ids:
        for prefix, name in TABLES.items():
            if table_id.startswith(prefix):
                matched[table_id] = name
                break
    return matched


def is_available(directory: Path = RAW_FBREF) -> bool:
    """Indica se há dados do FBref — o dashboard usa isto para degradar sem quebrar."""
    try:
        return bool(collect_tables(directory))
    except FbrefDataMissing:
        return False


def _cmd_list(directory: Path) -> int:
    tables = collect_tables(directory)
    expected = match_expected(tables)

    print(f"{len(tables)} tabelas encontradas em {directory}\n")
    for table_id, (path, table) in sorted(tables.items()):
        frame = table_to_frame(table)
        marca = f"-> {expected[table_id]}" if table_id in expected else "  (não mapeada)"
        print(f"  {table_id:<28} {len(frame):>4} linhas x {len(frame.columns):>3} col  "
              f"{marca}   [{path.name}]")

    faltando = set(TABLES.values()) - set(expected.values())
    if faltando:
        print(f"\nAinda não salvas: {', '.join(sorted(faltando))}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--list", action="store_true", help="lista as tabelas encontradas sem gravar CSV"
    )
    parser.add_argument(
        "--dir", type=Path, default=RAW_FBREF, help="diretório com o HTML salvo"
    )
    args = parser.parse_args(argv)

    try:
        tables = collect_tables(args.dir)
    except FbrefDataMissing as exc:
        print(exc, file=sys.stderr)
        return 1

    if args.list:
        return _cmd_list(args.dir)

    expected = match_expected(tables)
    if not expected:
        print(
            "Nenhuma tabela conhecida encontrada. Rode com --list para ver o que foi salvo.",
            file=sys.stderr,
        )
        return 1

    ensure_raw_dirs()
    for table_id, name in sorted(expected.items()):
        frame = table_to_frame(tables[table_id][1])
        if frame.empty:
            print(f"AVISO: tabela {table_id} veio vazia", file=sys.stderr)
            continue
        destino = RAW / f"inter_{SEASON_YEAR}_fbref_{name}.csv"
        frame.to_csv(destino, index=False, encoding="utf-8-sig")
        print(f"{len(frame):>4} linhas -> {destino.name}   (tabela {table_id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

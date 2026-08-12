"""Coleta classificação, posição por rodada, artilharia e técnicos na Wikipédia.

Fonte: artigo "Campeonato Brasileiro de Futebol de 2025 - Série A" via API
MediaWiki. Usamos `prop=text` (HTML renderizado) e não `prop=wikitext`, porque a
classificação vem de um template que só o parser do MediaWiki resolve.

As tabelas são localizadas pela assinatura do cabeçalho, não por índice fixo, de
modo que edições no artigo que insiram ou removam tabelas não quebrem a coleta.

Uso:
    poetry run python -m src.scraper.wikipedia
    poetry run python -m src.scraper.wikipedia --offline
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date

import pandas as pd
import requests
from bs4 import BeautifulSoup, Tag

from src.paths import RAW, ensure_raw_dirs

API_URL = "https://pt.wikipedia.org/w/api.php"
PAGE_TITLE = "Campeonato Brasileiro de Futebol de 2025 - Série A"
SEASON_YEAR = 2025
TOTAL_ROUNDS = 38

TEAM = "Internacional"

HTML_CACHE = RAW / f"wikipedia_brasileirao_{SEASON_YEAR}.html"
CLASSIFICACAO_CSV = RAW / f"brasileirao_{SEASON_YEAR}_classificacao.csv"
POS_RODADA_CSV = RAW / f"brasileirao_{SEASON_YEAR}_pos_por_rodada.csv"
ARTILHARIA_CSV = RAW / f"brasileirao_{SEASON_YEAR}_artilharia.csv"
ASSISTENCIAS_CSV = RAW / f"brasileirao_{SEASON_YEAR}_assistencias.csv"
TECNICOS_CSV = RAW / f"brasileirao_{SEASON_YEAR}_mudancas_tecnicos.csv"
INTER_TECNICOS_CSV = RAW / f"inter_{SEASON_YEAR}_tecnicos.csv"

MESES = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
    "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}

_REF_RE = re.compile(r"\[\s*\w+\s*\]")          # marcadores de referência: [ 59 ]
_EDIT_RE = re.compile(r"\bv\s+d\s+e\b")          # links do template "ver-discutir-editar"
_MARKER_RE = re.compile(r"\s*\((?:C|R|[A-Z])\)\s*$")  # (C) campeão, (R) rebaixado
_ROUND_RE = re.compile(r"^(\d+)\s*\.?\s*ª")
_ORDINAL_RE = re.compile(r"(\d+)")
_DATE_RE = re.compile(r"(\d{1,2})\s+de\s+([a-zç]+)", re.IGNORECASE)


def _clean(text: str) -> str:
    """Remove marcadores de referência, links de edição e espaços redundantes."""
    text = _REF_RE.sub("", text)
    text = _EDIT_RE.sub("", text)
    return " ".join(text.split()).strip()


def _cells(row: Tag) -> list[str]:
    return [_clean(c.get_text(" ", strip=True)) for c in row.find_all(["th", "td"])]


def _header(table: Tag) -> list[str]:
    rows = table.find_all("tr")
    return [c.casefold() for c in _cells(rows[0])] if rows else []


def _find_table(soup: BeautifulSoup, required: set[str], *, exclude: set[str] = frozenset()) -> Tag:
    """Localiza a primeira tabela cujo cabeçalho contenha todos os termos exigidos."""
    for table in soup.find_all("table"):
        header = _header(table)
        joined = " ".join(header)
        if not required <= set(header) and not all(term in joined for term in required):
            continue
        if any(term in joined for term in exclude):
            continue
        return table
    raise LookupError(f"nenhuma tabela com cabeçalho contendo {sorted(required)}")


def _to_int(value: str) -> int | None:
    match = _ORDINAL_RE.search(value.replace("+", "").replace("−", "-").replace("–", "-"))
    if not match:
        return None
    number = int(match.group(1))
    return -number if value.strip().startswith(("-", "−", "–")) else number


def parse_classificacao(soup: BeautifulSoup) -> pd.DataFrame:
    table = _find_table(soup, {"pos", "pts", "gp", "gc", "sg"})
    records = []
    for row in table.find_all("tr")[1:]:
        cells = _cells(row)
        if len(cells) < 10 or not cells[0].isdigit():
            continue
        records.append(
            {
                "posicao": int(cells[0]),
                "equipe": _MARKER_RE.sub("", cells[1]).strip(),
                "pontos": _to_int(cells[2]),
                "jogos": _to_int(cells[3]),
                "vitorias": _to_int(cells[4]),
                "empates": _to_int(cells[5]),
                "derrotas": _to_int(cells[6]),
                "gols_pro": _to_int(cells[7]),
                "gols_contra": _to_int(cells[8]),
                "saldo": _to_int(cells[9]),
                "situacao": cells[10] if len(cells) > 10 else "",
            }
        )
    return pd.DataFrame(records)


def parse_sigla_map(soup: BeautifulSoup) -> dict[str, str]:
    """Deriva o mapa sigla -> nome do time a partir da tabela de Confrontos.

    O cabeçalho traz as siglas (ATM, BAH, ...) e a primeira coluna, os nomes
    completos, ambos na mesma ordem alfabética — o que evita hardcodar os times.
    """
    table = _find_table(soup, {"mandante"})
    rows = table.find_all("tr")
    siglas = _cells(rows[0])[1:]
    nomes = [_cells(r)[0] for r in rows[1:] if _cells(r)]
    if len(siglas) != len(nomes):
        raise ValueError(
            f"Confrontos inconsistente: {len(siglas)} siglas e {len(nomes)} times"
        )
    return dict(zip(siglas, nomes))


def parse_pos_por_rodada(soup: BeautifulSoup, sigla_map: dict[str, str]) -> pd.DataFrame:
    """Posição de cada time ao fim de cada rodada, em formato longo.

    Na rodada 1 times empatados em todos os critérios dividem a colocação
    (Cruzeiro e Grêmio em 4º, e a seguinte é a 6ª), então as posições formam um
    "competition ranking" e não necessariamente a sequência 1..20. Da rodada 2
    em diante os valores são estritamente 1..20.
    """
    table = _find_table(soup, {"rodada"})
    rows = table.find_all("tr")
    siglas = _cells(rows[0])[1:]

    records = []
    for row in rows[1:]:
        cells = _cells(row)
        if not cells:
            continue
        round_match = _ROUND_RE.match(cells[0])
        if not round_match:
            continue
        rodada = int(round_match.group(1))
        for sigla, value in zip(siglas, cells[1:]):
            posicao = _to_int(value)
            if posicao is None:
                continue
            records.append(
                {
                    "rodada": rodada,
                    "sigla": sigla,
                    "equipe": sigla_map.get(sigla, sigla),
                    "posicao": posicao,
                }
            )
    return pd.DataFrame(records).sort_values(["rodada", "posicao"], ignore_index=True)


def _parse_ranking(soup: BeautifulSoup, metric: str, other: str) -> pd.DataFrame:
    """Extrai um ranking de jogadores (artilharia ou assistências).

    Jogadores empatados compartilham as células de posição e do total via
    `rowspan`: a primeira linha do grupo traz 4 células e as seguintes, apenas
    jogador e equipe. Os valores compartilhados são carregados adiante.
    """
    table = _find_table(soup, {"jogador", metric}, exclude={other})
    records = []
    posicao: int | None = None
    total: int | None = None

    for row in table.find_all("tr")[1:]:
        cells = _cells(row)
        if len(cells) >= 4:
            posicao, jogador, equipe, total = (
                _to_int(cells[0]),
                cells[1],
                cells[2],
                _to_int(cells[3]),
            )
        elif len(cells) == 2 and posicao is not None:
            jogador, equipe = cells
        else:
            continue
        records.append(
            {"posicao": posicao, "jogador": jogador, "equipe": equipe, metric: total}
        )
    return pd.DataFrame(records)


def parse_artilharia(soup: BeautifulSoup) -> pd.DataFrame:
    return _parse_ranking(soup, "gols", other="assist")


def parse_assistencias(soup: BeautifulSoup) -> pd.DataFrame:
    return _parse_ranking(soup, "assist", other="gols").rename(
        columns={"assist": "assistencias"}
    )


def _parse_date(text: str) -> date | None:
    match = _DATE_RE.search(text)
    if not match:
        return None
    month = MESES.get(match.group(2).casefold())
    return date(SEASON_YEAR, month, int(match.group(1))) if month else None


def parse_mudancas_tecnicos(soup: BeautifulSoup) -> pd.DataFrame:
    table = _find_table(soup, {"antecessor", "sucessor"})
    records = []
    for row in table.find_all("tr")[1:]:
        cells = _cells(row)
        if len(cells) < 7:
            continue
        records.append(
            {
                "clube": cells[0],
                "antecessor": cells[1],
                "data_saida": _parse_date(cells[2]),
                "ultima_partida": cells[3],
                "rodada_saida": _to_int(cells[4]),
                "posicao_saida": _to_int(cells[5]),
                "sucessor": cells[6],
            }
        )
    return pd.DataFrame(records)


def derive_coach_periods(
    mudancas: pd.DataFrame, clube: str = TEAM, total_rounds: int = TOTAL_ROUNDS
) -> pd.DataFrame:
    """Converte as trocas de técnico em períodos fechados de rodadas.

    Para o Inter em 2025: Roger Machado (1–24), Ramón Díaz (25–36) e
    Abel Braga (37–38).
    """
    changes = (
        mudancas[mudancas["clube"] == clube]
        .sort_values("rodada_saida")
        .reset_index(drop=True)
    )

    periods = []
    start = 1
    for _, change in changes.iterrows():
        end = int(change["rodada_saida"])
        periods.append(
            {
                "tecnico": change["antecessor"],
                "rodada_inicio": start,
                "rodada_fim": end,
                "jogos": end - start + 1,
                "data_saida": change["data_saida"],
                "ultima_partida": change["ultima_partida"],
                "posicao_saida": change["posicao_saida"],
            }
        )
        start = end + 1

    if not changes.empty:
        periods.append(
            {
                "tecnico": changes.iloc[-1]["sucessor"],
                "rodada_inicio": start,
                "rodada_fim": total_rounds,
                "jogos": total_rounds - start + 1,
                "data_saida": None,
                "ultima_partida": None,
                "posicao_saida": None,
            }
        )
    return pd.DataFrame(periods)


def fetch_html(*, timeout: int = 60) -> str:
    """Baixa o HTML renderizado do artigo e guarda uma cópia em data/raw/."""
    response = requests.get(
        API_URL,
        params={"action": "parse", "page": PAGE_TITLE, "prop": "text", "format": "json"},
        headers={"User-Agent": "internacional-2025-dashboard/0.1 (analise academica)"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(f"API MediaWiki: {payload['error'].get('info')}")

    html = payload["parse"]["text"]["*"]
    ensure_raw_dirs()
    HTML_CACHE.write_text(html, encoding="utf-8")
    return html


def load_cached_html() -> str:
    if not HTML_CACHE.exists():
        raise FileNotFoundError(
            f"HTML não encontrado em {HTML_CACHE}. "
            "Rode sem --offline pelo menos uma vez para baixá-lo."
        )
    return HTML_CACHE.read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="usa o HTML já salvo em data/raw/ em vez de baixar de novo",
    )
    args = parser.parse_args(argv)

    html = load_cached_html() if args.offline else fetch_html()
    soup = BeautifulSoup(html, "lxml")
    ensure_raw_dirs()

    sigla_map = parse_sigla_map(soup)

    outputs = {
        CLASSIFICACAO_CSV: parse_classificacao(soup),
        POS_RODADA_CSV: parse_pos_por_rodada(soup, sigla_map),
        ARTILHARIA_CSV: parse_artilharia(soup),
        ASSISTENCIAS_CSV: parse_assistencias(soup),
    }
    mudancas = parse_mudancas_tecnicos(soup)
    outputs[TECNICOS_CSV] = mudancas
    outputs[INTER_TECNICOS_CSV] = derive_coach_periods(mudancas)

    for path, frame in outputs.items():
        if frame.empty:
            print(f"ERRO: tabela vazia para {path.name}", file=sys.stderr)
            return 1
        frame.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"{len(frame):>4} linhas -> {path.name}")

    inter = outputs[CLASSIFICACAO_CSV].query("equipe == @TEAM")
    if not inter.empty:
        row = inter.iloc[0]
        print(
            f"\n{TEAM}: {row.posicao}º  {row.pontos} pts  "
            f"{row.vitorias}V {row.empates}E {row.derrotas}D  "
            f"{row.gols_pro}:{row.gols_contra} ({row.saldo:+d})"
        )
    print("\nTécnicos do Inter em 2025:")
    for _, period in outputs[INTER_TECNICOS_CSV].iterrows():
        print(
            f"  {period.tecnico:<15} rodadas {period.rodada_inicio:>2}-{period.rodada_fim:<2} "
            f"({period.jogos} jogos)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Coleta o calendário completo do Brasileirão Série A 2025 no Transfermarkt.

A página `gesamtspielplan` traz as 380 partidas agrupadas por rodada, com placar,
data e a posição de cada time na tabela no momento do jogo.

Sobre as colunas de posição (`pos_*`): o Transfermarkt informa a colocação com
que o time ENTRA na rodada, usando os próprios critérios de desempate — que
divergem dos da CBF em rodadas com muitos times empatados (ex.: rodada 2, o
Transfermarkt dá 11º ao Inter e a Wikipédia, 10º). São um dado de apoio; a fonte
autoritativa da posição por rodada é a tabela "Desempenho por rodada" da
Wikipédia, coletada em `src/scraper/wikipedia.py`.

Uso:
    poetry run python -m src.scraper.transfermarkt
    poetry run python -m src.scraper.transfermarkt --offline   # reusa o HTML salvo
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime

import pandas as pd
import requests
from bs4 import BeautifulSoup, Tag

from src.paths import RAW, ensure_raw_dirs

BASE_URL = "https://www.transfermarkt.com.br"

# ATENÇÃO: no Transfermarkt, saison_id=2024 corresponde à temporada 2025 do
# Brasileirão. saison_id=2025 devolve a temporada 2026 (com Athletico-PR e Remo).
SEASON_ID = 2024
SEASON_YEAR = 2025
COMPETITION = "BRA1"

GESAMTSPIELPLAN_URL = (
    f"{BASE_URL}/campeonato-brasileiro-serie-a/gesamtspielplan"
    f"/wettbewerb/{COMPETITION}/saison_id/{SEASON_ID}"
)

INTERNACIONAL_ID = "6600"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

HTML_CACHE = RAW / f"transfermarkt_gesamtspielplan_{SEASON_YEAR}.html"
MATCHES_CSV = RAW / f"brasileirao_{SEASON_YEAR}_partidas.csv"
INTER_CSV = RAW / f"inter_{SEASON_YEAR}_fixtures.csv"

_ROUND_RE = re.compile(r"(\d+)\s*\.?\s*[Rr]odada")
_SCORE_RE = re.compile(r"^(\d+):(\d+)$")
_DATE_RE = re.compile(r"(\d{2}/\d{2}/\d{2})")
_POSITION_RE = re.compile(r"\((\d+)\.\)")
_VEREIN_RE = re.compile(r"/verein/(\d+)")
_MATCH_ID_RE = re.compile(r"/spielbericht/(\d+)")


@dataclass(frozen=True)
class Match:
    """Uma partida do campeonato, na perspectiva neutra."""

    rodada: int
    data: date | None
    mandante: str
    mandante_id: str
    visitante: str
    visitante_id: str
    gols_mandante: int
    gols_visitante: int
    pos_mandante: int | None
    pos_visitante: int | None
    match_id: str | None


def fetch_html(*, timeout: int = 60) -> str:
    """Baixa o calendário completo e guarda uma cópia em data/raw/."""
    response = requests.get(
        GESAMTSPIELPLAN_URL,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9"},
        timeout=timeout,
    )
    response.raise_for_status()

    ensure_raw_dirs()
    HTML_CACHE.write_text(response.text, encoding="utf-8")
    return response.text


def load_cached_html() -> str:
    if not HTML_CACHE.exists():
        raise FileNotFoundError(
            f"HTML não encontrado em {HTML_CACHE}. "
            "Rode sem --offline pelo menos uma vez para baixá-lo."
        )
    return HTML_CACHE.read_text(encoding="utf-8")


def _parse_date(raw: str) -> date | None:
    """Converte 'sáb 29/03/25' em date(2025, 3, 29)."""
    match = _DATE_RE.search(raw)
    if not match:
        return None
    return datetime.strptime(match.group(1), "%d/%m/%y").date()


def _parse_team_cell(cell: Tag) -> tuple[str, str, int | None]:
    """Extrai (id, nome, posição) de uma célula de time.

    O texto vem como '(15.) Internacional' ou 'Internacional (15.)', gerando
    centenas de variantes por time — por isso o time é identificado pelo id
    numérico em /verein/<id>, e não pelo nome.
    """
    link = cell.find("a", href=_VEREIN_RE)
    if link is None:
        raise ValueError(f"célula de time sem link /verein/: {cell!r}")

    verein_id = _VEREIN_RE.search(link["href"]).group(1)

    raw = cell.get_text(" ", strip=True)
    position = _POSITION_RE.search(raw)
    name = _POSITION_RE.sub("", raw).strip()

    return verein_id, name, int(position.group(1)) if position else None


def parse_gesamtspielplan(html: str) -> list[Match]:
    """Extrai as 380 partidas do HTML do calendário."""
    soup = BeautifulSoup(html, "lxml")
    matches: list[Match] = []

    # A data aparece só na primeira linha de cada dia; as seguintes vêm vazias.
    # O último valor visto é carregado adiante (forward-fill).
    last_date: date | None = None

    for box in soup.find_all("div", class_="box"):
        header = box.find(
            ["h2", "div"], class_=re.compile("content-box-headline|table-header")
        )
        if header is None:
            continue
        round_match = _ROUND_RE.search(header.get_text(" ", strip=True))
        if round_match is None:
            continue
        rodada = int(round_match.group(1))

        for row in box.select("tr"):
            cells = row.find_all("td")
            if len(cells) < 7:
                continue

            if parsed := _parse_date(cells[0].get_text(" ", strip=True)):
                last_date = parsed

            # O placar é o texto de a.ergebnis-link. NÃO usar regex de \d+:\d+ no
            # texto da linha: o horário do jogo (ex. "21:00") também casa e
            # corrompe os dados.
            link = row.find("a", class_="ergebnis-link")
            if link is None:
                continue
            score = _SCORE_RE.match(link.get_text(strip=True))
            if score is None:
                continue  # jogo adiado / sem placar

            home_id, home_name, home_pos = _parse_team_cell(cells[2])
            away_id, away_name, away_pos = _parse_team_cell(cells[6])
            match_id = _MATCH_ID_RE.search(link.get("href", "") or "")

            matches.append(
                Match(
                    rodada=rodada,
                    data=last_date,
                    mandante=home_name,
                    mandante_id=home_id,
                    visitante=away_name,
                    visitante_id=away_id,
                    gols_mandante=int(score.group(1)),
                    gols_visitante=int(score.group(2)),
                    pos_mandante=home_pos,
                    pos_visitante=away_pos,
                    match_id=match_id.group(1) if match_id else None,
                )
            )

    return matches


def matches_to_frame(matches: list[Match]) -> pd.DataFrame:
    return pd.DataFrame([asdict(m) for m in matches]).sort_values(
        ["rodada", "data", "mandante"], ignore_index=True
    )


def team_perspective(df: pd.DataFrame, verein_id: str = INTERNACIONAL_ID) -> pd.DataFrame:
    """Reduz o calendário à perspectiva de um time (38 jogos)."""
    at_home = df["mandante_id"] == verein_id
    away = df["visitante_id"] == verein_id
    team = df[at_home | away].copy()

    home_side = team["mandante_id"] == verein_id
    team["mando"] = home_side.map({True: "casa", False: "fora"})
    team["adversario"] = team["visitante"].where(home_side, team["mandante"])
    team["adversario_id"] = team["visitante_id"].where(home_side, team["mandante_id"])
    team["gols_pro"] = team["gols_mandante"].where(home_side, team["gols_visitante"])
    team["gols_contra"] = team["gols_visitante"].where(home_side, team["gols_mandante"])
    team["pos_antes"] = team["pos_mandante"].where(home_side, team["pos_visitante"])

    team["resultado"] = pd.Series(
        pd.NA, index=team.index, dtype="object"
    ).mask(team["gols_pro"] > team["gols_contra"], "V").mask(
        team["gols_pro"] == team["gols_contra"], "E"
    ).mask(team["gols_pro"] < team["gols_contra"], "D")

    columns = [
        "rodada",
        "data",
        "mando",
        "adversario",
        "adversario_id",
        "gols_pro",
        "gols_contra",
        "resultado",
        "pos_antes",
        "match_id",
    ]
    return team[columns].sort_values("rodada", ignore_index=True)


def _summarize(inter: pd.DataFrame) -> str:
    counts = inter["resultado"].value_counts()
    wins, draws, losses = (int(counts.get(k, 0)) for k in ("V", "E", "D"))
    scored = int(inter["gols_pro"].sum())
    conceded = int(inter["gols_contra"].sum())
    points = wins * 3 + draws
    return (
        f"J {len(inter)}  V {wins}  E {draws}  D {losses}  "
        f"GP {scored}  GC {conceded}  SG {scored - conceded}  Pts {points}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="usa o HTML já salvo em data/raw/ em vez de baixar de novo",
    )
    args = parser.parse_args(argv)

    html = load_cached_html() if args.offline else fetch_html()
    matches = parse_gesamtspielplan(html)
    if not matches:
        print("ERRO: nenhuma partida extraída — o layout do site pode ter mudado.", file=sys.stderr)
        return 1

    ensure_raw_dirs()
    df = matches_to_frame(matches)
    df.to_csv(MATCHES_CSV, index=False, encoding="utf-8-sig")

    inter = team_perspective(df)
    inter.to_csv(INTER_CSV, index=False, encoding="utf-8-sig")

    print(f"{len(df):>3} partidas do campeonato -> {MATCHES_CSV.name}")
    print(f"{len(inter):>3} jogos do Internacional -> {INTER_CSV.name}")
    print(f"    {_summarize(inter)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Coleta xG e mapa de chutes do Brasileirão 2025 na API pública do FotMob.

O FBref não publica dados avançados para o Campeonato Brasileiro — nenhuma das
tabelas da página da temporada traz xG, nem distância de chute. O FotMob traz,
e com granularidade de chute: coordenadas no campo, xG, xGOT, tipo de chute e
situação de jogo.

São duas chamadas distintas:

* `leagues`      — 380 partidas da temporada e a tabela de xG por time;
* `matchDetails` — o shotmap de uma partida (um request por jogo).

Todo JSON baixado é gravado em `data/raw/fotmob/`, e `--offline` reprocessa a
cópia local sem repetir as requisições. Entre chamadas de rede há uma pausa
configurável (`--delay`), para não martelar o servidor.

Sobre qual xG usar: as duas agregações do próprio FotMob não batem exatamente.
Somando os chutes do Inter chega-se a 55,2 xG a favor e 46,7 contra, enquanto a
tabela da temporada traz 54,63 e 43,74 — diferença de ~1% no ataque e ~7% na
defesa, que não se explica por pênaltis, chutes bloqueados nem gols contra.
Como os dados de chute são auditáveis e reconciliam com o placar (44:57), use a
soma do shotmap para análise por partida, e a tabela da temporada apenas para
comparar com os outros times, de quem não coletamos chute a chute por padrão.

Uso:
    poetry run python -m src.scraper.fotmob
    poetry run python -m src.scraper.fotmob --offline
    poetry run python -m src.scraper.fotmob --todos-os-times   # 380 jogos
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from src.paths import RAW

LEAGUE_ID = 268          # Brasileirão Série A
SEASON = 2025
INTERNACIONAL_ID = "8702"
TOTAL_ROUNDS = 38

API_LEAGUE = "https://www.fotmob.com/api/data/leagues"
API_MATCH = "https://www.fotmob.com/api/data/matchDetails"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Referer": "https://www.fotmob.com/",
}

CACHE = RAW / "fotmob"
XG_TABELA_CSV = RAW / f"brasileirao_{SEASON}_xg_tabela.csv"
CHUTES_CSV = RAW / f"inter_{SEASON}_chutes.csv"
XG_PARTIDA_CSV = RAW / f"inter_{SEASON}_xg_por_partida.csv"

# eventType do FotMob -> rótulo em português
DESFECHOS = {
    "Goal": "gol",
    "AttemptSaved": "defendido",
    "Miss": "para fora",
    "Post": "trave",
    "Blocked": "bloqueado",
    "OwnGoal": "gol contra",
}


def _desfecho(chute: dict) -> str | None:
    """Rótulo do desfecho, com gol contra tratado à parte.

    O FotMob marca gol contra como eventType='Goal' no time de quem chutou, com
    `isOwnGoal=True` e sem xG. Sem essa distinção o Inter apareceria com 47 gols
    em vez de 44, e os 3 gols contra sumiriam do total sofrido (54 em vez de 57).
    """
    if chute.get("isOwnGoal"):
        return "gol contra"
    return DESFECHOS.get(chute.get("eventType"), chute.get("eventType"))


def _get(url: str, params: dict[str, Any], destino: Path, *, offline: bool, delay: float) -> dict:
    """Baixa um JSON com cache em disco; `offline` exige que o cache exista."""
    if destino.exists():
        return json.loads(destino.read_text(encoding="utf-8"))
    if offline:
        raise FileNotFoundError(
            f"{destino.name} não está em cache. Rode sem --offline pelo menos uma vez."
        )

    response = requests.get(url, params=params, headers=HEADERS, timeout=60)
    response.raise_for_status()
    payload = response.json()

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    time.sleep(delay)
    return payload


def fetch_league(*, offline: bool = False, delay: float = 1.5) -> dict:
    return _get(
        API_LEAGUE,
        {"id": LEAGUE_ID, "season": SEASON},
        CACHE / f"league_{SEASON}.json",
        offline=offline,
        delay=delay,
    )


def fetch_match(match_id: str, *, offline: bool = False, delay: float = 1.5) -> dict:
    return _get(
        API_MATCH,
        {"matchId": match_id},
        CACHE / f"match_{match_id}.json",
        offline=offline,
        delay=delay,
    )


def parse_xg_table(league: dict) -> pd.DataFrame:
    """Tabela de xG da temporada: 20 times, com xG, xG sofrido e pontos esperados.

    Atenção: os campos `position`/`xPosition` desta sub-tabela são o rank por
    pontos esperados, e não a colocação final no campeonato.
    """
    registros = []
    for time_ in league["table"][0]["data"]["table"]["xg"]:
        marcados, sofridos = (float(v) for v in time_["scoresStr"].split("-"))
        registros.append(
            {
                "equipe": time_["name"],
                "team_id": str(time_["teamId"]),
                "pontos": time_["pts"],
                "pontos_esperados": round(time_["xPoints"], 2),
                "gols_pro": int(marcados),
                "xg": round(time_["xg"], 2),
                "gols_contra": int(sofridos),
                "xg_contra": round(time_["xgConceded"], 2),
                "eficiencia_ataque": round(marcados - time_["xg"], 2),
                "eficiencia_defesa": round(sofridos - time_["xgConceded"], 2),
                "rank_pontos_esperados": time_["position"],
            }
        )
    return pd.DataFrame(registros).sort_values("pontos_esperados", ascending=False,
                                               ignore_index=True)


def parse_fixtures(league: dict) -> pd.DataFrame:
    registros = []
    for partida in league["fixtures"]["allMatches"]:
        placar = partida["status"].get("scoreStr") or ""
        marcados, _, sofridos = placar.partition("-")
        registros.append(
            {
                "match_id": str(partida["id"]),
                "rodada": int(partida["round"]),
                "data": partida["status"]["utcTime"][:10],
                "mandante": partida["home"]["name"],
                "mandante_id": str(partida["home"]["id"]),
                "visitante": partida["away"]["name"],
                "visitante_id": str(partida["away"]["id"]),
                "gols_mandante": int(marcados) if marcados.strip().isdigit() else None,
                "gols_visitante": int(sofridos) if sofridos.strip().isdigit() else None,
                "encerrada": bool(partida["status"].get("finished")),
            }
        )
    return pd.DataFrame(registros).sort_values("rodada", ignore_index=True)


def team_fixtures(fixtures: pd.DataFrame, team_id: str = INTERNACIONAL_ID) -> pd.DataFrame:
    return fixtures[
        (fixtures.mandante_id == team_id) | (fixtures.visitante_id == team_id)
    ].reset_index(drop=True)


def parse_shotmap(match: dict, meta: pd.Series, team_id: str = INTERNACIONAL_ID) -> pd.DataFrame:
    """Extrai os chutes de uma partida, já com o contexto do jogo."""
    shotmap = (match.get("content") or {}).get("shotmap") or {}
    chutes = shotmap.get("shots") or []

    em_casa = meta.mandante_id == team_id
    registros = []
    for chute in chutes:
        do_time = str(chute.get("teamId")) == team_id
        registros.append(
            {
                "rodada": meta.rodada,
                "match_id": meta.match_id,
                "data": meta.data,
                "equipe": meta.mandante if str(chute.get("teamId")) == meta.mandante_id
                else meta.visitante,
                "do_internacional": do_time,
                "mando": "casa" if em_casa else "fora",
                "adversario": meta.visitante if em_casa else meta.mandante,
                "jogador": chute.get("playerName"),
                "minuto": chute.get("min"),
                "x": chute.get("x"),
                "y": chute.get("y"),
                "xg": chute.get("expectedGoals"),
                "xgot": chute.get("expectedGoalsOnTarget"),
                "desfecho": _desfecho(chute),
                "tipo_chute": chute.get("shotType"),
                "situacao": chute.get("situation"),
                "dentro_area": chute.get("isFromInsideBox"),
                "no_alvo": chute.get("isOnTarget"),
                "bloqueado": chute.get("isBlocked"),
                "gol_contra": chute.get("isOwnGoal"),
            }
        )
    return pd.DataFrame(registros)


def contar_gols(chutes: pd.DataFrame) -> tuple[int, int]:
    """Gols marcados e sofridos pelo Inter, segundo o shotmap.

    Um gol contra é creditado ao adversário, não a quem chutou.
    """
    do_inter = chutes.do_internacional
    marcados = int(((do_inter) & (chutes.desfecho == "gol")).sum())
    sofridos = int(
        ((~do_inter) & (chutes.desfecho == "gol")).sum()
        + ((do_inter) & (chutes.desfecho == "gol contra")).sum()
    )
    return marcados, sofridos


def aggregate_por_partida(chutes: pd.DataFrame, fixtures: pd.DataFrame,
                          team_id: str = INTERNACIONAL_ID) -> pd.DataFrame:
    """Consolida xG a favor e contra por partida, ao lado dos gols reais."""
    soma = (
        chutes.groupby(["rodada", "do_internacional"], as_index=False)["xg"]
        .sum()
        .pivot(index="rodada", columns="do_internacional", values="xg")
        .rename(columns={True: "xg_pro", False: "xg_contra"})
    )

    jogos = fixtures.copy()
    em_casa = jogos.mandante_id == team_id
    jogos["mando"] = em_casa.map({True: "casa", False: "fora"})
    jogos["adversario"] = jogos.visitante.where(em_casa, jogos.mandante)
    jogos["gols_pro"] = jogos.gols_mandante.where(em_casa, jogos.gols_visitante)
    jogos["gols_contra"] = jogos.gols_visitante.where(em_casa, jogos.gols_mandante)

    colunas = ["rodada", "data", "mando", "adversario", "gols_pro", "gols_contra", "match_id"]
    resultado = jogos[colunas].merge(soma, on="rodada", how="left")
    resultado["xg_pro"] = resultado["xg_pro"].round(2)
    resultado["xg_contra"] = resultado["xg_contra"].round(2)
    resultado["saldo_xg"] = (resultado.xg_pro - resultado.xg_contra).round(2)
    return resultado.sort_values("rodada", ignore_index=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true",
                        help="usa apenas o JSON já em cache em data/raw/fotmob/")
    parser.add_argument("--delay", type=float, default=1.5,
                        help="pausa em segundos entre requisições (padrão: 1.5)")
    parser.add_argument("--todos-os-times", action="store_true",
                        help="baixa o shotmap das 380 partidas, não só as do Inter")
    args = parser.parse_args(argv)

    try:
        league = fetch_league(offline=args.offline, delay=args.delay)
    except (FileNotFoundError, requests.RequestException) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1

    xg_tabela = parse_xg_table(league)
    xg_tabela.to_csv(XG_TABELA_CSV, index=False, encoding="utf-8-sig")
    print(f"{len(xg_tabela):>4} times -> {XG_TABELA_CSV.name}")

    fixtures = parse_fixtures(league)
    alvo = fixtures if args.todos_os_times else team_fixtures(fixtures)
    encerradas = alvo[alvo.encerrada]

    print(f"\nBaixando shotmap de {len(encerradas)} partidas "
          f"(pausa de {args.delay}s entre requisições)...")

    partes = []
    for numero, (_, meta) in enumerate(encerradas.iterrows(), start=1):
        try:
            match = fetch_match(meta.match_id, offline=args.offline, delay=args.delay)
        except (FileNotFoundError, requests.RequestException) as exc:
            print(f"  rodada {meta.rodada}: falhou ({exc})", file=sys.stderr)
            continue
        chutes = parse_shotmap(match, meta)
        if chutes.empty:
            print(f"  rodada {meta.rodada}: sem shotmap", file=sys.stderr)
            continue
        partes.append(chutes)
        print(f"  [{numero:>3}/{len(encerradas)}] rodada {meta.rodada:>2} "
              f"vs {meta.visitante if meta.mandante_id == INTERNACIONAL_ID else meta.mandante:<18}"
              f" {len(chutes):>3} chutes")

    if not partes:
        print("Nenhum shotmap coletado.", file=sys.stderr)
        return 1

    chutes = pd.concat(partes, ignore_index=True)
    chutes.to_csv(CHUTES_CSV, index=False, encoding="utf-8-sig")
    print(f"\n{len(chutes):>4} chutes -> {CHUTES_CSV.name}")

    por_partida = aggregate_por_partida(chutes, team_fixtures(fixtures))
    por_partida.to_csv(XG_PARTIDA_CSV, index=False, encoding="utf-8-sig")
    print(f"{len(por_partida):>4} partidas -> {XG_PARTIDA_CSV.name}")

    do_inter = chutes[chutes.do_internacional]
    print(
        f"\nInternacional: {do_inter.xg.sum():.1f} xG em {len(do_inter)} chutes  |  "
        f"sofrido: {chutes[~chutes.do_internacional].xg.sum():.1f} xG"
    )

    marcados, sofridos = contar_gols(chutes)
    esperado_pro, esperado_contra = int(por_partida.gols_pro.sum()), int(por_partida.gols_contra.sum())
    print(
        f"Gols pelo shotmap: {marcados}:{sofridos}  |  pelo placar: "
        f"{esperado_pro}:{esperado_contra}  "
        + ("OK" if (marcados, sofridos) == (esperado_pro, esperado_contra) else "DIVERGE")
    )
    if (marcados, sofridos) != (esperado_pro, esperado_contra):
        print(
            "AVISO: a soma dos gols do shotmap não bate com o placar das partidas.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

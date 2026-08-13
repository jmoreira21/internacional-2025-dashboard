"""Testes do coletor do FotMob."""

from __future__ import annotations

import pandas as pd
import pytest

from src.scraper.fotmob import (
    INTERNACIONAL_ID,
    aggregate_por_partida,
    contar_gols,
    parse_fixtures,
    parse_shotmap,
    parse_xg_table,
    team_fixtures,
)

OUTRO_ID = "9770"


def _shot(team_id, xg, event="Goal", own=False, **extra):
    return {
        "teamId": team_id,
        "playerName": extra.get("player", "Fulano"),
        "min": extra.get("min", 10),
        "x": 88.0,
        "y": 40.0,
        "expectedGoals": xg,
        "expectedGoalsOnTarget": extra.get("xgot", 0.5),
        "eventType": event,
        "shotType": "RightFoot",
        "situation": extra.get("situation", "RegularPlay"),
        "isFromInsideBox": True,
        "isOnTarget": event in {"Goal", "AttemptSaved"},
        "isBlocked": event == "Blocked",
        "isOwnGoal": own,
    }


LEAGUE = {
    "table": [
        {
            "data": {
                "table": {
                    "xg": [
                        {
                            "name": "Internacional", "teamId": 8702, "pts": 44,
                            "xPoints": 59.8, "scoresStr": "44-57",
                            "xg": 54.63, "xgConceded": 43.74, "position": 4,
                        },
                        {
                            "name": "Flamengo", "teamId": 9770, "pts": 79,
                            "xPoints": 71.2, "scoresStr": "78-27",
                            "xg": 63.56, "xgConceded": 33.72, "position": 1,
                        },
                    ]
                }
            }
        }
    ],
    "fixtures": {
        "allMatches": [
            {
                "round": "1", "id": "4732475",
                "home": {"name": "Flamengo", "id": "9770"},
                "away": {"name": "Internacional", "id": "8702"},
                "status": {"utcTime": "2025-03-30T00:00:00Z", "finished": True,
                           "scoreStr": "1 - 1"},
            },
            {
                "round": "2", "id": "4732500",
                "home": {"name": "Internacional", "id": "8702"},
                "away": {"name": "Flamengo", "id": "9770"},
                "status": {"utcTime": "2025-04-06T00:00:00Z", "finished": True,
                           "scoreStr": "3 - 0"},
            },
        ]
    },
}


@pytest.fixture
def fixtures():
    return parse_fixtures(LEAGUE)


def test_tabela_de_xg_calcula_eficiencia():
    df = parse_xg_table(LEAGUE)
    inter = df.query("equipe == 'Internacional'").iloc[0]
    assert inter.eficiencia_ataque == pytest.approx(44 - 54.63, abs=0.01)
    assert inter.eficiencia_defesa == pytest.approx(57 - 43.74, abs=0.01)
    assert inter.pontos_esperados == 59.8


def test_tabela_de_xg_ordenada_por_pontos_esperados():
    df = parse_xg_table(LEAGUE)
    assert df.equipe.tolist() == ["Flamengo", "Internacional"]


def test_fixtures_separa_placar(fixtures):
    assert len(fixtures) == 2
    primeiro = fixtures.iloc[0]
    assert (primeiro.gols_mandante, primeiro.gols_visitante) == (1, 1)
    assert primeiro.data == "2025-03-30"


def test_team_fixtures_filtra_os_dois_mandos(fixtures):
    inter = team_fixtures(fixtures, INTERNACIONAL_ID)
    assert len(inter) == 2


def test_shotmap_marca_mando_e_adversario(fixtures):
    meta = team_fixtures(fixtures).iloc[0]  # Inter visitante
    match = {"content": {"shotmap": {"shots": [_shot(INTERNACIONAL_ID, 0.3)]}}}
    chutes = parse_shotmap(match, meta)
    assert chutes.iloc[0].mando == "fora"
    assert chutes.iloc[0].adversario == "Flamengo"
    assert chutes.iloc[0].do_internacional


def test_gol_contra_e_creditado_ao_adversario(fixtures):
    """Regressão: o FotMob marca gol contra como Goal do time que chutou.

    Sem tratar `isOwnGoal`, o Inter aparecia com 47 gols em vez de 44 e o total
    sofrido caía de 57 para 54.
    """
    meta = team_fixtures(fixtures).iloc[0]
    match = {
        "content": {
            "shotmap": {
                "shots": [
                    _shot(INTERNACIONAL_ID, 0.4),                      # gol do Inter
                    _shot(INTERNACIONAL_ID, None, own=True),           # gol contra
                    _shot(OUTRO_ID, 0.2),                              # gol do adversário
                ]
            }
        }
    }
    chutes = parse_shotmap(match, meta)
    assert chutes.desfecho.tolist() == ["gol", "gol contra", "gol"]
    assert contar_gols(chutes) == (1, 2)


def test_shotmap_ausente_nao_quebra(fixtures):
    meta = team_fixtures(fixtures).iloc[0]
    assert parse_shotmap({"content": {}}, meta).empty
    assert parse_shotmap({}, meta).empty


def test_agregado_por_partida_soma_xg(fixtures):
    inter = team_fixtures(fixtures)
    chutes = pd.concat(
        [
            parse_shotmap(
                {"content": {"shotmap": {"shots": [
                    _shot(INTERNACIONAL_ID, 0.5), _shot(OUTRO_ID, 0.2, event="Miss")
                ]}}},
                inter.iloc[0],
            ),
            parse_shotmap(
                {"content": {"shotmap": {"shots": [
                    _shot(INTERNACIONAL_ID, 1.1), _shot(OUTRO_ID, 0.4, event="Miss")
                ]}}},
                inter.iloc[1],
            ),
        ],
        ignore_index=True,
    )
    agregado = aggregate_por_partida(chutes, inter)
    assert agregado.rodada.tolist() == [1, 2]
    assert agregado.xg_pro.tolist() == [0.5, 1.1]
    assert agregado.xg_contra.tolist() == [0.2, 0.4]
    assert agregado.saldo_xg.tolist() == [0.3, 0.7]
    # mando e placar vêm da tabela de partidas, não do shotmap
    assert agregado.mando.tolist() == ["fora", "casa"]
    assert agregado.gols_pro.tolist() == [1, 3]

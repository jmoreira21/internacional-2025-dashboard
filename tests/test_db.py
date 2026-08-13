"""Testes do schema, da dimensão de times e das views."""

from __future__ import annotations

import sqlite3

import pytest

from src.db.schema import conectar, criar_schema
from src.etl.times import normalizar

TIMES = [
    ("INT", "Internacional", 6600, 8702),
    ("FLA", "Flamengo", 614, 9770),
]


@pytest.fixture
def conexao(tmp_path):
    con = conectar(tmp_path / "teste.db")
    criar_schema(con)
    con.executemany("INSERT INTO times VALUES (?, ?, ?, ?)", TIMES)
    con.commit()
    yield con
    con.close()


# --- normalização de nomes ---------------------------------------------------


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("Atlético-MG", "Atlético Mineiro"),
        ("Atletico MG", "Atlético Mineiro"),
        ("Bragantino", "Red Bull Bragantino"),
        ("Santos", "Santos FC"),
        ("Sport", "Sport Recife"),
        ("São Paulo", "Sao Paulo"),
        ("Grêmio", "Gremio"),
        ("Vitória", "Vitoria"),
        ("Ceará", "Ceara"),
        ("Botafogo", "Botafogo RJ"),
    ],
)
def test_nomes_equivalentes_entre_fontes(a, b):
    """Só 2 dos 20 clubes têm grafia idêntica nas três fontes."""
    assert normalizar(a) == normalizar(b)


def test_nomes_de_clubes_distintos_nao_colidem():
    distintos = ["Internacional", "Flamengo", "Fluminense", "Botafogo",
                 "Bahia", "Vasco da Gama", "Vitória", "Bragantino"]
    chaves = [normalizar(n) for n in distintos]
    assert len(set(chaves)) == len(distintos)


# --- schema ------------------------------------------------------------------


def test_chaves_estrangeiras_estao_ativas(conexao):
    """O PRAGMA vale por conexão: sem ele as FKs seriam só documentação."""
    with pytest.raises(sqlite3.IntegrityError):
        conexao.execute(
            "INSERT INTO partidas (rodada, data, mandante, visitante,"
            " gols_mandante, gols_visitante) VALUES (1, '2025-03-29', 'INT', 'XXX', 1, 1)"
        )


def test_classificacao_rejeita_pontos_inconsistentes(conexao):
    with pytest.raises(sqlite3.IntegrityError):
        conexao.execute(
            "INSERT INTO classificacao VALUES ('INT', 16, 99, 38, 11, 11, 16, 44, 57, -13, '')"
        )


def test_classificacao_rejeita_saldo_inconsistente(conexao):
    with pytest.raises(sqlite3.IntegrityError):
        conexao.execute(
            "INSERT INTO classificacao VALUES ('INT', 16, 44, 38, 11, 11, 16, 44, 57, 0, '')"
        )


def test_partida_nao_pode_ter_o_mesmo_time_dos_dois_lados(conexao):
    with pytest.raises(sqlite3.IntegrityError):
        conexao.execute(
            "INSERT INTO partidas (rodada, data, mandante, visitante,"
            " gols_mandante, gols_visitante) VALUES (1, '2025-03-29', 'INT', 'INT', 1, 1)"
        )


def test_rodada_fora_do_intervalo_e_rejeitada(conexao):
    with pytest.raises(sqlite3.IntegrityError):
        conexao.execute(
            "INSERT INTO partidas (rodada, data, mandante, visitante,"
            " gols_mandante, gols_visitante) VALUES (39, '2025-03-29', 'INT', 'FLA', 1, 1)"
        )


def test_criar_schema_e_idempotente(conexao):
    """Recriar o schema sobre um banco populado não deve falhar nem duplicar."""
    criar_schema(conexao)
    conexao.executemany("INSERT INTO times VALUES (?, ?, ?, ?)", TIMES)
    conexao.commit()
    assert conexao.execute("SELECT COUNT(*) FROM times").fetchone()[0] == 2


# --- views -------------------------------------------------------------------


def _popular_jogos(conexao):
    partidas = [
        (1, "2025-03-29", "FLA", "INT", 1, 1),
        (2, "2025-04-06", "INT", "FLA", 3, 0),
        (3, "2025-04-13", "INT", "FLA", 0, 2),
    ]
    conexao.executemany(
        "INSERT INTO partidas (rodada, data, mandante, visitante,"
        " gols_mandante, gols_visitante) VALUES (?, ?, ?, ?, ?, ?)",
        partidas,
    )
    conexao.execute(
        "INSERT INTO tecnicos (sigla, tecnico, rodada_inicio, rodada_fim, jogos)"
        " VALUES ('INT', 'Roger Machado', 1, 2, 2)"
    )
    conexao.execute(
        "INSERT INTO tecnicos (sigla, tecnico, rodada_inicio, rodada_fim, jogos)"
        " VALUES ('INT', 'Ramón Díaz', 3, 3, 1)"
    )
    conexao.commit()


def test_view_de_jogos_resolve_mando_e_adversario(conexao):
    _popular_jogos(conexao)
    linhas = conexao.execute(
        "SELECT rodada, mando, adversario, gols_pro, gols_contra FROM vw_jogos_inter ORDER BY rodada"
    ).fetchall()
    assert [tuple(linha) for linha in linhas] == [
        (1, "fora", "FLA", 1, 1),
        (2, "casa", "FLA", 3, 0),
        (3, "casa", "FLA", 0, 2),
    ]


def test_view_de_desempenho_por_tecnico_soma_pontos(conexao):
    _popular_jogos(conexao)
    linhas = conexao.execute(
        "SELECT tecnico, jogos, pontos, gols_pro, gols_contra FROM vw_desempenho_tecnico"
    ).fetchall()
    assert [tuple(linha) for linha in linhas] == [
        ("Roger Machado", 2, 4, 4, 1),   # empate + vitória
        ("Ramón Díaz", 1, 0, 0, 2),      # derrota
    ]


def test_view_de_xg_agrega_por_rodada(conexao):
    _popular_jogos(conexao)
    chutes = [
        (1, 111, "2025-03-29", "INT", "FLA", "fora", 0.4),
        (1, 111, "2025-03-29", "FLA", "INT", "fora", 0.9),
        (2, 222, "2025-04-06", "INT", "FLA", "casa", 1.5),
    ]
    conexao.executemany(
        "INSERT INTO chutes (rodada, fotmob_match_id, data, sigla, adversario, mando, xg)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        chutes,
    )
    conexao.commit()
    linhas = conexao.execute(
        "SELECT rodada, xg_pro, xg_contra FROM vw_xg_por_rodada ORDER BY rodada"
    ).fetchall()
    assert [tuple(linha) for linha in linhas] == [(1, 0.4, 0.9), (2, 1.5, 0.0)]

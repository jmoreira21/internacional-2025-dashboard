"""Acesso ao banco pelo dashboard, com cache.

Todas as consultas passam por `consultar`, que é cacheada pelo Streamlit: o
banco é lido uma vez por sessão e as abas reaproveitam os mesmos DataFrames.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.db.schema import conectar
from src.paths import DB_PATH

SIGLA_INTER = "INT"


def banco_existe() -> bool:
    return DB_PATH.exists()


@st.cache_data(show_spinner=False)
def consultar(sql: str, parametros: tuple = ()) -> pd.DataFrame:
    with conectar() as conexao:
        return pd.read_sql_query(sql, conexao, params=parametros)


def jogos_do_inter() -> pd.DataFrame:
    return consultar(
        "SELECT rodada, data, mando, adversario, gols_pro, gols_contra, tecnico,"
        "       gols_pro - gols_contra AS saldo,"
        "       CASE WHEN gols_pro > gols_contra THEN 'V'"
        "            WHEN gols_pro = gols_contra THEN 'E' ELSE 'D' END AS resultado,"
        "       CASE WHEN gols_pro > gols_contra THEN 3"
        "            WHEN gols_pro = gols_contra THEN 1 ELSE 0 END AS pontos"
        "  FROM vw_jogos_inter ORDER BY rodada"
    )


def posicoes_por_rodada() -> pd.DataFrame:
    return consultar(
        "SELECT p.rodada, p.sigla, t.nome, p.posicao"
        "  FROM posicoes_rodada p JOIN times t ON t.sigla = p.sigla"
        " ORDER BY p.rodada, p.posicao"
    )


def classificacao() -> pd.DataFrame:
    return consultar(
        "SELECT c.posicao, c.sigla, t.nome, c.pontos, c.jogos, c.vitorias, c.empates,"
        "       c.derrotas, c.gols_pro, c.gols_contra, c.saldo, c.situacao"
        "  FROM classificacao c JOIN times t ON t.sigla = c.sigla"
        " ORDER BY c.posicao"
    )


def desempenho_tecnicos() -> pd.DataFrame:
    return consultar(
        "SELECT tecnico, rodada_inicio, rodada_fim, jogos, pontos, gols_pro, gols_contra,"
        "       ROUND(100.0 * pontos / (jogos * 3), 1) AS aproveitamento"
        "  FROM vw_desempenho_tecnico"
    )


def xg_por_rodada() -> pd.DataFrame:
    return consultar("SELECT * FROM vw_xg_por_rodada ORDER BY rodada")


def xg_dos_times() -> pd.DataFrame:
    return consultar(
        "SELECT x.sigla, t.nome, c.posicao, x.pontos, x.pontos_esperados,"
        "       x.gols_pro, x.xg, x.gols_contra, x.xg_contra,"
        "       x.eficiencia_ataque, x.eficiencia_defesa,"
        "       x.pontos - x.pontos_esperados AS diferenca_pontos"
        "  FROM xg_times x"
        "  JOIN times t ON t.sigla = x.sigla"
        "  JOIN classificacao c ON c.sigla = x.sigla"
        " ORDER BY c.posicao"
    )


def chutes(apenas_inter: bool = True) -> pd.DataFrame:
    filtro = "WHERE sigla = 'INT'" if apenas_inter else ""
    return consultar(
        "SELECT rodada, sigla, adversario, mando, jogador, minuto, x, y, xg, xgot,"
        "       desfecho, tipo_chute, situacao, dentro_area, no_alvo"
        f"  FROM chutes {filtro} ORDER BY rodada, minuto"
    )


def jogadores() -> pd.DataFrame:
    return consultar(
        "SELECT jogador, posicao, jogos, titular, minutos, gols, assistencias,"
        "       chutes, chutes_no_alvo, amarelos, vermelhos"
        "  FROM jogadores WHERE sigla = 'INT' AND jogos > 0"
        " ORDER BY gols DESC, minutos DESC"
    )


def tem_jogadores() -> bool:
    """O FBref é coleta manual: as abas que dependem dele degradam sem quebrar."""
    return not consultar("SELECT COUNT(*) AS n FROM jogadores").empty and bool(
        consultar("SELECT COUNT(*) AS n FROM jogadores").n.iloc[0]
    )

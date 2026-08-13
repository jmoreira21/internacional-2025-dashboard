"""Schema do banco SQLite.

O banco é descartável: é reconstruído inteiro a partir dos CSVs de `data/raw/`,
por isso está no .gitignore. As chaves estrangeiras são declaradas e ativadas
(`PRAGMA foreign_keys`), de modo que um erro no cruzamento de times entre fontes
falha na carga em vez de virar um JOIN vazio silencioso mais adiante.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from src.paths import DB_PATH

# Ordem importa: as tabelas com chave estrangeira vêm depois de `times`.
TABELAS = {
    "times": """
        CREATE TABLE times (
            sigla      TEXT    PRIMARY KEY,
            nome       TEXT    NOT NULL UNIQUE,
            tm_id      INTEGER NOT NULL UNIQUE,
            fotmob_id  INTEGER NOT NULL UNIQUE
        )
    """,
    "partidas": """
        CREATE TABLE partidas (
            id             INTEGER PRIMARY KEY,
            rodada         INTEGER NOT NULL CHECK (rodada BETWEEN 1 AND 38),
            data           TEXT    NOT NULL,
            mandante       TEXT    NOT NULL REFERENCES times(sigla),
            visitante      TEXT    NOT NULL REFERENCES times(sigla),
            gols_mandante  INTEGER NOT NULL CHECK (gols_mandante >= 0),
            gols_visitante INTEGER NOT NULL CHECK (gols_visitante >= 0),
            tm_match_id    INTEGER UNIQUE,
            UNIQUE (rodada, mandante, visitante),
            CHECK (mandante <> visitante)
        )
    """,
    "classificacao": """
        CREATE TABLE classificacao (
            sigla       TEXT    PRIMARY KEY REFERENCES times(sigla),
            posicao     INTEGER NOT NULL UNIQUE CHECK (posicao BETWEEN 1 AND 20),
            pontos      INTEGER NOT NULL,
            jogos       INTEGER NOT NULL,
            vitorias    INTEGER NOT NULL,
            empates     INTEGER NOT NULL,
            derrotas    INTEGER NOT NULL,
            gols_pro    INTEGER NOT NULL,
            gols_contra INTEGER NOT NULL,
            saldo       INTEGER NOT NULL,
            situacao    TEXT,
            CHECK (pontos = vitorias * 3 + empates),
            CHECK (saldo = gols_pro - gols_contra)
        )
    """,
    "posicoes_rodada": """
        CREATE TABLE posicoes_rodada (
            rodada  INTEGER NOT NULL CHECK (rodada BETWEEN 1 AND 38),
            sigla   TEXT    NOT NULL REFERENCES times(sigla),
            posicao INTEGER NOT NULL CHECK (posicao BETWEEN 1 AND 20),
            PRIMARY KEY (rodada, sigla)
        )
    """,
    "tecnicos": """
        CREATE TABLE tecnicos (
            id             INTEGER PRIMARY KEY,
            sigla          TEXT    NOT NULL REFERENCES times(sigla),
            tecnico        TEXT    NOT NULL,
            rodada_inicio  INTEGER NOT NULL,
            rodada_fim     INTEGER NOT NULL,
            jogos          INTEGER NOT NULL,
            data_saida     TEXT,
            ultima_partida TEXT,
            posicao_saida  INTEGER,
            UNIQUE (sigla, rodada_inicio),
            CHECK (rodada_fim >= rodada_inicio)
        )
    """,
    "xg_times": """
        CREATE TABLE xg_times (
            sigla             TEXT PRIMARY KEY REFERENCES times(sigla),
            pontos            INTEGER NOT NULL,
            pontos_esperados  REAL NOT NULL,
            gols_pro          INTEGER NOT NULL,
            xg                REAL NOT NULL,
            gols_contra       INTEGER NOT NULL,
            xg_contra         REAL NOT NULL,
            eficiencia_ataque REAL NOT NULL,
            eficiencia_defesa REAL NOT NULL
        )
    """,
    "chutes": """
        CREATE TABLE chutes (
            id              INTEGER PRIMARY KEY,
            rodada          INTEGER NOT NULL CHECK (rodada BETWEEN 1 AND 38),
            fotmob_match_id INTEGER NOT NULL,
            data            TEXT,
            sigla           TEXT NOT NULL REFERENCES times(sigla),
            adversario      TEXT NOT NULL REFERENCES times(sigla),
            mando           TEXT CHECK (mando IN ('casa', 'fora')),
            jogador         TEXT,
            minuto          INTEGER,
            x               REAL,
            y               REAL,
            xg              REAL,
            xgot            REAL,
            desfecho        TEXT,
            tipo_chute      TEXT,
            situacao        TEXT,
            dentro_area     INTEGER,
            no_alvo         INTEGER,
            bloqueado       INTEGER,
            gol_contra      INTEGER
        )
    """,
    "jogadores": """
        CREATE TABLE jogadores (
            id             INTEGER PRIMARY KEY,
            sigla          TEXT NOT NULL REFERENCES times(sigla),
            jogador        TEXT NOT NULL,
            posicao        TEXT,
            nacionalidade  TEXT,
            idade          INTEGER,
            jogos          INTEGER,
            titular        INTEGER,
            minutos        INTEGER,
            gols           INTEGER,
            assistencias   INTEGER,
            chutes         INTEGER,
            chutes_no_alvo INTEGER,
            amarelos       INTEGER,
            vermelhos      INTEGER,
            UNIQUE (sigla, jogador)
        )
    """,
}

INDICES = [
    "CREATE INDEX idx_partidas_rodada ON partidas(rodada)",
    "CREATE INDEX idx_partidas_mandante ON partidas(mandante)",
    "CREATE INDEX idx_partidas_visitante ON partidas(visitante)",
    "CREATE INDEX idx_chutes_rodada ON chutes(rodada)",
    "CREATE INDEX idx_chutes_sigla ON chutes(sigla)",
    "CREATE INDEX idx_posicoes_sigla ON posicoes_rodada(sigla)",
]

# Consultas frequentes, expostas como views para uso direto em SQL.
VIEWS = {
    "vw_jogos_inter": """
        CREATE VIEW vw_jogos_inter AS
        SELECT
            p.rodada,
            p.data,
            CASE WHEN p.mandante = 'INT' THEN 'casa' ELSE 'fora' END AS mando,
            CASE WHEN p.mandante = 'INT' THEN p.visitante ELSE p.mandante END AS adversario,
            CASE WHEN p.mandante = 'INT' THEN p.gols_mandante ELSE p.gols_visitante END AS gols_pro,
            CASE WHEN p.mandante = 'INT' THEN p.gols_visitante ELSE p.gols_mandante END AS gols_contra,
            t.tecnico
        FROM partidas p
        LEFT JOIN tecnicos t
               ON t.sigla = 'INT'
              AND p.rodada BETWEEN t.rodada_inicio AND t.rodada_fim
        WHERE p.mandante = 'INT' OR p.visitante = 'INT'
    """,
    "vw_xg_por_rodada": """
        CREATE VIEW vw_xg_por_rodada AS
        SELECT
            j.rodada,
            j.mando,
            j.adversario,
            j.gols_pro,
            j.gols_contra,
            ROUND(SUM(CASE WHEN c.sigla = 'INT' THEN c.xg ELSE 0 END), 2) AS xg_pro,
            ROUND(SUM(CASE WHEN c.sigla <> 'INT' THEN c.xg ELSE 0 END), 2) AS xg_contra
        FROM vw_jogos_inter j
        JOIN chutes c ON c.rodada = j.rodada
        GROUP BY j.rodada, j.mando, j.adversario, j.gols_pro, j.gols_contra
    """,
    "vw_desempenho_tecnico": """
        CREATE VIEW vw_desempenho_tecnico AS
        SELECT
            t.tecnico,
            t.rodada_inicio,
            t.rodada_fim,
            COUNT(*)                                            AS jogos,
            SUM(CASE WHEN j.gols_pro >  j.gols_contra THEN 3
                     WHEN j.gols_pro =  j.gols_contra THEN 1
                     ELSE 0 END)                                AS pontos,
            SUM(j.gols_pro)                                     AS gols_pro,
            SUM(j.gols_contra)                                  AS gols_contra
        FROM tecnicos t
        JOIN vw_jogos_inter j
          ON j.rodada BETWEEN t.rodada_inicio AND t.rodada_fim
        WHERE t.sigla = 'INT'
        GROUP BY t.tecnico, t.rodada_inicio, t.rodada_fim
        ORDER BY t.rodada_inicio
    """,
}


def conectar(caminho: Path = DB_PATH) -> sqlite3.Connection:
    """Abre a conexão com chaves estrangeiras ativas.

    O SQLite exige o PRAGMA em cada conexão — sem ele, as FKs declaradas no
    schema são apenas documentação.
    """
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(caminho)
    conexao.execute("PRAGMA foreign_keys = ON")
    conexao.row_factory = sqlite3.Row
    return conexao


def criar_schema(conexao: sqlite3.Connection) -> None:
    """Recria o schema do zero, tornando a carga idempotente."""
    for nome in VIEWS:
        conexao.execute(f"DROP VIEW IF EXISTS {nome}")
    for nome in reversed(list(TABELAS)):
        conexao.execute(f"DROP TABLE IF EXISTS {nome}")

    for ddl in TABELAS.values():
        conexao.execute(ddl)
    for ddl in INDICES:
        conexao.execute(ddl)
    for ddl in VIEWS.values():
        conexao.execute(ddl)
    conexao.commit()

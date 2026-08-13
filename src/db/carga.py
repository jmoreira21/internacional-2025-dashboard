"""Carga dos CSVs de data/raw/ no SQLite.

A carga é idempotente por reconstrução: o schema é recriado do zero a cada
execução, de modo que rodar duas vezes produz exatamente o mesmo banco. Como o
banco é derivado dos CSVs e não é versionado, essa é a estratégia mais simples
e a que não deixa resíduo de execuções anteriores.

Uso:
    poetry run python -m src.db.carga
"""

from __future__ import annotations

import sqlite3
import sys

import pandas as pd

from src.db.schema import conectar, criar_schema
from src.etl.times import construir_dimensao, normalizar
from src.paths import DB_PATH, RAW

TEAM = "Internacional"
SIGLA_INTER = "INT"


def _ler(nome: str) -> pd.DataFrame:
    return pd.read_csv(RAW / nome, encoding="utf-8-sig")


def _existe(nome: str) -> bool:
    return (RAW / nome).exists()


def _mapa_por_nome(dimensao: pd.DataFrame) -> dict[str, str]:
    """Chave normalizada -> sigla, para resolver nomes de qualquer fonte."""
    return {normalizar(nome): sigla for nome, sigla in zip(dimensao.nome, dimensao.sigla)}


def _mapa_por_tm_id(dimensao: pd.DataFrame) -> dict[int, str]:
    return dict(zip(dimensao.tm_id, dimensao.sigla))


def carregar_times(conexao: sqlite3.Connection, dimensao: pd.DataFrame) -> int:
    dimensao.to_sql("times", conexao, if_exists="append", index=False)
    return len(dimensao)


def carregar_partidas(conexao: sqlite3.Connection, dimensao: pd.DataFrame) -> int:
    por_id = _mapa_por_tm_id(dimensao)
    partidas = _ler("brasileirao_2025_partidas.csv")

    frame = pd.DataFrame(
        {
            "rodada": partidas.rodada,
            "data": partidas.data,
            "mandante": partidas.mandante_id.map(por_id),
            "visitante": partidas.visitante_id.map(por_id),
            "gols_mandante": partidas.gols_mandante,
            "gols_visitante": partidas.gols_visitante,
            "tm_match_id": partidas.match_id,
        }
    )
    if frame[["mandante", "visitante"]].isna().any().any():
        raise ValueError("partidas com time não mapeado para sigla")

    frame.to_sql("partidas", conexao, if_exists="append", index=False)
    return len(frame)


def carregar_classificacao(conexao: sqlite3.Connection, dimensao: pd.DataFrame) -> int:
    por_nome = _mapa_por_nome(dimensao)
    tabela = _ler("brasileirao_2025_classificacao.csv")
    tabela = tabela.assign(sigla=tabela.equipe.map(lambda n: por_nome[normalizar(n)]))
    colunas = ["sigla", "posicao", "pontos", "jogos", "vitorias", "empates",
               "derrotas", "gols_pro", "gols_contra", "saldo", "situacao"]
    tabela[colunas].to_sql("classificacao", conexao, if_exists="append", index=False)
    return len(tabela)


def carregar_posicoes(conexao: sqlite3.Connection, dimensao: pd.DataFrame) -> int:
    posicoes = _ler("brasileirao_2025_pos_por_rodada.csv")
    frame = posicoes[["rodada", "sigla", "posicao"]]
    frame.to_sql("posicoes_rodada", conexao, if_exists="append", index=False)
    return len(frame)


def carregar_tecnicos(conexao: sqlite3.Connection) -> int:
    tecnicos = _ler("inter_2025_tecnicos.csv").assign(sigla=SIGLA_INTER)
    colunas = ["sigla", "tecnico", "rodada_inicio", "rodada_fim", "jogos",
               "data_saida", "ultima_partida", "posicao_saida"]
    tecnicos[colunas].to_sql("tecnicos", conexao, if_exists="append", index=False)
    return len(tecnicos)


def carregar_xg_times(conexao: sqlite3.Connection, dimensao: pd.DataFrame) -> int:
    por_nome = _mapa_por_nome(dimensao)
    xg = _ler("brasileirao_2025_xg_tabela.csv")
    xg = xg.assign(sigla=xg.equipe.map(lambda n: por_nome[normalizar(n)]))
    colunas = ["sigla", "pontos", "pontos_esperados", "gols_pro", "xg",
               "gols_contra", "xg_contra", "eficiencia_ataque", "eficiencia_defesa"]
    xg[colunas].to_sql("xg_times", conexao, if_exists="append", index=False)
    return len(xg)


def carregar_chutes(conexao: sqlite3.Connection, dimensao: pd.DataFrame) -> int:
    por_nome = _mapa_por_nome(dimensao)
    chutes = _ler("inter_2025_chutes.csv")

    frame = pd.DataFrame(
        {
            "rodada": chutes.rodada,
            "fotmob_match_id": chutes.match_id,
            "data": chutes.data,
            "sigla": chutes.equipe.map(lambda n: por_nome.get(normalizar(n))),
            "adversario": chutes.adversario.map(lambda n: por_nome.get(normalizar(n))),
            "mando": chutes.mando,
            "jogador": chutes.jogador,
            "minuto": chutes.minuto,
            "x": chutes.x,
            "y": chutes.y,
            "xg": chutes.xg,
            "xgot": chutes.xgot,
            "desfecho": chutes.desfecho,
            "tipo_chute": chutes.tipo_chute,
            "situacao": chutes.situacao,
            "dentro_area": chutes.dentro_area.astype("boolean").astype("Int64"),
            "no_alvo": chutes.no_alvo.astype("boolean").astype("Int64"),
            "bloqueado": chutes.bloqueado.astype("boolean").astype("Int64"),
            "gol_contra": chutes.gol_contra.astype("boolean").astype("Int64"),
        }
    )
    nao_mapeados = frame[frame.sigla.isna() | frame.adversario.isna()]
    if not nao_mapeados.empty:
        raise ValueError(
            "chutes com time não mapeado: "
            + str(sorted(set(chutes.loc[nao_mapeados.index, "equipe"])))
        )

    frame.to_sql("chutes", conexao, if_exists="append", index=False)
    return len(frame)


def carregar_jogadores(conexao: sqlite3.Connection) -> int:
    """Estatísticas por jogador do FBref; opcional, depende de HTML salvo."""
    if not (_existe("inter_2025_fbref_standard.csv")
            and _existe("inter_2025_fbref_shooting.csv")):
        return 0

    padrao = _ler("inter_2025_fbref_standard.csv")
    chutes = _ler("inter_2025_fbref_shooting.csv")

    # A última linha das tabelas do FBref é o total da equipe, não um jogador.
    padrao = padrao[padrao.player.notna() & (padrao.get("games").notna())]
    juntos = padrao.merge(
        chutes[["player", "shots", "shots_on_target"]], on="player", how="left"
    )

    frame = pd.DataFrame(
        {
            "sigla": SIGLA_INTER,
            "jogador": juntos.player,
            "posicao": juntos.get("position"),
            "nacionalidade": juntos.get("nationality"),
            "idade": pd.to_numeric(juntos.get("age"), errors="coerce"),
            "jogos": juntos.get("games"),
            "titular": juntos.get("games_starts"),
            "minutos": pd.to_numeric(
                juntos.get("minutes").astype(str).str.replace(",", ""), errors="coerce"
            ),
            "gols": juntos.get("goals"),
            "assistencias": juntos.get("assists"),
            "chutes": juntos.get("shots"),
            "chutes_no_alvo": juntos.get("shots_on_target"),
            "amarelos": juntos.get("cards_yellow"),
            "vermelhos": juntos.get("cards_red"),
        }
    ).drop_duplicates(subset="jogador")

    frame.to_sql("jogadores", conexao, if_exists="append", index=False)
    return len(frame)


def main() -> int:
    obrigatorios = [
        "brasileirao_2025_partidas.csv",
        "brasileirao_2025_classificacao.csv",
        "brasileirao_2025_pos_por_rodada.csv",
        "inter_2025_tecnicos.csv",
        "brasileirao_2025_xg_tabela.csv",
        "inter_2025_chutes.csv",
    ]
    faltando = [nome for nome in obrigatorios if not _existe(nome)]
    if faltando:
        print("CSVs ausentes: " + ", ".join(faltando), file=sys.stderr)
        print("Rode os coletores em src/scraper/ antes da carga.", file=sys.stderr)
        return 1

    dimensao = construir_dimensao()

    with conectar() as conexao:
        criar_schema(conexao)

        cargas = [
            ("times", carregar_times(conexao, dimensao)),
            ("partidas", carregar_partidas(conexao, dimensao)),
            ("classificacao", carregar_classificacao(conexao, dimensao)),
            ("posicoes_rodada", carregar_posicoes(conexao, dimensao)),
            ("tecnicos", carregar_tecnicos(conexao)),
            ("xg_times", carregar_xg_times(conexao, dimensao)),
            ("chutes", carregar_chutes(conexao, dimensao)),
            ("jogadores", carregar_jogadores(conexao)),
        ]
        conexao.commit()

        print(f"Banco: {DB_PATH}")
        for tabela, linhas in cargas:
            aviso = "  (FBref não coletado)" if tabela == "jogadores" and not linhas else ""
            print(f"  {tabela:<18}{linhas:>5} linhas{aviso}")

        violacoes = conexao.execute("PRAGMA foreign_key_check").fetchall()
        if violacoes:
            print(f"\nERRO: {len(violacoes)} violações de chave estrangeira", file=sys.stderr)
            return 1
        print("\nIntegridade referencial: OK")

    # Fora da transação: compacta as páginas liberadas pelo DROP/CREATE.
    conexao = conectar()
    conexao.execute("VACUUM")
    conexao.close()
    print(f"Tamanho do banco: {DB_PATH.stat().st_size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

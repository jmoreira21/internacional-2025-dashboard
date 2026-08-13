"""Dimensão de times: cruza as quatro fontes num identificador único.

Cada fonte escreve o nome do clube de um jeito — "Atlético-MG" no
Transfermarkt, "Atlético Mineiro" na Wikipédia, "Atletico MG" no FotMob — e
apenas 2 dos 20 clubes têm grafia idêntica nas três. O cruzamento é feito por
uma chave normalizada (sem acentos, sem sufixos de estado ou de patrocínio), e
qualquer clube que não case nas três fontes derruba a construção com erro
explícito, em vez de sumir silenciosamente de um JOIN.

O nome canônico adotado é o da Wikipédia, por ser o mais correto em português.
"""

from __future__ import annotations

import re
import unicodedata

import pandas as pd

from src.paths import RAW

TOTAL_TEAMS = 20

# Tokens que aparecem em algumas fontes e não em outras: sufixo de estado,
# forma jurídica e nome de patrocinador.
_RUIDO = {"fc", "ec", "sc", "ac", "rj", "sp", "mg", "rs", "ce", "pe", "ba",
          "red", "bull", "recife", "futebol", "clube", "de", "do", "da"}

# Casos que a normalização por token não resolve sozinha.
_ALIASES = {
    "atletico mineiro": "atletico",
    "atletico": "atletico",
    "bragantino": "bragantino",
    "vasco gama": "vasco",
    "vasco": "vasco",
}


def normalizar(nome: str) -> str:
    """Reduz o nome do clube a uma chave comparável entre fontes.

    >>> normalizar("Atlético-MG") == normalizar("Atlético Mineiro")
    True
    >>> normalizar("Bragantino") == normalizar("Red Bull Bragantino")
    True
    """
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", nome)
        if unicodedata.category(c) != "Mn"
    )
    limpo = re.sub(r"[^a-z0-9\s]", " ", sem_acento.casefold())
    tokens = [t for t in limpo.split() if t not in _RUIDO]
    chave = " ".join(tokens)
    return _ALIASES.get(chave, chave)


def _carregar(nome_arquivo: str) -> pd.DataFrame:
    return pd.read_csv(RAW / nome_arquivo, encoding="utf-8-sig")


def construir_dimensao() -> pd.DataFrame:
    """Monta a tabela de times com os identificadores de cada fonte.

    Colunas: sigla, nome, tm_id, fotmob_id.
    """
    posicoes = _carregar("brasileirao_2025_pos_por_rodada.csv")
    partidas = _carregar("brasileirao_2025_partidas.csv")
    xg = _carregar("brasileirao_2025_xg_tabela.csv")

    base = (
        posicoes[["sigla", "equipe"]]
        .drop_duplicates()
        .rename(columns={"equipe": "nome"})
        .assign(chave=lambda d: d.nome.map(normalizar))
    )

    transfermarkt = (
        pd.concat([
            partidas[["mandante", "mandante_id"]].rename(
                columns={"mandante": "nome_tm", "mandante_id": "tm_id"}),
            partidas[["visitante", "visitante_id"]].rename(
                columns={"visitante": "nome_tm", "visitante_id": "tm_id"}),
        ])
        .drop_duplicates()
        .assign(chave=lambda d: d.nome_tm.map(normalizar))
    )

    fotmob = (
        xg[["equipe", "team_id"]]
        .rename(columns={"equipe": "nome_fm", "team_id": "fotmob_id"})
        .assign(chave=lambda d: d.nome_fm.map(normalizar))
    )

    for rotulo, frame in (("Wikipédia", base), ("Transfermarkt", transfermarkt),
                          ("FotMob", fotmob)):
        if len(frame) != TOTAL_TEAMS:
            raise ValueError(
                f"{rotulo}: {len(frame)} times após normalizar, esperado {TOTAL_TEAMS}. "
                f"Chaves duplicadas: {frame.chave[frame.chave.duplicated()].tolist()}"
            )

    dimensao = base.merge(transfermarkt, on="chave", how="outer", indicator="_tm")
    faltando_tm = dimensao[dimensao._tm != "both"]
    if not faltando_tm.empty:
        raise ValueError(
            "times sem correspondência entre Wikipédia e Transfermarkt: "
            + str(faltando_tm[["nome", "nome_tm", "chave"]].to_dict("records"))
        )

    dimensao = dimensao.drop(columns="_tm").merge(
        fotmob, on="chave", how="outer", indicator="_fm"
    )
    faltando_fm = dimensao[dimensao._fm != "both"]
    if not faltando_fm.empty:
        raise ValueError(
            "times sem correspondência com o FotMob: "
            + str(faltando_fm[["nome", "nome_fm", "chave"]].to_dict("records"))
        )

    return (
        dimensao.drop(columns=["_fm", "chave", "nome_tm", "nome_fm"])
        .astype({"tm_id": "int64", "fotmob_id": "int64"})
        .sort_values("nome", ignore_index=True)
    )


if __name__ == "__main__":
    dimensao = construir_dimensao()
    print(dimensao.to_string(index=False))
    print(f"\n{len(dimensao)} times cruzados nas três fontes.")

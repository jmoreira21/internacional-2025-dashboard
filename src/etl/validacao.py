"""Relatório de qualidade dos dados brutos coletados.

Roda todas as checagens de integridade e reconciliação de uma vez e imprime um
resumo legível, para conferir os CSVs de `data/raw/` antes de avançar para o
schema do banco e o dashboard.

Encerra com código 1 se qualquer checagem falhar, o que também o torna
utilizável como passo de verificação em automações.

Uso:
    poetry run python -m src.etl.validacao
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

import pandas as pd

from src.paths import RAW
from src.scraper import fbref_parser

TOTAL_ROUNDS = 38
TOTAL_TEAMS = 20
TOTAL_MATCHES = 380
TEAM = "Internacional"

ARQUIVOS = {
    "fixtures": "inter_2025_fixtures.csv",
    "partidas": "brasileirao_2025_partidas.csv",
    "classificacao": "brasileirao_2025_classificacao.csv",
    "pos_rodada": "brasileirao_2025_pos_por_rodada.csv",
    "artilharia": "brasileirao_2025_artilharia.csv",
    "assistencias": "brasileirao_2025_assistencias.csv",
    "tecnicos": "inter_2025_tecnicos.csv",
    "mudancas": "brasileirao_2025_mudancas_tecnicos.csv",
}

# Coletados do FotMob; ausentes até rodar `python -m src.scraper.fotmob`.
ARQUIVOS_XG = {
    "xg_tabela": "brasileirao_2025_xg_tabela.csv",
    "chutes": "inter_2025_chutes.csv",
    "xg_partida": "inter_2025_xg_por_partida.csv",
}


@dataclass
class Check:
    nome: str
    ok: bool
    detalhe: str = ""

    def render(self) -> str:
        marca = "OK   " if self.ok else "FALHA"
        sufixo = f"  ({self.detalhe})" if self.detalhe else ""
        return f"  [{marca}] {self.nome}{sufixo}"


def _titulo(texto: str) -> None:
    print(f"\n{texto}\n{'-' * len(texto)}")


def carregar() -> dict[str, pd.DataFrame]:
    faltando = [nome for nome, arq in ARQUIVOS.items() if not (RAW / arq).exists()]
    if faltando:
        print("Arquivos ausentes em data/raw/: " + ", ".join(faltando), file=sys.stderr)
        print(
            "\nRode os coletores primeiro:\n"
            "  poetry run python -m src.scraper.transfermarkt\n"
            "  poetry run python -m src.scraper.wikipedia",
            file=sys.stderr,
        )
        raise SystemExit(1)
    dados = {
        nome: pd.read_csv(RAW / arq, encoding="utf-8-sig")
        for nome, arq in ARQUIVOS.items()
    }
    for nome, arq in ARQUIVOS_XG.items():
        if (RAW / arq).exists():
            dados[nome] = pd.read_csv(RAW / arq, encoding="utf-8-sig")
    return dados


def checar_integridade(d: dict[str, pd.DataFrame]) -> list[Check]:
    fixtures, partidas = d["fixtures"], d["partidas"]
    classificacao, pos = d["classificacao"], d["pos_rodada"]

    jogos_por_time = pd.concat([partidas.mandante_id, partidas.visitante_id]).value_counts()

    return [
        Check("380 partidas no campeonato", len(partidas) == TOTAL_MATCHES, f"{len(partidas)}"),
        Check("20 times", partidas.mandante_id.nunique() == TOTAL_TEAMS),
        Check("38 jogos para cada time", set(jogos_por_time) == {TOTAL_ROUNDS}),
        Check("match_id único por partida", partidas.match_id.nunique() == len(partidas)),
        Check("38 jogos do Inter", len(fixtures) == TOTAL_ROUNDS, f"{len(fixtures)}"),
        Check("rodadas 1-38 sem buracos", sorted(fixtures.rodada) == list(range(1, 39))),
        Check(
            "19 jogos em casa e 19 fora",
            fixtures.mando.value_counts().to_dict() == {"casa": 19, "fora": 19},
        ),
        Check("sem placar nulo", not fixtures[["gols_pro", "gols_contra"]].isna().any().any()),
        Check("classificação com 20 linhas", len(classificacao) == TOTAL_TEAMS),
        Check("soma dos saldos é zero", int(classificacao.saldo.sum()) == 0),
        Check(
            "gols marcados = gols sofridos no total",
            int(classificacao.gols_pro.sum()) == int(classificacao.gols_contra.sum()),
            f"{int(classificacao.gols_pro.sum())}",
        ),
        Check(
            "pontos = 3V + E para todos os times",
            bool((classificacao.pontos == classificacao.vitorias * 3 + classificacao.empates).all()),
        ),
        Check("posição por rodada com 38x20 linhas", len(pos) == TOTAL_ROUNDS * TOTAL_TEAMS),
    ]


def checar_reconciliacao(d: dict[str, pd.DataFrame]) -> list[Check]:
    """Cruza fontes independentes: Transfermarkt x Wikipédia."""
    fixtures, classificacao, pos = d["fixtures"], d["classificacao"], d["pos_rodada"]
    oficial = classificacao.query("equipe == @TEAM").iloc[0]

    contagem = fixtures.resultado.value_counts()
    vitorias, empates, derrotas = (int(contagem.get(k, 0)) for k in "VED")
    marcados, sofridos = int(fixtures.gols_pro.sum()), int(fixtures.gols_contra.sum())
    pontos = vitorias * 3 + empates

    final_por_rodada = pos.query("rodada == @TOTAL_ROUNDS").set_index("equipe").posicao
    fecha_com_tabela = (
        final_por_rodada.sort_index()
        .eq(classificacao.set_index("equipe").posicao.sort_index())
        .all()
    )

    tecnicos = d["tecnicos"]
    contiguo = (
        tecnicos.rodada_inicio.iloc[0] == 1
        and tecnicos.rodada_fim.iloc[-1] == TOTAL_ROUNDS
        and int(tecnicos.jogos.sum()) == TOTAL_ROUNDS
    )

    return [
        Check("vitórias batem com a tabela", vitorias == int(oficial.vitorias),
              f"{vitorias} vs {int(oficial.vitorias)}"),
        Check("empates batem", empates == int(oficial.empates), f"{empates} vs {int(oficial.empates)}"),
        Check("derrotas batem", derrotas == int(oficial.derrotas),
              f"{derrotas} vs {int(oficial.derrotas)}"),
        Check("gols marcados batem", marcados == int(oficial.gols_pro),
              f"{marcados} vs {int(oficial.gols_pro)}"),
        Check("gols sofridos batem", sofridos == int(oficial.gols_contra),
              f"{sofridos} vs {int(oficial.gols_contra)}"),
        Check("pontos batem", pontos == int(oficial.pontos), f"{pontos} vs {int(oficial.pontos)}"),
        Check("posição da rodada 38 = classificação final (20 times)", bool(fecha_com_tabela)),
        Check("técnicos cobrem as rodadas 1-38 sem buraco", bool(contiguo)),
    ]


def resumo_do_inter(d: dict[str, pd.DataFrame]) -> None:
    fixtures, classificacao = d["fixtures"], d["classificacao"]
    oficial = classificacao.query("equipe == @TEAM").iloc[0]
    dezessete = classificacao.query("posicao == 17").iloc[0]

    _titulo("RESUMO DO INTERNACIONAL EM 2025")
    print(
        f"  {int(oficial.posicao)}º lugar, {int(oficial.pontos)} pts  "
        f"({int(oficial.vitorias)}V {int(oficial.empates)}E {int(oficial.derrotas)}D, "
        f"{int(oficial.gols_pro)}:{int(oficial.gols_contra)}, saldo {int(oficial.saldo):+d})"
    )
    print(
        f"  Escapou do rebaixamento por {int(oficial.pontos) - int(dezessete.pontos)} ponto(s) "
        f"sobre o {dezessete.equipe} ({int(dezessete.pontos)} pts)"
    )

    inter_pos = d["pos_rodada"].query("equipe == @TEAM").sort_values("rodada")
    no_z4 = inter_pos.query("posicao >= 17")
    print(
        f"  Pior posição no ano: {int(inter_pos.posicao.max())}º  |  "
        f"rodadas dentro do Z4: {len(no_z4)}"
        + (f" (rodadas {', '.join(map(str, no_z4.rodada))})" if len(no_z4) else "")
    )

    casa = fixtures.query("mando == 'casa'")
    fora = fixtures.query("mando == 'fora'")
    for nome, recorte in (("Em casa", casa), ("Fora", fora)):
        pontos = int((recorte.resultado == "V").sum()) * 3 + int((recorte.resultado == "E").sum())
        print(
            f"  {nome:<8} {pontos:>2} pts em {len(recorte) * 3}  "
            f"({pontos / (len(recorte) * 3):.1%})  "
            f"{int(recorte.gols_pro.sum())}:{int(recorte.gols_contra.sum())}"
        )

    _titulo("DESEMPENHO POR TÉCNICO")
    print(f"  {'Técnico':<16}{'Rodadas':<10}{'J':>3}{'Pts':>5}{'Aprov.':>9}{'Gols':>9}")
    for _, periodo in d["tecnicos"].iterrows():
        recorte = fixtures.query(
            "rodada >= @periodo.rodada_inicio and rodada <= @periodo.rodada_fim"
        )
        pontos = int((recorte.resultado == "V").sum()) * 3 + int((recorte.resultado == "E").sum())
        maximo = len(recorte) * 3
        print(
            f"  {periodo.tecnico:<16}"
            f"{f'{periodo.rodada_inicio}-{periodo.rodada_fim}':<10}"
            f"{len(recorte):>3}{pontos:>5}{pontos / maximo:>8.1%}"
            f"{f'{int(recorte.gols_pro.sum())}:{int(recorte.gols_contra.sum())}':>9}"
        )
    print("\n  Atenção: Abel Braga dirigiu apenas 2 jogos — amostra pequena demais")
    print("  para comparação estatística com os outros dois.")

    _titulo("JOGADORES DO INTER NOS RANKINGS DO CAMPEONATO")
    encontrou = False
    for rotulo, chave, metrica in (
        ("Artilharia", "artilharia", "gols"),
        ("Assistências", "assistencias", "assistencias"),
    ):
        for _, linha in d[chave].query("equipe == @TEAM").iterrows():
            print(f"  {rotulo:<14} {int(linha.posicao):>2}º  {linha.jogador} — "
                  f"{int(linha[metrica])} {metrica}")
            encontrou = True
    if not encontrou:
        print("  (nenhum)")


def checar_xg(d: dict[str, pd.DataFrame]) -> list[Check]:
    """Checagens do FotMob; lista vazia se o coletor de xG ainda não rodou."""
    if "chutes" not in d:
        return []

    chutes, por_partida, tabela = d["chutes"], d["xg_partida"], d["xg_tabela"]
    do_inter = chutes.do_internacional

    marcados = int((do_inter & (chutes.desfecho == "gol")).sum())
    sofridos = int(
        ((~do_inter) & (chutes.desfecho == "gol")).sum()
        + (do_inter & (chutes.desfecho == "gol contra")).sum()
    )
    oficial = d["classificacao"].query("equipe == @TEAM").iloc[0]

    return [
        Check("38 partidas com xG", len(por_partida) == TOTAL_ROUNDS, f"{len(por_partida)}"),
        Check("todas as rodadas com shotmap", chutes.rodada.nunique() == TOTAL_ROUNDS),
        Check("tabela de xG com 20 times", len(tabela) == TOTAL_TEAMS),
        Check(
            "gols do shotmap batem com o placar",
            (marcados, sofridos) == (int(oficial.gols_pro), int(oficial.gols_contra)),
            f"{marcados}:{sofridos} vs {int(oficial.gols_pro)}:{int(oficial.gols_contra)}",
        ),
        Check(
            "coordenadas presentes em todos os chutes",
            not chutes[["x", "y"]].isna().any().any(),
        ),
        Check(
            "só gols contra ficam sem xG",
            int(chutes.xg.isna().sum()) == int(chutes.gol_contra.sum()),
            f"{int(chutes.xg.isna().sum())} sem xG",
        ),
    ]


def resumo_xg(d: dict[str, pd.DataFrame]) -> None:
    if "chutes" not in d:
        return

    tabela, chutes = d["xg_tabela"], d["chutes"]
    inter = tabela.query("equipe == @TEAM").iloc[0]

    _titulo("EFICIÊNCIA (xG do FotMob)")
    print(f"  Pontos      {inter.pontos:>3}  vs {inter.pontos_esperados:>5.1f} esperados  "
          f"({inter.pontos - inter.pontos_esperados:+.1f})")
    print(f"  Gols feitos {inter.gols_pro:>3}  vs {inter.xg:>5.1f} xG         "
          f"({inter.eficiencia_ataque:+.1f})")
    print(f"  Gols sofr.  {inter.gols_contra:>3}  vs {inter.xg_contra:>5.1f} xG contra   "
          f"({inter.eficiencia_defesa:+.1f})")

    pior_ataque = tabela.nsmallest(1, "eficiencia_ataque").iloc[0]
    pior_defesa = tabela.nlargest(1, "eficiencia_defesa").iloc[0]
    print(f"\n  Pior finalização da liga: {pior_ataque.equipe} ({pior_ataque.eficiencia_ataque:+.1f})")
    print(f"  Pior defesa vs esperado:  {pior_defesa.equipe} ({pior_defesa.eficiencia_defesa:+.1f})")

    do_inter = chutes[chutes.do_internacional]
    gols = do_inter[do_inter.desfecho == "gol"]
    print(f"\n  {len(do_inter)} chutes, {do_inter.xg.sum():.1f} xG, {len(gols)} gols")
    print(f"  dentro da área: {int(do_inter.dentro_area.sum())} chutes "
          f"({do_inter[do_inter.dentro_area].xg.sum():.1f} xG)")
    print("  por situação: " + ", ".join(
        f"{situacao} {n}" for situacao, n in do_inter.situacao.value_counts().head(4).items()
    ))


def status_fbref() -> None:
    _titulo("FBREF (coleta manual)")
    if fbref_parser.is_available():
        tabelas = fbref_parser.collect_tables()
        reconhecidas = fbref_parser.match_expected(tabelas)
        print(f"  {len(tabelas)} tabelas salvas, {len(reconhecidas)} reconhecidas")
        for table_id, nome in sorted(reconhecidas.items()):
            print(f"    {table_id:<28} -> {nome}")
    else:
        print("  Nenhum HTML salvo — análises de xG e finalização indisponíveis.")
        print("  Veja as instruções em: poetry run python -m src.scraper.fbref_parser")


def main() -> int:
    dados = carregar()

    _titulo("ARQUIVOS COLETADOS")
    for nome, arq in ARQUIVOS.items():
        frame = dados[nome]
        nulos = int(frame.isna().sum().sum())
        print(
            f"  {arq:<44}{len(frame):>5} linhas x{len(frame.columns):>3} col"
            + (f"   ({nulos} nulos)" if nulos else "")
        )

    _titulo("INTEGRIDADE")
    checks = checar_integridade(dados)
    for check in checks:
        print(check.render())

    _titulo("RECONCILIAÇÃO ENTRE FONTES (Transfermarkt x Wikipédia)")
    reconciliacao = checar_reconciliacao(dados)
    for check in reconciliacao:
        print(check.render())

    xg = checar_xg(dados)
    if xg:
        _titulo("DADOS DE xG (FotMob)")
        for check in xg:
            print(check.render())

    resumo_do_inter(dados)
    resumo_xg(dados)
    status_fbref()

    falhas = [c for c in checks + reconciliacao + xg if not c.ok]
    _titulo("RESULTADO")
    if falhas:
        print(f"  {len(falhas)} checagem(ns) falharam:")
        for check in falhas:
            print(f"    - {check.nome}")
        return 1
    print(f"  Todas as {len(checks) + len(reconciliacao) + len(xg)} checagens passaram.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

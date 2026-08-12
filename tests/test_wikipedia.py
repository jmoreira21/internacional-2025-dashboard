"""Testes do coletor da Wikipédia."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from bs4 import BeautifulSoup

from src.scraper.wikipedia import (
    TOTAL_ROUNDS,
    derive_coach_periods,
    parse_artilharia,
    parse_assistencias,
    parse_classificacao,
    parse_mudancas_tecnicos,
    parse_pos_por_rodada,
    parse_sigla_map,
)

HTML = """<html><body>
<table class="wikitable">
  <tr><th>Pos</th><th>Equipe <span>v</span> <span>d</span> <span>e</span></th><th>Pts</th>
      <th>J</th><th>V</th><th>E</th><th>D</th><th>GP</th><th>GC</th><th>SG</th>
      <th>Classificação ou descenso</th></tr>
  <tr><td>1</td><td>Flamengo (C)</td><td>79</td><td>38</td><td>23</td><td>10</td><td>5</td>
      <td>78</td><td>27</td><td>+51</td><td>Libertadores</td></tr>
  <tr><td>16</td><td>Internacional</td><td>44</td><td>38</td><td>11</td><td>11</td><td>16</td>
      <td>44</td><td>57</td><td>&#8722;13</td><td></td></tr>
</table>

<table class="wikitable">
  <tr><th>Mandante \\ Visitante</th><th>FLA</th><th>INT</th></tr>
  <tr><th>Flamengo</th><td>—</td><td>1:1</td></tr>
  <tr><th>Internacional</th><td>0:2</td><td>—</td></tr>
</table>

<table class="wikitable">
  <tr><th>Rodada ↓</th><th>FLA</th><th>INT</th></tr>
  <tr><td>1.ª</td><td>8</td><td>10</td></tr>
  <tr><td>38.ª</td><td>1</td><td>16</td></tr>
</table>

<table class="wikitable">
  <tr><th>Pos.</th><th>Jogador</th><th>Equipe</th><th>Gols<sup>[59]</sup></th></tr>
  <tr><td>1</td><td>Kaio Jorge</td><td>Cruzeiro</td><td>21</td></tr>
  <tr><td rowspan="2">4</td><td>Pablo Vegetti</td><td>Vasco da Gama</td><td rowspan="2">14</td></tr>
  <tr><td>Rayan</td><td>Vasco da Gama</td></tr>
</table>

<table class="wikitable">
  <tr><th>Pos.</th><th>Jogador</th><th>Equipe</th><th>Assists.<sup>[60]</sup></th></tr>
  <tr><td rowspan="2">4</td><td>Alan Patrick</td><td>Internacional</td><td rowspan="2">7</td></tr>
  <tr><td>Cristian Pavón</td><td>Grêmio</td></tr>
</table>

<table class="wikitable">
  <tr><th>Clube</th><th>Antecessor</th><th>Data</th><th>Última partida</th><th>Rod</th>
      <th>Pos</th><th>Sucessor</th><th>Ref.</th></tr>
  <tr><td>Internacional</td><td>Roger Machado</td><td>21 de setembro</td>
      <td>Internacional 2–3 Grêmio</td><td>24.ª</td><td>13.º</td><td>Ramón Díaz</td>
      <td><sup>[130]</sup></td></tr>
  <tr><td>Internacional</td><td>Ramón Díaz</td><td>29 de novembro</td>
      <td>Vasco da Gama 5–1 Internacional</td><td>36.ª</td><td>16.º</td><td>Abel Braga</td>
      <td><sup>[139]</sup></td></tr>
  <tr><td>Grêmio</td><td>Gustavo Quinteros</td><td>16 de abril</td>
      <td>Mirassol 4–1 Grêmio</td><td>4.ª</td><td>17.º</td><td>Mano Menezes</td>
      <td><sup>[1]</sup></td></tr>
</table>
</body></html>"""


@pytest.fixture(scope="module")
def soup():
    return BeautifulSoup(HTML, "lxml")


def test_classificacao_limpa_marcadores(soup):
    df = parse_classificacao(soup)
    assert df.loc[0, "equipe"] == "Flamengo"  # o "(C)" de campeão é removido
    assert df.loc[0, "saldo"] == 51


def test_classificacao_interpreta_saldo_negativo(soup):
    """O saldo usa o sinal de menos unicode (−), não o hífen ASCII."""
    inter = parse_classificacao(soup).query("equipe == 'Internacional'").iloc[0]
    assert inter.saldo == -13
    assert (inter.pontos, inter.gols_pro, inter.gols_contra) == (44, 44, 57)


def test_sigla_map_derivado_dos_confrontos(soup):
    assert parse_sigla_map(soup) == {"FLA": "Flamengo", "INT": "Internacional"}


def test_pos_por_rodada_em_formato_longo(soup):
    df = parse_pos_por_rodada(soup, parse_sigla_map(soup))
    assert len(df) == 4
    inter = df.query("equipe == 'Internacional'").set_index("rodada")["posicao"]
    assert inter[1] == 10
    assert inter[38] == 16


def test_artilharia_expande_rowspan(soup):
    """Empatados dividem as células de posição e total via rowspan."""
    df = parse_artilharia(soup)
    assert len(df) == 3
    assert df.query("jogador == 'Rayan'").iloc[0][["posicao", "gols"]].tolist() == [4, 14]


def test_assistencias_nao_colide_com_artilharia(soup):
    """As duas tabelas têm cabeçalho quase idêntico e são distinguidas pela métrica."""
    df = parse_assistencias(soup)
    assert "assistencias" in df.columns
    alan = df.query("jogador == 'Alan Patrick'").iloc[0]
    assert (alan.equipe, alan.assistencias, alan.posicao) == ("Internacional", 7, 4)


def test_mudancas_tecnicos(soup):
    df = parse_mudancas_tecnicos(soup)
    assert len(df) == 3
    roger = df.iloc[0]
    assert roger.data_saida == date(2025, 9, 21)
    assert (roger.rodada_saida, roger.posicao_saida) == (24, 13)


def test_periodos_dos_tecnicos_sao_contiguos(soup):
    df = derive_coach_periods(parse_mudancas_tecnicos(soup))
    assert df["tecnico"].tolist() == ["Roger Machado", "Ramón Díaz", "Abel Braga"]
    assert df["rodada_inicio"].tolist() == [1, 25, 37]
    assert df["rodada_fim"].tolist() == [24, 36, 38]
    assert df["jogos"].sum() == TOTAL_ROUNDS


def test_periodos_ignoram_outros_clubes(soup):
    """A tabela cobre todos os clubes; só as linhas do Inter importam aqui."""
    df = derive_coach_periods(parse_mudancas_tecnicos(soup), clube="Grêmio")
    assert df["tecnico"].tolist() == ["Gustavo Quinteros", "Mano Menezes"]


# --- reconciliação com os dados reais ---------------------------------------


def test_classificacao_real_e_consistente(classificacao):
    assert len(classificacao) == 20
    assert classificacao["jogos"].sum() == 380 * 2
    assert classificacao["gols_pro"].sum() == classificacao["gols_contra"].sum()
    assert classificacao["saldo"].sum() == 0

    esperado = classificacao["vitorias"] * 3 + classificacao["empates"]
    pd.testing.assert_series_equal(
        classificacao["pontos"], esperado, check_names=False, check_dtype=False
    )


def test_inter_terminou_em_16_por_um_ponto(classificacao):
    """O contexto do projeto: o Inter escapou do rebaixamento por 1 ponto."""
    inter = classificacao.query("equipe == 'Internacional'").iloc[0]
    primeiro_rebaixado = classificacao.query("posicao == 17").iloc[0]
    assert inter.posicao == 16
    assert inter.pontos - primeiro_rebaixado.pontos == 1


def test_pos_por_rodada_real(wikipedia_soup, classificacao):
    df = parse_pos_por_rodada(wikipedia_soup, parse_sigla_map(wikipedia_soup))
    assert len(df) == TOTAL_ROUNDS * 20
    assert df["rodada"].nunique() == TOTAL_ROUNDS

    # Da rodada 2 em diante as posições são estritamente 1..20. Na rodada 1
    # times empatados em tudo dividem a colocação (Cruzeiro e Grêmio em 4º).
    for rodada, grupo in df.query("rodada > 1").groupby("rodada"):
        assert sorted(grupo["posicao"]) == list(range(1, 21)), f"rodada {rodada}"
    assert len(df.query("rodada == 1")) == 20

    final = df.query("rodada == @TOTAL_ROUNDS").set_index("equipe")["posicao"]
    oficial = classificacao.set_index("equipe")["posicao"]
    pd.testing.assert_series_equal(
        final.sort_index(), oficial.sort_index(), check_names=False, check_dtype=False
    )


def test_tecnicos_reais_do_inter_cobrem_a_temporada(wikipedia_soup):
    df = derive_coach_periods(parse_mudancas_tecnicos(wikipedia_soup))
    assert df["tecnico"].tolist() == ["Roger Machado", "Ramón Díaz", "Abel Braga"]
    assert df["jogos"].sum() == TOTAL_ROUNDS
    assert df["rodada_inicio"].iloc[0] == 1
    assert df["rodada_fim"].iloc[-1] == TOTAL_ROUNDS
    # sem buracos nem sobreposição entre um técnico e o seguinte
    assert (df["rodada_inicio"].shift(-1).dropna() == df["rodada_fim"][:-1] + 1).all()

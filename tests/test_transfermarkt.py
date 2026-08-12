"""Testes do coletor do Transfermarkt."""

from __future__ import annotations

from datetime import date

import pytest

from src.scraper.transfermarkt import (
    INTERNACIONAL_ID,
    parse_gesamtspielplan,
    matches_to_frame,
    team_perspective,
)

FLAMENGO, INTER, CRUZEIRO, PALMEIRAS, SANTOS = "614", "6600", "609", "1023", "221"


def _row(home_id: str, home: str, away_id: str, away: str, score: str | None,
         match_id: str = "1", data: str = "", hora: str = "") -> str:
    """Monta uma linha fiel ao DOM do Transfermarkt (7 células)."""
    placar = (
        f'<a class="ergebnis-link" href="/x/index/spielbericht/{match_id}">{score}</a>'
        if score
        else "adiado"
    )
    return f"""
    <tr>
      <td class="hide-for-small">{data}</td>
      <td class="zentriert hide-for-small">{hora}</td>
      <td class="text-right no-border-rechts hauptlink">
        <a href="/x/spielplan/verein/{home_id}/saison_id/2024">{home}</a></td>
      <td class="zentriert no-border-links"><a href="/x/spielplan/verein/{home_id}/saison_id/2024"></a></td>
      <td class="zentriert hauptlink">{placar}</td>
      <td class="zentriert no-border-rechts"><a href="/x/spielplan/verein/{away_id}/saison_id/2024"></a></td>
      <td class="no-border-links hauptlink">
        <a href="/x/spielplan/verein/{away_id}/saison_id/2024">{away}</a></td>
    </tr>"""


HTML = f"""<html><body>
<div class="box">
  <div class="content-box-headline">1.Rodada</div>
  <table>{_row(FLAMENGO, "Flamengo", INTER, "Internacional", "1:1",
               "4582060", data='sáb <a href="/d">29/03/25</a>', hora="21:00")}</table>
</div>
<div class="box">
  <div class="content-box-headline">2.Rodada</div>
  <table>
    {_row(INTER, "(11.) Internacional", CRUZEIRO, "Cruzeiro (3.)", "3:0",
          "4582136", data='dom <a href="/d">06/04/25</a>', hora="16:00")}
    {_row(PALMEIRAS, "Palmeiras", SANTOS, "Santos", "2:1", "4582137")}
    {_row(PALMEIRAS, "Palmeiras", SANTOS, "Santos", None, "0")}
  </table>
</div>
</body></html>"""


@pytest.fixture(scope="module")
def matches():
    return parse_gesamtspielplan(HTML)


def test_ignora_partida_sem_placar(matches):
    """Jogos adiados não têm a.ergebnis-link e devem ser descartados."""
    assert len(matches) == 3


def test_horario_nao_e_confundido_com_placar(matches):
    """Regressão: o regex \\d+:\\d+ casa com o horário 21:00 e gerava 21x0.

    Esse erro inflava os gols do Inter de 44 para 462 na validação inicial.
    """
    primeiro = matches[0]
    assert (primeiro.gols_mandante, primeiro.gols_visitante) == (1, 1)


def test_identifica_times_por_verein_id(matches):
    """O texto vem como '(11.) Internacional'; o id é a chave confiável."""
    segundo = matches[1]
    assert segundo.mandante_id == INTER
    assert segundo.mandante == "Internacional"
    assert segundo.visitante == "Cruzeiro"


def test_extrai_posicao_da_celula_do_time(matches):
    segundo = matches[1]
    assert (segundo.pos_mandante, segundo.pos_visitante) == (11, 3)
    assert matches[0].pos_mandante is None


def test_data_e_propagada_para_linhas_sem_data(matches):
    """Só a primeira linha do dia traz a data; as seguintes herdam."""
    assert matches[1].data == date(2025, 4, 6)
    assert matches[2].data == date(2025, 4, 6)


def test_rodada_e_match_id(matches):
    assert [m.rodada for m in matches] == [1, 2, 2]
    assert matches[0].match_id == "4582060"


def test_perspectiva_do_time():
    inter = team_perspective(matches_to_frame(parse_gesamtspielplan(HTML)), INTER)
    assert len(inter) == 2
    assert inter["mando"].tolist() == ["fora", "casa"]
    assert inter["adversario"].tolist() == ["Flamengo", "Cruzeiro"]
    assert inter["gols_pro"].tolist() == [1, 3]
    assert inter["gols_contra"].tolist() == [1, 0]
    assert inter["resultado"].tolist() == ["E", "V"]


# --- reconciliação com os dados reais ---------------------------------------


def test_campeonato_completo(transfermarkt_matches):
    assert len(transfermarkt_matches) == 380

    times = {m.mandante_id for m in transfermarkt_matches}
    assert len(times) == 20

    jogos = {t: 0 for t in times}
    for match in transfermarkt_matches:
        jogos[match.mandante_id] += 1
        jogos[match.visitante_id] += 1
    assert set(jogos.values()) == {38}


def test_inter_reconcilia_com_a_classificacao(transfermarkt_matches, classificacao):
    """As 38 partidas coletadas devem reproduzir a linha oficial do Inter.

    É o teste de qualidade mais forte do pipeline: cruza duas fontes
    independentes (Transfermarkt e Wikipédia).
    """
    inter = team_perspective(matches_to_frame(transfermarkt_matches), INTERNACIONAL_ID)
    contagem = inter["resultado"].value_counts()
    marcados, sofridos = int(inter["gols_pro"].sum()), int(inter["gols_contra"].sum())
    vitorias, empates = int(contagem.get("V", 0)), int(contagem.get("E", 0))

    oficial = classificacao.query("equipe == 'Internacional'").iloc[0]

    assert len(inter) == int(oficial.jogos) == 38
    assert vitorias == int(oficial.vitorias)
    assert empates == int(oficial.empates)
    assert int(contagem.get("D", 0)) == int(oficial.derrotas)
    assert marcados == int(oficial.gols_pro)
    assert sofridos == int(oficial.gols_contra)
    assert marcados - sofridos == int(oficial.saldo)
    assert vitorias * 3 + empates == int(oficial.pontos)


def test_inter_tem_19_jogos_em_casa_e_19_fora(transfermarkt_matches):
    inter = team_perspective(matches_to_frame(transfermarkt_matches), INTERNACIONAL_ID)
    assert inter["mando"].value_counts().to_dict() == {"casa": 19, "fora": 19}
    assert sorted(inter["rodada"]) == list(range(1, 39))

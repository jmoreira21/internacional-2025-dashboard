"""Testes do parser de HTML local do FBref.

Não há dados reais do FBref versionados (a coleta é manual), então os testes
usam HTML sintético que reproduz as duas particularidades do site: tabelas
escondidas em comentários e colunas identificadas por `data-stat`.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.scraper.fbref_parser import (
    FbrefDataMissing,
    collect_tables,
    find_tables,
    is_available,
    match_expected,
    table_to_frame,
)

FIXTURES_TABLE = """
<table id="matchlogs_for">
  <thead>
    <tr class="over_header"><th colspan="4">Desempenho</th></tr>
    <tr><th data-stat="date">Data</th><th data-stat="opponent">Adversário</th>
        <th data-stat="goals_for">GF</th><th data-stat="xg_for">xG</th></tr>
  </thead>
  <tbody>
    <tr><th data-stat="date">2025-03-29</th><td data-stat="opponent">Flamengo</td>
        <td data-stat="goals_for">1</td><td data-stat="xg_for">0.8</td></tr>
    <tr class="thead"><th data-stat="date">Data</th><td data-stat="opponent">Adversário</td>
        <td data-stat="goals_for">GF</td><td data-stat="xg_for">xG</td></tr>
    <tr><th data-stat="date">2025-04-06</th><td data-stat="opponent">Cruzeiro</td>
        <td data-stat="goals_for">3</td><td data-stat="xg_for">1.9</td></tr>
    <tr class="spacer"><td data-stat="date"></td></tr>
  </tbody>
</table>"""

SHOOTING_TABLE = """
<table id="stats_shooting_24">
  <thead><tr><th data-stat="player">Jogador</th><th data-stat="shots">Ch</th>
             <th data-stat="average_shot_distance">Dist</th><th data-stat="xg">xG</th></tr></thead>
  <tbody>
    <tr><th data-stat="player">Alan Patrick</th><td data-stat="shots">62</td>
        <td data-stat="average_shot_distance">19.4</td><td data-stat="xg">5.7</td></tr>
  </tbody>
</table>"""

# No FBref real, só a primeira tabela vem no DOM; as demais ficam em comentários.
HTML = f"""<html><body>
  <div>{FIXTURES_TABLE}</div>
  <div class="placeholder"></div>
  <!--
  {SHOOTING_TABLE}
  -->
</body></html>"""


def test_encontra_tabela_escondida_em_comentario():
    """A principal armadilha do FBref: sem ler comentários, só 1 tabela aparece."""
    assert set(find_tables(HTML)) == {"matchlogs_for", "stats_shooting_24"}


def test_colunas_vem_do_data_stat():
    """Os cabeçalhos visíveis mudam entre pt e en; os data-stat são estáveis."""
    frame = table_to_frame(find_tables(HTML)["matchlogs_for"])
    assert list(frame.columns) == ["date", "opponent", "goals_for", "xg_for"]


def test_descarta_cabecalhos_repetidos_e_espacadores():
    frame = table_to_frame(find_tables(HTML)["matchlogs_for"])
    assert len(frame) == 2
    assert frame["opponent"].tolist() == ["Flamengo", "Cruzeiro"]


def test_converte_colunas_numericas():
    frame = table_to_frame(find_tables(HTML)["matchlogs_for"])
    assert frame["goals_for"].sum() == 4
    assert frame["xg_for"].sum() == pytest.approx(2.7)
    # coluna de texto não pode ser convertida (pandas 3 usa StringDtype, não object)
    assert not pd.api.types.is_numeric_dtype(frame["opponent"])
    assert frame["opponent"].tolist() == ["Flamengo", "Cruzeiro"]


def test_casa_id_com_sufixo_variavel():
    """O sufixo do id varia com a competição (stats_shooting_24)."""
    assert match_expected(find_tables(HTML)) == {
        "matchlogs_for": "fixtures",
        "stats_shooting_24": "shooting",
    }


def test_le_arquivos_salvos(tmp_path):
    (tmp_path / "inter.html").write_text(HTML, encoding="utf-8")
    tables = collect_tables(tmp_path)
    assert set(tables) == {"matchlogs_for", "stats_shooting_24"}
    assert is_available(tmp_path)


def test_diretorio_vazio_orienta_o_usuario(tmp_path):
    """Sem HTML salvo, o erro precisa dizer o que fazer — não estourar cru."""
    with pytest.raises(FbrefDataMissing, match="Cloudflare"):
        collect_tables(tmp_path)
    assert not is_available(tmp_path)


def test_diretorio_inexistente_nao_quebra(tmp_path):
    """O dashboard chama is_available() para degradar sem quebrar."""
    assert not is_available(tmp_path / "nao" / "existe")

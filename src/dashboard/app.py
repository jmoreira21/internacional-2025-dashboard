"""Dashboard do Internacional no Brasileirão 2025.

Rode com:
    poetry run streamlit run src/dashboard/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# O Streamlit coloca o diretório do script no sys.path, não a raiz do projeto.
RAIZ = Path(__file__).resolve().parent.parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import streamlit as st  # noqa: E402

from src.dashboard import dados, estilo  # noqa: E402
from src.dashboard.paginas import (  # noqa: E402
    artilheiros,
    chutes,
    gols,
    posicao,
    resumo,
    rivais,
    tecnicos,
    xg,
)

ABAS = {
    "Visão geral": resumo.render,
    "Z4": posicao.render,
    "Gols": gols.render,
    "xG": xg.render,
    "Técnicos": tecnicos.render,
    "Chutes": chutes.render,
    "Artilheiros": artilheiros.render,
    "Rivais": rivais.render,
}


def main() -> None:
    st.set_page_config(
        page_title="Internacional 2025",
        page_icon="⚽",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    estilo.aplicar_css()

    if not dados.banco_existe():
        _sem_banco()
        st.stop()

    _cabecalho()
    _faixa_de_indicadores()

    for aba, render in zip(st.tabs(list(ABAS)), ABAS.values()):
        with aba:
            render()


def _sem_banco() -> None:
    st.error("Banco não encontrado.")
    st.markdown(
        "Monte os dados antes de abrir o dashboard:\n\n"
        "```bash\n"
        "poetry run python -m src.scraper.transfermarkt\n"
        "poetry run python -m src.scraper.wikipedia\n"
        "poetry run python -m src.scraper.fotmob\n"
        "poetry run python -m src.db.carga\n"
        "```"
    )


def _cabecalho() -> None:
    esquerda, direita = st.columns([3, 1])
    with esquerda:
        st.markdown(
            '<div class="titulo-clube">Sport Club Internacional</div>'
            '<div class="titulo-temporada">Temporada <span>2025</span></div>',
            unsafe_allow_html=True,
        )
    with direita:
        st.markdown(
            '<div style="text-align:right;padding-top:1.1rem">'
            '<span class="rotulo">Brasileirão Série A · 38 rodadas</span></div>',
            unsafe_allow_html=True,
        )
    st.write("")


def _faixa_de_indicadores() -> None:
    tabela = dados.classificacao()
    inter = tabela.query("sigla == 'INT'").iloc[0]
    primeiro_rebaixado = tabela.query("posicao == 17").iloc[0]
    margem = int(inter.pontos) - int(primeiro_rebaixado.pontos)
    aproveitamento = int(inter.pontos) / (int(inter.jogos) * 3)

    manchete, *cards = st.columns([2.4, 1, 1, 1, 1, 1.15])

    with manchete:
        st.markdown(
            '<div class="card card-acento">'
            '<div class="rotulo">Termômetro da temporada</div>'
            f'<div class="manchete" style="margin-top:.5rem">{int(inter.posicao)}º lugar. '
            f'<em>Escapou por {margem} ponto{"s" if margem != 1 else ""}.</em></div>'
            '<div class="subtexto">O Inter terminou à frente do '
            f'{primeiro_rebaixado.nome} por {margem} ponto'
            f'{"s" if margem != 1 else ""} e evitou a Série B na última rodada.</div>'
            "</div>",
            unsafe_allow_html=True,
        )

    indicadores = [
        ("Jogos", str(int(inter.jogos)), "temporada 2025", None, False),
        ("Vitórias", str(int(inter.vitorias)),
         f"{100 * inter.vitorias / inter.jogos:.1f}% dos jogos", None, False),
        ("Empates", str(int(inter.empates)),
         f"{100 * inter.empates / inter.jogos:.1f}% dos jogos", None, False),
        ("Derrotas", str(int(inter.derrotas)),
         f"{100 * inter.derrotas / inter.jogos:.1f}% dos jogos", None, False),
        ("Gols", f"{int(inter.gols_pro)} : {int(inter.gols_contra)}",
         f"saldo {int(inter.saldo):+d}", None, False),
        ("Aproveitamento", f"{100 * aproveitamento:.1f}%",
         f"{int(inter.pontos)} de {int(inter.jogos) * 3} pontos", aproveitamento, True),
    ]
    for coluna, (rotulo, valor, nota, proporcao, vermelho) in zip(cards, indicadores):
        with coluna:
            st.markdown(
                estilo.card(rotulo, valor, nota, proporcao=proporcao, vermelho=vermelho),
                unsafe_allow_html=True,
            )

    st.write("")


if __name__ == "__main__":
    main()

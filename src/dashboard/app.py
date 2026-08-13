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

from src.dashboard import dados  # noqa: E402
from src.dashboard.paginas import gols, posicao, rivais, tecnicos  # noqa: E402

PAGINAS = {
    "Briga contra o Z4": posicao.render,
    "Gols por rodada": gols.render,
    "Os três técnicos": tecnicos.render,
    "Rivais do Z4": rivais.render,
}


def main() -> None:
    st.set_page_config(
        page_title="Internacional 2025",
        page_icon="⚽",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    if not dados.banco_existe():
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
        st.stop()

    with st.sidebar:
        st.title("⚽ Internacional 2025")
        st.caption("Por que o time brigou contra o rebaixamento")
        escolha = st.radio("Análise", list(PAGINAS), label_visibility="collapsed")
        st.divider()
        _resumo_lateral()

    PAGINAS[escolha]()


def _resumo_lateral() -> None:
    tabela = dados.classificacao()
    inter = tabela.query("sigla == 'INT'").iloc[0]
    primeiro_rebaixado = tabela.query("posicao == 17").iloc[0]
    margem = int(inter.pontos) - int(primeiro_rebaixado.pontos)

    st.metric("Posição final", f"{int(inter.posicao)}º", f"{int(inter.pontos)} pontos",
              delta_color="off")
    st.metric(
        "Margem para o Z4",
        f"{margem} ponto" + ("s" if margem != 1 else ""),
        f"sobre o {primeiro_rebaixado.nome}",
        delta_color="off",
    )
    st.caption(
        f"{int(inter.vitorias)}V · {int(inter.empates)}E · {int(inter.derrotas)}D  |  "
        f"{int(inter.gols_pro)}:{int(inter.gols_contra)} ({int(inter.saldo):+d})"
    )


if __name__ == "__main__":
    main()

"""Dashboard do Internacional no Brasileirão 2025.

A tela é organizada como um argumento, não como um painel de monitoramento: a
abertura apresenta o desfecho e cada seção seguinte sustenta uma afirmação sobre
por que a temporada terminou assim, com a evidência logo abaixo.

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
    rivais,
    tecnicos,
    xg,
)

# A ordem é o argumento: criou bem, converteu mal, e o resto decorre disso.
NARRATIVA = [
    rivais.secao,       # não foi falta de criar
    xg.secao,           # foi ineficiência nas duas pontas
    chutes.secao,       # todos os gols saíram de dentro da área
    gols.secao,         # fora de casa desabava
    tecnicos.secao,     # trocar de técnico não mudou
    artilheiros.secao,  # dependia de um jogador
    posicao.secao,      # a conta fechou na última rodada
]


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

    _abertura()
    for numero, secao in enumerate(NARRATIVA, start=1):
        secao(numero)
    _fechamento()


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


def _abertura() -> None:
    tabela = dados.classificacao()
    inter = tabela.query("sigla == 'INT'").iloc[0]
    rebaixado = tabela.query("posicao == 17").iloc[0]
    margem = int(inter.pontos) - int(rebaixado.pontos)
    aproveitamento = int(inter.pontos) / (int(inter.jogos) * 3)
    plural = "s" if margem != 1 else ""

    st.markdown(
        '<div class="titulo-clube">Sport Club Internacional · Brasileirão Série A</div>'
        '<div class="titulo-temporada">Temporada <span>2025</span></div>',
        unsafe_allow_html=True,
    )
    st.write("")

    esquerda, direita = st.columns([1.6, 1], gap="medium")
    with esquerda:
        st.markdown(
            '<div class="card card-acento">'
            f'<div class="manchete">O Inter terminou em {int(inter.posicao)}º e '
            f"<em>escapou do rebaixamento por {margem} ponto{plural}</em>.</div>"
            '<div class="subtexto">Criou chances como time de cima da tabela e converteu '
            "como o pior do campeonato. As sete seções abaixo mostram onde a temporada "
            "foi perdida — e onde <strong>não</strong> foi.</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    with direita:
        st.markdown(
            estilo.card(
                "Aproveitamento",
                f"{100 * aproveitamento:.1f}%",
                f"{int(inter.pontos)} de {int(inter.jogos) * 3} pontos · "
                f"{int(inter.vitorias)}V {int(inter.empates)}E {int(inter.derrotas)}D · "
                f"{int(inter.gols_pro)}:{int(inter.gols_contra)} ({int(inter.saldo):+d})",
                proporcao=aproveitamento,
                vermelho=True,
            ),
            unsafe_allow_html=True,
        )


def _fechamento() -> None:
    st.markdown('<div class="secao" style="margin-bottom:1rem"></div>', unsafe_allow_html=True)
    estilo.rotulo_secao("Fontes e ressalvas")
    st.markdown(
        """
- **Partidas e classificação**: Transfermarkt e Wikipédia, reconciliados entre si —
  as 38 partidas reproduzem a linha oficial (11V/11E/16D, 44:57, 44 pontos).
- **xG e chutes**: FotMob, 987 finalizações com coordenadas. O FBref não publica
  dados avançados do Brasileirão.
- **Estatísticas por jogador**: FBref, coleta manual.
- **Abel Braga dirigiu 2 jogos.** O percentual dele aparece com o número de jogos ao
  lado justamente por não ser comparável aos outros dois.
- **xG é estimativa, não verdade.** As duas agregações do próprio FotMob divergem
  cerca de 7% na defesa; aqui usamos a soma dos chutes, que reconcilia com o placar.
        """,
        unsafe_allow_html=False,
    )


if __name__ == "__main__":
    main()

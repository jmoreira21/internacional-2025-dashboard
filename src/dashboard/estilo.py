"""Chrome da interface: CSS e componentes de card.

O Streamlit não expõe um sistema de cards, então a camada visual é injetada
como CSS uma vez por sessão. Os valores vêm de `tema.py`, para que gráfico e
interface não saiam de sincronia.
"""

from __future__ import annotations

import streamlit as st

from src.dashboard import tema

CSS = f"""
<style>
  /* --- base ------------------------------------------------------------- */
  .stApp {{ background: {tema.PAGINA}; }}
  .block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1500px; }}
  #MainMenu, footer, header {{ visibility: hidden; }}

  /* --- tipografia de rótulo --------------------------------------------- */
  .rotulo {{
    font-size: .68rem;
    letter-spacing: .14em;
    text-transform: uppercase;
    color: {tema.MUDO};
    font-weight: 600;
  }}

  /* --- cards ------------------------------------------------------------- */
  .card {{
    background: {tema.SUPERFICIE};
    border: 1px solid {tema.BORDA};
    border-radius: 10px;
    padding: 1.1rem 1.25rem;
    height: 100%;
  }}
  .card-acento {{ border-left: 3px solid {tema.SERIE_1}; }}

  /* --- números ----------------------------------------------------------- */
  .valor {{
    font-size: 2.1rem;
    font-weight: 600;
    color: {tema.TINTA};
    line-height: 1.15;
    margin-top: .35rem;
  }}
  .valor-vermelho {{ color: {tema.SERIE_1}; }}
  .nota {{ font-size: .76rem; color: {tema.MUDO}; margin-top: .3rem; }}

  /* --- barra de proporção ------------------------------------------------ */
  .trilho {{
    height: 3px;
    background: {tema.GRADE};
    border-radius: 2px;
    margin-top: .7rem;
    overflow: hidden;
  }}
  .trilho > div {{ height: 100%; background: {tema.SERIE_1}; border-radius: 2px; }}

  /* --- destaque do topo -------------------------------------------------- */
  .manchete {{ font-size: 1.55rem; font-weight: 600; color: {tema.TINTA}; line-height: 1.25; }}
  .manchete em {{ color: {tema.SERIE_1}; font-style: normal; }}
  .subtexto {{ font-size: .82rem; color: {tema.TINTA_2}; margin-top: .6rem; line-height: 1.55; }}

  /* --- cabeçalho --------------------------------------------------------- */
  .titulo-clube {{
    font-size: .7rem; letter-spacing: .2em; text-transform: uppercase;
    color: {tema.MUDO}; font-weight: 600;
  }}
  .titulo-temporada {{ font-size: 1.9rem; font-weight: 600; color: {tema.TINTA}; line-height: 1.1; }}
  .titulo-temporada span {{ color: {tema.SERIE_1}; }}

  /* --- tabela enxuta ----------------------------------------------------- */
  .linha-tabela {{
    display: flex; align-items: center; gap: .6rem;
    padding: .42rem .5rem; border-radius: 6px;
    font-size: .82rem; color: {tema.TINTA_2};
  }}
  .linha-tabela.destaque {{
    background: rgba(229, 72, 77, .12);
    border-left: 2px solid {tema.SERIE_1};
    color: {tema.TINTA};
  }}
  .linha-tabela .pos {{ width: 1.5rem; color: {tema.MUDO}; font-variant-numeric: tabular-nums; }}
  .linha-tabela .nome {{ flex: 1; }}
  .linha-tabela .pts {{ font-variant-numeric: tabular-nums; font-weight: 600; }}

  /* --- abas -------------------------------------------------------------- */
  .stTabs [data-baseweb="tab-list"] {{ gap: .3rem; border-bottom: 1px solid {tema.BORDA}; }}
  .stTabs [data-baseweb="tab"] {{
    height: 2.4rem; padding: 0 .9rem; background: transparent;
    font-size: .78rem; letter-spacing: .06em; text-transform: uppercase;
    color: {tema.MUDO};
  }}
  .stTabs [aria-selected="true"] {{ color: {tema.TINTA}; }}

  /* --- seções da narrativa ----------------------------------------------- */
  .secao {{
    display: flex; align-items: baseline; gap: .9rem;
    margin: 3.2rem 0 .35rem;
    border-top: 1px solid {tema.BORDA}; padding-top: 1.4rem;
  }}
  .secao-num {{
    font-size: .78rem; font-weight: 700; color: {tema.SERIE_1};
    font-variant-numeric: tabular-nums; letter-spacing: .1em;
  }}
  .secao-tese {{ font-size: 1.42rem; font-weight: 600; color: {tema.TINTA}; line-height: 1.3; }}
  .secao-apoio {{
    font-size: .9rem; color: {tema.TINTA_2}; line-height: 1.6;
    margin: 0 0 1.1rem 2.7rem; max-width: 62ch;
  }}
  .secao-apoio strong {{ color: {tema.TINTA}; font-weight: 600; }}

  /* --- diversos ---------------------------------------------------------- */
  div[data-testid="stExpander"] {{ border: 1px solid {tema.BORDA}; border-radius: 8px; }}
  hr {{ border-color: {tema.BORDA}; }}
</style>
"""


def aplicar_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def card(rotulo: str, valor: str, nota: str = "", *, acento: bool = False,
         proporcao: float | None = None, vermelho: bool = False) -> str:
    """Card de indicador. `proporcao` (0..1) desenha a barra de preenchimento."""
    classes = "card card-acento" if acento else "card"
    cor = "valor valor-vermelho" if vermelho else "valor"
    partes = [
        f'<div class="{classes}">',
        f'<div class="rotulo">{rotulo}</div>',
        f'<div class="{cor}">{valor}</div>',
    ]
    if nota:
        partes.append(f'<div class="nota">{nota}</div>')
    if proporcao is not None:
        largura = max(0.0, min(1.0, proporcao)) * 100
        partes.append(f'<div class="trilho"><div style="width:{largura:.1f}%"></div></div>')
    partes.append("</div>")
    return "".join(partes)


def rotulo_secao(texto: str) -> None:
    st.markdown(f'<div class="rotulo">{texto}</div>', unsafe_allow_html=True)


def secao(numero: int, tese: str, apoio: str) -> None:
    """Cabeçalho de uma seção da narrativa: a afirmação e a frase que a sustenta."""
    st.markdown(
        f'<div class="secao">'
        f'<span class="secao-num">{numero:02d}</span>'
        f'<span class="secao-tese">{tese}</span>'
        f"</div>"
        f'<div class="secao-apoio">{apoio}</div>',
        unsafe_allow_html=True,
    )

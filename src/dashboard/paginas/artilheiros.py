"""Dependência ofensiva — quanto o ataque do Inter passava por um jogador só."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from src.dashboard import dados, tema

QUANTOS_MOSTRAR = 12


def render() -> None:
    st.header("Dependência ofensiva")

    if not dados.tem_jogadores():
        st.info(
            "As estatísticas por jogador vêm do FBref, que é coleta manual.\n\n"
            "Salve a página da temporada em `data/raw/fbref/` e rode:\n\n"
            "```bash\n"
            "poetry run python -m src.scraper.fbref_parser\n"
            "poetry run python -m src.db.carga\n"
            "```",
            icon="ℹ️",
        )
        return

    elenco = dados.jogadores()
    com_gol = elenco.query("gols > 0").copy()
    total_gols = int(elenco.gols.sum())
    craque = com_gol.iloc[0]
    participacoes = int(craque.gols) + int(craque.assistencias)

    colunas = st.columns(4)
    colunas[0].metric("Gols do time", total_gols)
    colunas[1].metric("Jogadores que marcaram", len(com_gol))
    colunas[2].metric(f"Gols de {craque.jogador}", int(craque.gols),
                      f"{100 * craque.gols / total_gols:.0f}% do time", delta_color="off")
    colunas[3].metric("Participações diretas", participacoes,
                      f"{100 * participacoes / total_gols:.0f}% dos gols", delta_color="off")

    st.plotly_chart(_gols_por_jogador(elenco, craque.jogador), use_container_width=True)

    st.markdown(
        f"**{craque.jogador}** participou de **{participacoes} dos {total_gols} gols** "
        f"({100 * participacoes / total_gols:.0f}%) somando gols e assistências, e foi o "
        "único jogador do Inter a aparecer em qualquer ranking individual do campeonato "
        "— 4º em assistências. O segundo maior artilheiro do elenco fez "
        f"{int(com_gol.gols.iloc[1])} gols."
    )

    st.plotly_chart(_conversao(com_gol), use_container_width=True)

    with st.expander("Ver dados"):
        st.dataframe(
            elenco.rename(columns={
                "jogador": "Jogador", "posicao": "Posição", "jogos": "Jogos",
                "titular": "Titular", "minutos": "Minutos", "gols": "Gols",
                "assistencias": "Assistências", "chutes": "Chutes",
                "chutes_no_alvo": "No alvo", "amarelos": "CA", "vermelhos": "CV",
            }),
            hide_index=True, use_container_width=True,
        )


def _gols_por_jogador(elenco, destaque: str) -> go.Figure:
    """Participação em gols por jogador.

    A cor identifica a métrica (gol ou assistência) e vale para todos os
    jogadores — colorir só o destaque quebraria a legenda, que passaria a
    mostrar dois quadradinhos cinzas. O destaque fica por conta da magnitude,
    que já é 2,5× a do segundo colocado, mais um rótulo direto.
    """
    topo = (
        elenco.query("gols > 0 or assistencias > 0")
        .nlargest(QUANTOS_MOSTRAR, ["gols", "assistencias"])
        .sort_values(["gols", "assistencias"])
    )

    for coluna, cor, rotulo in (
        ("gols", tema.SERIE_1, "Gols"),
        ("assistencias", tema.SERIE_3, "Assistências"),
    ):
        if coluna == "gols":
            figura = go.Figure()
        figura.add_trace(
            go.Bar(
                y=topo.jogador, x=topo[coluna], orientation="h", name=rotulo,
                marker={"color": cor, "line": {"width": 2, "color": tema.SUPERFICIE}},
                hovertemplate=f"%{{y}} — {rotulo}: %{{x}}<extra></extra>",
            )
        )

    participacoes = topo.gols + topo.assistencias
    total = int(participacoes[topo.jogador == destaque].iloc[0])
    figura.add_annotation(
        x=total, y=destaque, text=f"  {total} participações", showarrow=False,
        xanchor="left", font={"color": tema.TINTA_2, "size": 12},
    )

    return tema.aplicar(
        figura,
        altura=460,
        title={"text": "Participação em gols no Brasileirão"},
        xaxis={"title": {"text": "Gols + assistências"},
               "range": [0, participacoes.max() * 1.25]},
        yaxis={"title": {"text": ""}},
        barmode="stack",
        bargap=0.35,
        margin={"l": 150, "r": 60},
    )


def _conversao(com_gol) -> go.Figure:
    """Chutes contra gols: quem finalizou muito e converteu pouco."""
    figura = go.Figure(
        go.Scatter(
            x=com_gol.chutes, y=com_gol.gols, mode="markers+text",
            text=com_gol.jogador, textposition="top center",
            textfont={"color": tema.TINTA_2, "size": 11},
            marker={"color": tema.SERIE_1, "size": 13,
                    "line": {"width": 2, "color": tema.SUPERFICIE}},
            hovertemplate=("%{text}<br>%{x} chutes · %{y} gols<extra></extra>"),
            showlegend=False,
        )
    )

    return tema.aplicar(
        figura,
        legenda=False,
        altura=400,
        title={"text": "Chutes contra gols, por jogador"},
        xaxis={"title": {"text": "Chutes no campeonato"}, "rangemode": "tozero"},
        yaxis={"title": {"text": "Gols"}, "rangemode": "tozero", "dtick": 2},
        margin={"t": 60},
    )

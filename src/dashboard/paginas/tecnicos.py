"""Comparativo entre os três técnicos de 2025."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from src.dashboard import dados, tema

AMOSTRA_MINIMA = 5


def render() -> None:
    st.header("Os três técnicos")

    tecnicos = dados.desempenho_tecnicos()

    colunas = st.columns(len(tecnicos))
    for coluna, (_, tecnico) in zip(colunas, tecnicos.iterrows()):
        coluna.metric(
            tecnico.tecnico,
            f"{tecnico.aproveitamento:.1f}%",
            f"rodadas {int(tecnico.rodada_inicio)}–{int(tecnico.rodada_fim)} "
            f"({int(tecnico.jogos)} jogos)",
            delta_color="off",
        )

    st.plotly_chart(_aproveitamento(tecnicos), use_container_width=True)

    curtos = tecnicos.query("jogos < @AMOSTRA_MINIMA")
    if not curtos.empty:
        nomes = " e ".join(curtos.tecnico)
        st.warning(
            f"⚠️ {nomes} dirigiu apenas {int(curtos.jogos.iloc[0])} jogos. "
            "O percentual não é comparável estatisticamente aos demais — "
            "o número de jogos está ao lado de cada barra por isso.",
            icon="⚠️",
        )

    st.plotly_chart(_gols(tecnicos), use_container_width=True)

    estaveis = tecnicos.query("jogos >= @AMOSTRA_MINIMA")
    if len(estaveis) >= 2:
        diferenca = abs(estaveis.aproveitamento.iloc[0] - estaveis.aproveitamento.iloc[1])
        st.caption(
            f"Entre os dois técnicos com amostra relevante a diferença é de "
            f"{diferenca:.1f} ponto percentual. A troca de comando não mudou o "
            "patamar do time — o problema era outro."
        )

    with st.expander("Ver dados"):
        st.dataframe(
            tecnicos.rename(columns={
                "tecnico": "Técnico", "rodada_inicio": "Da rodada",
                "rodada_fim": "Até", "jogos": "Jogos", "pontos": "Pontos",
                "gols_pro": "Gols marcados", "gols_contra": "Gols sofridos",
                "aproveitamento": "Aproveitamento %",
            }),
            hide_index=True, use_container_width=True,
        )


def _aproveitamento(tecnicos) -> go.Figure:
    """Categorias nominais: uma cor só, nunca gradiente por valor."""
    rotulos = [f"{t.aproveitamento:.1f}%  ({int(t.jogos)} jogos)"
               for _, t in tecnicos.iterrows()]

    figura = go.Figure(
        go.Bar(
            y=tecnicos.tecnico, x=tecnicos.aproveitamento, orientation="h",
            marker={"color": tema.SERIE_1}, text=rotulos, textposition="outside",
            textfont={"color": tema.TINTA_2},
            hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
            showlegend=False,
        )
    )

    return tema.aplicar(
        figura,
        altura=300,
        title={"text": "Aproveitamento de pontos por período"},
        xaxis={"title": {"text": "% dos pontos disputados"}, "range": [0, 72]},
        yaxis={"title": {"text": ""}, "autorange": "reversed"},
        margin={"l": 130, "r": 140},
        bargap=0.4,
    )


def _gols(tecnicos) -> go.Figure:
    figura = go.Figure()
    for coluna, cor, rotulo in (
        ("gols_pro", tema.SERIE_1, "Marcados"),
        ("gols_contra", tema.SERIE_2, "Sofridos"),
    ):
        por_jogo = tecnicos[coluna] / tecnicos.jogos
        figura.add_trace(
            go.Bar(
                x=tecnicos.tecnico, y=por_jogo, name=rotulo,
                marker={"color": cor},
                text=[f"{v:.2f}" for v in por_jogo], textposition="outside",
                textfont={"color": tema.TINTA_2},
                hovertemplate=f"{rotulo}: %{{y:.2f}} por jogo<extra></extra>",
            )
        )

    return tema.aplicar(
        figura,
        altura=340,
        title={"text": "Gols por jogo em cada período"},
        xaxis={"title": {"text": ""}},
        yaxis={"title": {"text": "Gols por jogo"}, "rangemode": "tozero"},
        barmode="group",
        bargap=0.45,
        bargroupgap=0.08,
    )

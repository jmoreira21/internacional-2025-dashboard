"""Comparativo entre os três técnicos de 2025."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from src.dashboard import dados, estilo, tema

AMOSTRA_MINIMA = 5


def secao(numero: int) -> None:
    tecnicos = dados.desempenho_tecnicos()
    estaveis = tecnicos.query("jogos >= @AMOSTRA_MINIMA")
    diferenca = (
        abs(estaveis.aproveitamento.iloc[0] - estaveis.aproveitamento.iloc[1])
        if len(estaveis) >= 2 else 0.0
    )

    estilo.secao(
        numero,
        "Trocar de técnico não mudou o patamar.",
        f"Roger Machado entregou {estaveis.aproveitamento.iloc[0]:.1f}% dos pontos em "
        f"{int(estaveis.jogos.iloc[0])} jogos; Ramón Díaz, "
        f"{estaveis.aproveitamento.iloc[1]:.1f}% em {int(estaveis.jogos.iloc[1])}. "
        f"<strong>{diferenca:.1f} ponto percentual de diferença</strong> — ruído, não "
        "mudança de patamar. O problema do time não estava no banco.",
    )

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
        legenda=False,
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

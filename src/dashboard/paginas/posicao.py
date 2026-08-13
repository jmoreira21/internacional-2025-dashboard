"""Linha do tempo da posição na tabela — a briga contra o Z4."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from src.dashboard import dados, tema

Z4_INICIO = 17
TOTAL_TIMES = 20


def render() -> None:
    st.header("A briga contra o Z4")

    posicoes = dados.posicoes_por_rodada()
    inter = posicoes.query("sigla == 'INT'").sort_values("rodada")
    rodadas_no_z4 = inter.query("posicao >= @Z4_INICIO")

    esquerda, meio, direita = st.columns(3)
    esquerda.metric("Pior posição no ano", f"{int(inter.posicao.max())}º")
    meio.metric("Rodadas dentro do Z4", len(rodadas_no_z4))
    direita.metric("Posição final", f"{int(inter.posicao.iloc[-1])}º")

    st.plotly_chart(_grafico(posicoes, inter), use_container_width=True)

    if len(rodadas_no_z4):
        rodadas = ", ".join(str(r) for r in rodadas_no_z4.rodada)
        st.caption(
            f"O Inter esteve no Z4 nas rodadas {rodadas} — e saiu na última, "
            "vencendo o Bragantino por 3–1."
        )

    with st.expander("Ver dados"):
        st.dataframe(
            inter[["rodada", "posicao"]].rename(
                columns={"rodada": "Rodada", "posicao": "Posição"}
            ),
            hide_index=True,
            use_container_width=True,
        )


def _grafico(posicoes, inter) -> go.Figure:
    """Ênfase: o Inter em cor, os demais recuados em cinza."""
    figura = go.Figure()

    # Os 19 rivais são contexto, não séries: bem recuados, para não competir
    # com a linha que interessa.
    for sigla, grupo in posicoes.query("sigla != 'INT'").groupby("sigla"):
        grupo = grupo.sort_values("rodada")
        figura.add_trace(
            go.Scatter(
                x=grupo.rodada,
                y=grupo.posicao,
                mode="lines",
                line={"color": tema.NEUTRO, "width": 1, "shape": "spline"},
                opacity=0.2,
                hovertemplate=f"{grupo.nome.iloc[0]}<br>rodada %{{x}}: %{{y}}º<extra></extra>",
                showlegend=False,
                name=sigla,
            )
        )

    figura.add_trace(
        go.Scatter(
            x=inter.rodada,
            y=inter.posicao,
            mode="lines+markers",
            line={"color": tema.SERIE_1, "width": 2},
            marker={"size": 8, "color": tema.SERIE_1,
                    "line": {"width": 2, "color": tema.SUPERFICIE}},
            name="Internacional",
            showlegend=False,  # série única: o título já a nomeia
            hovertemplate="Internacional<br>rodada %{x}: %{y}º<extra></extra>",
        )
    )

    figura.add_hrect(
        y0=Z4_INICIO - 0.5,
        y1=TOTAL_TIMES + 0.5,
        fillcolor=tema.CRITICO,
        opacity=0.07,
        line_width=0,
        layer="below",
    )
    figura.add_annotation(
        x=1, y=TOTAL_TIMES, text="Zona de rebaixamento", showarrow=False,
        xanchor="left", font={"color": tema.CRITICO, "size": 12},
    )
    figura.add_annotation(
        x=int(inter.rodada.iloc[-1]),
        y=int(inter.posicao.iloc[-1]),
        text=f"  {int(inter.posicao.iloc[-1])}º",
        showarrow=False, xanchor="left",
        font={"color": tema.SERIE_1, "size": 13},
    )

    return tema.aplicar(
        figura,
        legenda=False,
        altura=460,
        title={"text": "Internacional: posição ao fim de cada rodada "
                       "<span style='color:#898781'>(cinza = os outros 19 times)</span>"},
        xaxis={"title": {"text": "Rodada"}, "dtick": 4, "range": [0, 40]},
        yaxis={
            "title": {"text": "Posição"},
            "autorange": "reversed",
            "dtick": 1,
            "range": [20.5, 0.5],
            "tickvals": [1, 5, 10, 15, 17, 20],
        },
        hovermode="x unified",
    )

"""Linha do tempo da posição na tabela — a briga contra o Z4."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from src.dashboard import dados, estilo, tema

Z4_INICIO = 17
TOTAL_TIMES = 20


def secao(numero: int) -> None:
    posicoes = dados.posicoes_por_rodada()
    inter = posicoes.query("sigla == 'INT'").sort_values("rodada")
    rodadas_no_z4 = inter.query("posicao >= @Z4_INICIO")
    rodadas = ", ".join(str(r) for r in rodadas_no_z4.rodada)

    estilo.secao(
        numero,
        "A conta só fechou na última rodada.",
        f"O Inter passou <strong>{len(rodadas_no_z4)} rodadas dentro do Z4</strong> "
        f"(a {rodadas}) e chegou à 38ª em {int(inter.posicao.iloc[-2])}º, dentro da zona. "
        "Precisou vencer o Bragantino por 3–1 para terminar em "
        f"{int(inter.posicao.iloc[-1])}º. A temporada inteira de ineficiência foi resolvida "
        "em noventa minutos — e podia não ter sido.",
    )

    st.plotly_chart(_grafico(inter), use_container_width=True)

    with st.expander("Ver dados"):
        st.dataframe(
            inter[["rodada", "posicao"]].rename(
                columns={"rodada": "Rodada", "posicao": "Posição"}
            ),
            hide_index=True,
            use_container_width=True,
        )


def _grafico(inter) -> go.Figure:
    """Só a linha do Inter: os 19 rivais tornavam o hover ilegível."""
    figura = go.Figure()

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

    # A faixa do Z4 fica num lavado neutro: o vermelho já é a linha do Inter, e
    # repetir a cor faria a zona competir com o assunto do gráfico.
    figura.add_hrect(
        y0=Z4_INICIO - 0.5,
        y1=TOTAL_TIMES + 0.5,
        fillcolor="#ffffff",
        opacity=0.04,
        line_width=0,
        layer="below",
    )
    figura.add_annotation(
        x=1, y=TOTAL_TIMES, text="Zona de rebaixamento", showarrow=False,
        xanchor="left", font={"color": tema.MUDO, "size": 12},
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
        title={"text": "Internacional: posição ao fim de cada rodada"},
        xaxis={"title": {"text": "Rodada"}, "dtick": 4, "range": [0, 40]},
        yaxis={
            "title": {"text": "Posição"},
            "autorange": "reversed",
            "dtick": 1,
            "range": [20.5, 0.5],
            "tickvals": [1, 5, 10, 15, 17, 20],
        },
        hovermode="closest",
    )

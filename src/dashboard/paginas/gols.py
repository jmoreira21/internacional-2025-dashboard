"""Gols marcados e sofridos por rodada, com médias móveis."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from src.dashboard import dados, tema

JANELA = 5


def render() -> None:
    st.header("Gols marcados e sofridos")

    jogos = dados.jogos_do_inter().copy()
    jogos["media_pro"] = jogos.gols_pro.rolling(JANELA, min_periods=1).mean()
    jogos["media_contra"] = jogos.gols_contra.rolling(JANELA, min_periods=1).mean()

    casa = jogos.query("mando == 'casa'")
    fora = jogos.query("mando == 'fora'")

    colunas = st.columns(4)
    colunas[0].metric("Gols marcados", int(jogos.gols_pro.sum()))
    colunas[1].metric("Gols sofridos", int(jogos.gols_contra.sum()))
    colunas[2].metric("Aproveitamento em casa",
                      f"{100 * casa.pontos.sum() / (len(casa) * 3):.0f}%",
                      f"{int(casa.gols_pro.sum())}:{int(casa.gols_contra.sum())}",
                      delta_color="off")
    colunas[3].metric("Aproveitamento fora",
                      f"{100 * fora.pontos.sum() / (len(fora) * 3):.0f}%",
                      f"{int(fora.gols_pro.sum())}:{int(fora.gols_contra.sum())}",
                      delta_color="off")

    st.plotly_chart(_medias_moveis(jogos), use_container_width=True)
    st.plotly_chart(_saldo_por_rodada(jogos), use_container_width=True)

    st.caption(
        f"Fora de casa o Inter sofreu {int(fora.gols_contra.sum())} gols em {len(fora)} jogos "
        f"— quase o dobro dos {int(casa.gols_contra.sum())} que sofreu no Beira-Rio."
    )

    with st.expander("Ver dados"):
        st.dataframe(
            jogos[["rodada", "mando", "adversario", "gols_pro", "gols_contra", "resultado"]]
            .rename(columns={
                "rodada": "Rodada", "mando": "Mando", "adversario": "Adversário",
                "gols_pro": "Marcados", "gols_contra": "Sofridos", "resultado": "Resultado",
            }),
            hide_index=True, use_container_width=True,
        )


def _medias_moveis(jogos) -> go.Figure:
    figura = go.Figure()

    for coluna, cor, rotulo in (
        ("gols_pro", tema.SERIE_1, "Marcados"),
        ("gols_contra", tema.SERIE_2, "Sofridos"),
    ):
        figura.add_trace(
            go.Scatter(
                x=jogos.rodada, y=jogos[coluna], mode="markers",
                marker={"size": 7, "color": cor, "opacity": 0.35},
                name=f"{rotulo} (rodada)", showlegend=False, hoverinfo="skip",
            )
        )

    for coluna, cor, rotulo in (
        ("media_pro", tema.SERIE_1, "Marcados"),
        ("media_contra", tema.SERIE_2, "Sofridos"),
    ):
        figura.add_trace(
            go.Scatter(
                x=jogos.rodada, y=jogos[coluna], mode="lines",
                line={"color": cor, "width": 2}, name=rotulo,
                hovertemplate=f"{rotulo}: %{{y:.2f}}<extra></extra>",
            )
        )

    return tema.aplicar(
        figura,
        title={"text": f"Média móvel de {JANELA} rodadas (pontos claros = jogo a jogo)"},
        xaxis={"title": {"text": "Rodada"}, "dtick": 4},
        yaxis={"title": {"text": "Gols por jogo"}, "rangemode": "tozero"},
        hovermode="x unified",
    )


def _saldo_por_rodada(jogos) -> go.Figure:
    """Barra divergente: azul acima de zero, vermelho abaixo."""
    cores = [tema.SERIE_1 if saldo > 0 else tema.CRITICO if saldo < 0 else tema.NEUTRO
             for saldo in jogos.saldo]

    figura = go.Figure(
        go.Bar(
            x=jogos.rodada, y=jogos.saldo, marker={"color": cores},
            customdata=jogos[["adversario", "gols_pro", "gols_contra"]],
            hovertemplate=("rodada %{x} vs %{customdata[0]}<br>"
                           "%{customdata[1]}–%{customdata[2]}<extra></extra>"),
            showlegend=False,
        )
    )
    figura.add_hline(y=0, line={"color": tema.EIXO, "width": 1})

    return tema.aplicar(
        figura,
        legenda=False,
        altura=300,
        title={"text": "Saldo de gols por rodada"},
        xaxis={"title": {"text": "Rodada"}, "dtick": 4},
        yaxis={"title": {"text": "Saldo"}, "dtick": 2},
        bargap=0.35,
    )

"""Gols marcados e sofridos por rodada, com médias móveis."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from src.dashboard import dados, estilo, tema

JANELA = 5


def secao(numero: int) -> None:
    jogos = dados.jogos_do_inter().copy()
    jogos["media_pro"] = jogos.gols_pro.rolling(JANELA, min_periods=1).mean()
    jogos["media_contra"] = jogos.gols_contra.rolling(JANELA, min_periods=1).mean()

    casa = jogos.query("mando == 'casa'")
    fora = jogos.query("mando == 'fora'")
    aproveitamento_casa = 100 * casa.pontos.sum() / (len(casa) * 3)
    aproveitamento_fora = 100 * fora.pontos.sum() / (len(fora) * 3)

    estilo.secao(
        numero,
        "Longe do Beira-Rio, o time desabava.",
        f"Em casa o Inter fez <strong>{aproveitamento_casa:.0f}% dos pontos</strong> e sofreu "
        f"{int(casa.gols_contra.sum())} gols. Fora, <strong>{aproveitamento_fora:.0f}%</strong> "
        f"e <strong>{int(fora.gols_contra.sum())} gols sofridos em {len(fora)} jogos</strong> — "
        "quase dois por partida. É a diferença que explica a maior parte dos pontos que "
        "faltaram.",
    )

    colunas = st.columns(2, gap="medium")
    with colunas[0]:
        st.plotly_chart(_casa_fora(casa, fora), use_container_width=True)
    with colunas[1]:
        st.plotly_chart(_medias_moveis(jogos), use_container_width=True)

    st.plotly_chart(_saldo_por_rodada(jogos), use_container_width=True)

    with st.expander("Ver dados"):
        st.dataframe(
            jogos[["rodada", "mando", "adversario", "gols_pro", "gols_contra", "resultado"]]
            .rename(columns={
                "rodada": "Rodada", "mando": "Mando", "adversario": "Adversário",
                "gols_pro": "Marcados", "gols_contra": "Sofridos", "resultado": "Resultado",
            }),
            hide_index=True, use_container_width=True,
        )


def _casa_fora(casa, fora) -> go.Figure:
    """Gols por jogo dentro e fora, nas mesmas cores do resto da seção."""
    grupos = [("Em casa", casa), ("Fora", fora)]

    figura = go.Figure()
    for coluna, cor, rotulo in (
        ("gols_pro", tema.SERIE_1, "Marcados"),
        ("gols_contra", tema.SERIE_2, "Sofridos"),
    ):
        por_jogo = [g[coluna].sum() / len(g) for _, g in grupos]
        figura.add_trace(
            go.Bar(
                x=[nome for nome, _ in grupos], y=por_jogo, name=rotulo,
                marker={"color": cor, "line": {"width": 2, "color": tema.SUPERFICIE}},
                text=[f"{v:.2f}" for v in por_jogo], textposition="outside",
                textfont={"color": tema.TINTA_2},
                hovertemplate=f"{rotulo}: %{{y:.2f}} por jogo<extra></extra>",
            )
        )

    return tema.aplicar(
        figura,
        altura=330,
        title={"text": "Gols por jogo, dentro e fora"},
        xaxis={"title": {"text": ""}},
        yaxis={"title": {"text": "Gols por jogo"}, "rangemode": "tozero", "range": [0, 2.4]},
        barmode="group",
        bargap=0.45,
        bargroupgap=0.06,
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
    """Barra divergente sobre o zero.

    Vermelho para cima é o Inter marcando mais, azul para baixo é o adversário
    — os mesmos papéis de cor do gráfico acima, para o leitor não ter que
    reaprender a legenda.
    """
    cores = [tema.SERIE_1 if saldo > 0 else tema.SERIE_2 if saldo < 0 else tema.NEUTRO
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

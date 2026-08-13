"""Comparação com os outros times da parte de baixo da tabela."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from src.dashboard import dados, tema

Z4_INICIO = 17
PARTE_DE_BAIXO = 14


def render() -> None:
    st.header("Inter e os rivais da parte de baixo")

    times = dados.xg_dos_times()
    inter = times.query("sigla == 'INT'").iloc[0]

    colunas = st.columns(3)
    colunas[0].metric("Pontos", int(inter.pontos),
                      f"{inter.diferenca_pontos:+.1f} vs esperado", delta_color="off")
    colunas[1].metric("Posição por pontos esperados",
                      f"{int(times.pontos_esperados.rank(ascending=False)[inter.name])}º",
                      f"{inter.pontos_esperados:.1f} xPts", delta_color="off")
    colunas[2].metric("Posição real", f"{int(inter.posicao)}º")

    st.plotly_chart(_dispersao(times), use_container_width=True)
    st.plotly_chart(_deficit(times), use_container_width=True)

    st.caption(
        "Pelo modelo de xG, o Inter gerou o 4º maior total de pontos esperados da liga "
        "e terminou em 16º. Nenhum outro time da parte de baixo criou tanto."
    )

    with st.expander("Ver dados"):
        st.dataframe(
            times[["posicao", "nome", "pontos", "pontos_esperados", "gols_pro", "xg",
                   "gols_contra", "xg_contra"]]
            .rename(columns={
                "posicao": "Pos", "nome": "Time", "pontos": "Pts",
                "pontos_esperados": "xPts", "gols_pro": "GP", "xg": "xG",
                "gols_contra": "GC", "xg_contra": "xGC",
            }),
            hide_index=True, use_container_width=True,
        )


def _classe(time) -> str:
    if time.sigla == "INT":
        return "Internacional"
    if time.posicao >= Z4_INICIO:
        return "Rebaixados"
    return "Demais"


def _dispersao(times) -> go.Figure:
    """Ênfase em três classes — o teto para formas de dispersão."""
    times = times.assign(classe=times.apply(_classe, axis=1))
    estilos = {
        "Demais": (tema.NEUTRO, 9),
        "Rebaixados": (tema.SERIE_2, 12),
        "Internacional": (tema.SERIE_1, 16),
    }

    figura = go.Figure()
    for classe, (cor, tamanho) in estilos.items():
        grupo = times.query("classe == @classe")
        figura.add_trace(
            go.Scatter(
                x=grupo.xg, y=grupo.xg_contra, mode="markers", name=classe,
                marker={"color": cor, "size": tamanho,
                        "line": {"width": 2, "color": tema.SUPERFICIE}},
                customdata=grupo[["nome", "posicao", "pontos"]],
                hovertemplate=("%{customdata[0]} (%{customdata[1]}º)<br>"
                               "xG %{x:.1f} · xG contra %{y:.1f}<extra></extra>"),
            )
        )

    for _, time in times.query("classe != 'Demais'").iterrows():
        figura.add_annotation(
            x=time.xg, y=time.xg_contra, text=f"  {time.sigla}", showarrow=False,
            xanchor="left", font={"color": tema.TINTA_2, "size": 11},
        )

    return tema.aplicar(
        figura,
        altura=440,
        title={"text": "Chances criadas × chances cedidas (xG da temporada)"},
        xaxis={"title": {"text": "xG a favor  →  cria mais"}},
        yaxis={"title": {"text": "xG contra  →  cede mais"}},
    )


def _deficit(times) -> go.Figure:
    """Barra divergente: pontos reais menos pontos esperados."""
    baixo = times.query("posicao >= @PARTE_DE_BAIXO").sort_values("diferenca_pontos")
    cores = [tema.SERIE_1 if sigla == "INT" else tema.NEUTRO for sigla in baixo.sigla]

    figura = go.Figure(
        go.Bar(
            y=baixo.nome, x=baixo.diferenca_pontos, orientation="h",
            marker={"color": cores},
            text=[f"{v:+.1f}" for v in baixo.diferenca_pontos],
            textposition="outside", textfont={"color": tema.TINTA_2},
            hovertemplate="%{y}: %{x:+.1f} pontos<extra></extra>",
            showlegend=False,
        )
    )
    figura.add_vline(x=0, line={"color": tema.EIXO, "width": 1})

    return tema.aplicar(
        figura,
        altura=360,
        title={"text": "Pontos feitos menos pontos esperados (do 14º ao 20º)"},
        xaxis={"title": {"text": "← ficou abaixo do esperado    acima →"}},
        yaxis={"title": {"text": ""}},
        margin={"l": 150, "r": 70},
        bargap=0.35,
    )

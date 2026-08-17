"""Comparação com os outros times da parte de baixo da tabela."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from src.dashboard import dados, estilo, tema

Z4_INICIO = 17
PARTE_DE_BAIXO = 14


def secao(numero: int) -> None:
    times = dados.xg_dos_times()
    inter = times.query("sigla == 'INT'").iloc[0]
    posicao_esperada = int(times.pontos_esperados.rank(ascending=False)[inter.name])

    estilo.secao(
        numero,
        "Não foi falta de criar chances.",
        f"Pelo modelo de xG, o Inter gerou o <strong>{posicao_esperada}º maior total de "
        f"pontos esperados</strong> do campeonato — {inter.pontos_esperados:.1f} — e terminou "
        f"em {int(inter.posicao)}º com {int(inter.pontos)} pontos. Na dispersão abaixo ele "
        "aparece longe do grupo que caiu: criava muito mais do que os rivais da parte de "
        "baixo.",
    )

    colunas = st.columns([1.25, 1], gap="medium")
    with colunas[0]:
        st.plotly_chart(_dispersao(times), use_container_width=True)
    with colunas[1]:
        st.plotly_chart(_deficit(times), use_container_width=True)

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

    # Folga nas duas pontas para os rótulos externos não encostarem na borda.
    limite_esquerdo = baixo.diferenca_pontos.min() * 1.22
    limite_direito = max(baixo.diferenca_pontos.max() * 2.4, 2.0)

    return tema.aplicar(
        figura,
        legenda=False,
        altura=360,
        title={"text": "Pontos feitos menos pontos esperados (do 14º ao 20º)"},
        xaxis={"title": {"text": "← ficou abaixo do esperado    acima →"},
               "range": [limite_esquerdo, limite_direito]},
        yaxis={"title": {"text": ""}},
        margin={"l": 150, "r": 70},
        bargap=0.35,
    )

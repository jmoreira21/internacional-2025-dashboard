"""Mapa de chutes com as coordenadas do FotMob."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from src.dashboard import dados, estilo, tema

# Campo em metros, no padrão FIFA. Nos dados do FotMob o gol atacado fica em
# x = 105 e a largura em y = 0..68.
#
# O mapa é desenhado na vertical, que é a convenção para shot maps e aproveita
# melhor o espaço (a largura do campo, 68 m, é maior que o trecho de
# comprimento mostrado): o eixo horizontal do gráfico recebe a LARGURA do campo
# e o vertical, o COMPRIMENTO, com o gol no topo.
COMPRIMENTO, LARGURA = 105.0, 68.0
GRANDE_AREA = {"inicio": 88.5, "de": 13.84, "ate": 54.16}
PEQUENA_AREA = {"inicio": 99.5, "de": 24.84, "ate": 43.16}
MARCA_PENALTI = 94.0
TRAVE_ESQUERDA, TRAVE_DIREITA = 30.34, 37.66

# O campo é recortado no último terço: 515 dos 517 chutes acontecem daqui para
# frente, e mostrar o campo inteiro deixaria dois terços da figura vazios. Os
# chutes de trás do recorte continuam na tabela ao pé da página.
INICIO_DO_RECORTE = 58.0


def render() -> None:
    estilo.rotulo_secao("Mapa de chutes")

    todos = dados.chutes()
    # Gols contra ficam registrados no campo de defesa e não são finalizações
    # do Inter ao gol adversário.
    chutes = todos.query("desfecho != 'gol contra'").copy()

    situacoes = ["Todas", *sorted(chutes.situacao.dropna().unique())]
    escolha = st.radio("Situação de jogo", situacoes, horizontal=True)
    if escolha != "Todas":
        chutes = chutes.query("situacao == @escolha")

    if chutes.empty:
        st.info("Nenhum chute nessa situação.")
        return

    gols = chutes.query("desfecho == 'gol'")
    dentro = chutes.query("dentro_area == 1")

    colunas = st.columns(4)
    colunas[0].metric("Chutes", len(chutes))
    colunas[1].metric("Gols", len(gols))
    colunas[2].metric("xG total", f"{chutes.xg.sum():.1f}")
    colunas[3].metric("Dentro da área", f"{100 * len(dentro) / len(chutes):.0f}%",
                      f"{dentro.xg.sum():.1f} xG", delta_color="off")

    st.plotly_chart(_mapa(chutes), use_container_width=True)

    fora_do_recorte = int((chutes.x < INICIO_DO_RECORTE).sum())
    nota_recorte = (
        f" {fora_do_recorte} chute(s) de trás do recorte não aparecem no campo, "
        "mas estão na tabela abaixo."
        if fora_do_recorte else ""
    )
    st.caption(
        "O tamanho do ponto é o xG do chute. A área é onde o Inter finalizava — "
        f"{100 * len(dentro) / len(chutes):.0f}% dos chutes e "
        f"{100 * dentro.xg.sum() / chutes.xg.sum():.0f}% do xG saíram de dentro dela. "
        "O problema não era de onde chutava." + nota_recorte
    )

    st.plotly_chart(_por_situacao(todos.query("desfecho != 'gol contra'")),
                    use_container_width=True)

    with st.expander("Ver dados"):
        st.dataframe(
            chutes[["rodada", "adversario", "jogador", "minuto", "xg", "desfecho",
                    "situacao", "tipo_chute"]]
            .rename(columns={
                "rodada": "Rodada", "adversario": "Adversário", "jogador": "Jogador",
                "minuto": "Min", "xg": "xG", "desfecho": "Desfecho",
                "situacao": "Situação", "tipo_chute": "Tipo",
            }),
            hide_index=True, use_container_width=True,
        )


def _formas_do_campo() -> list[dict]:
    """Linhas do campo, já na orientação vertical (gol no topo)."""
    linha = {"color": tema.EIXO, "width": 1}

    def retangulo(de: float, ate: float, inicio: float, fim: float) -> dict:
        return {"type": "rect", "line": linha, "layer": "below",
                "x0": de, "x1": ate, "y0": inicio, "y1": fim}

    return [
        retangulo(0, LARGURA, INICIO_DO_RECORTE, COMPRIMENTO),
        retangulo(GRANDE_AREA["de"], GRANDE_AREA["ate"], GRANDE_AREA["inicio"], COMPRIMENTO),
        retangulo(PEQUENA_AREA["de"], PEQUENA_AREA["ate"], PEQUENA_AREA["inicio"], COMPRIMENTO),
        {"type": "circle", "layer": "below", "line": linha, "fillcolor": tema.EIXO,
         "x0": LARGURA / 2 - 0.4, "x1": LARGURA / 2 + 0.4,
         "y0": MARCA_PENALTI - 0.4, "y1": MARCA_PENALTI + 0.4},
        # meia-lua na entrada da área
        {"type": "path", "layer": "below", "line": linha,
         "path": "M 26.7,88.5 C 30,82 38,82 41.3,88.5"},
        # gol
        {"type": "rect", "layer": "below", "line": {"color": tema.MUDO, "width": 3},
         "x0": TRAVE_ESQUERDA, "x1": TRAVE_DIREITA,
         "y0": COMPRIMENTO, "y1": COMPRIMENTO + 1.8},
    ]


def _mapa(chutes) -> go.Figure:
    """Ênfase: gols em cor, demais finalizações recuadas.

    O eixo horizontal é a largura do campo e o vertical, o comprimento — os
    papéis de x e y dos dados do FotMob são trocados de propósito.
    """
    figura = go.Figure()

    grupos = [
        ("Finalizações", chutes.query("desfecho != 'gol'"), tema.NEUTRO, 0.7),
        ("Gols", chutes.query("desfecho == 'gol'"), tema.SERIE_1, 0.9),
    ]
    for rotulo, grupo, cor, opacidade in grupos:
        if grupo.empty:
            continue
        figura.add_trace(
            go.Scatter(
                x=grupo.y, y=grupo.x, mode="markers", name=rotulo,
                marker={
                    "color": cor,
                    # xG vai de ~0 a ~0,8; 7 a 25 px mantém os pontos legíveis
                    # sem virar bolha sobreposta.
                    "size": grupo.xg.fillna(0.01) * 24 + 7,
                    "opacity": opacidade,
                    "line": {"width": 2, "color": tema.SUPERFICIE},
                },
                customdata=grupo[["jogador", "rodada", "adversario", "xg", "desfecho"]],
                hovertemplate=(
                    "%{customdata[0]}<br>rodada %{customdata[1]} vs %{customdata[2]}"
                    "<br>xG %{customdata[3]:.2f} · %{customdata[4]}<extra></extra>"
                ),
            )
        )

    return tema.aplicar(
        figura,
        altura=560,
        title={"text": "Onde o Inter finalizou — tamanho do ponto = xG"},
        shapes=_formas_do_campo(),
        xaxis={"visible": False, "range": [-2, LARGURA + 2]},
        yaxis={"visible": False, "range": [INICIO_DO_RECORTE - 1, COMPRIMENTO + 4],
               "scaleanchor": "x", "scaleratio": 1},
        margin={"l": 24, "r": 24, "t": 96, "b": 24},
    )


def _por_situacao(chutes) -> go.Figure:
    """Categorias nominais de situação de jogo: uma cor só."""
    resumo = (
        chutes.groupby("situacao")
        .agg(chutes=("xg", "size"), xg=("xg", "sum"),
             gols=("desfecho", lambda s: (s == "gol").sum()))
        .sort_values("chutes", ascending=True)
        .reset_index()
    )

    figura = go.Figure(
        go.Bar(
            y=resumo.situacao, x=resumo.chutes, orientation="h",
            marker={"color": tema.SERIE_1},
            text=[f"{int(c)} chutes · {g} gols · {x:.1f} xG"
                  for c, g, x in zip(resumo.chutes, resumo.gols, resumo.xg)],
            textposition="outside", textfont={"color": tema.TINTA_2},
            hovertemplate="%{y}: %{x} chutes<extra></extra>",
            showlegend=False,
        )
    )

    return tema.aplicar(
        figura,
        legenda=False,
        altura=340,
        title={"text": "Finalizações por situação de jogo"},
        xaxis={"title": {"text": "Chutes"},
               "range": [0, resumo.chutes.max() * 1.6]},
        yaxis={"title": {"text": ""}},
        margin={"l": 130, "r": 40},
        bargap=0.4,
    )

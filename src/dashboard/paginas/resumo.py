"""Visão geral — a temporada inteira numa tela."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from src.dashboard import dados, estilo, tema

Z4_INICIO = 17
ULTIMOS = 5


def render() -> None:
    coluna_lateral, coluna_principal = st.columns([1, 3], gap="medium")

    with coluna_lateral:
        _mini_tabela()
        st.write("")
        _ultimos_jogos()

    with coluna_principal:
        _periodos_dos_tecnicos()
        st.write("")
        graficos = st.columns([1.35, 1], gap="medium")
        with graficos[0]:
            st.plotly_chart(_evolucao(), use_container_width=True)
        with graficos[1]:
            st.plotly_chart(_eficiencia(), use_container_width=True)


def _mini_tabela() -> None:
    estilo.rotulo_secao("Classificação · parte de baixo")
    tabela = dados.classificacao().query("posicao >= 14")

    linhas = []
    for _, time in tabela.iterrows():
        destaque = " destaque" if time.sigla == "INT" else ""
        linhas.append(
            f'<div class="linha-tabela{destaque}">'
            f'<span class="pos">{int(time.posicao)}</span>'
            f'<span class="nome">{time.nome}</span>'
            f'<span class="pts">{int(time.pontos)}</span>'
            "</div>"
        )
    st.markdown(
        f'<div class="card" style="padding:.7rem">{"".join(linhas)}</div>',
        unsafe_allow_html=True,
    )

    inter = dados.classificacao().query("sigla == 'INT'").iloc[0]
    corte = dados.classificacao().query("posicao == 17").iloc[0]
    st.markdown(
        f'<div class="nota">Margem para o Z4: '
        f'<span style="color:{tema.SERIE_1}">'
        f'{int(inter.pontos) - int(corte.pontos)} ponto</span></div>',
        unsafe_allow_html=True,
    )


def _ultimos_jogos() -> None:
    estilo.rotulo_secao(f"Últimos {ULTIMOS} jogos")
    jogos = dados.jogos_do_inter().tail(ULTIMOS)

    linhas = []
    for _, jogo in jogos.iterrows():
        cor = {"V": tema.SERIE_1, "E": tema.MUDO, "D": tema.SERIE_2}[jogo.resultado]
        linhas.append(
            '<div class="linha-tabela">'
            f'<span class="pos">{int(jogo.rodada)}</span>'
            f'<span class="nome">{jogo.adversario} '
            f'<span style="color:{tema.MUDO};font-size:.72rem">'
            f'({jogo.mando})</span></span>'
            f'<span class="pts" style="color:{cor}">'
            f'{int(jogo.gols_pro)}–{int(jogo.gols_contra)}</span>'
            "</div>"
        )
    st.markdown(
        f'<div class="card" style="padding:.7rem">{"".join(linhas)}</div>',
        unsafe_allow_html=True,
    )


def _periodos_dos_tecnicos() -> None:
    estilo.rotulo_secao("Desempenho por período de comando")
    tecnicos = dados.desempenho_tecnicos()

    for coluna, (_, tecnico) in zip(st.columns(len(tecnicos)), tecnicos.iterrows()):
        with coluna:
            st.markdown(
                estilo.card(
                    tecnico.tecnico,
                    f"{tecnico.aproveitamento:.1f}%",
                    f"rodadas {int(tecnico.rodada_inicio)}–{int(tecnico.rodada_fim)} · "
                    f"{int(tecnico.jogos)} jogos · {int(tecnico.gols_pro)}:"
                    f"{int(tecnico.gols_contra)}",
                    proporcao=tecnico.aproveitamento / 100,
                    vermelho=True,
                ),
                unsafe_allow_html=True,
            )


def _evolucao() -> go.Figure:
    """Posição na tabela ao longo das rodadas, só o Inter."""
    inter = (
        dados.posicoes_por_rodada().query("sigla == 'INT'").sort_values("rodada")
    )

    figura = go.Figure(
        go.Scatter(
            x=inter.rodada, y=inter.posicao, mode="lines",
            line={"color": tema.SERIE_1, "width": 2},
            fill="tozeroy", fillcolor="rgba(229, 72, 77, 0.10)",
            hovertemplate="rodada %{x}: %{y}º<extra></extra>",
            showlegend=False,
        )
    )
    figura.add_hline(y=Z4_INICIO - 0.5, line={"color": tema.EIXO, "width": 1})
    figura.add_annotation(
        x=38, y=Z4_INICIO - 0.5, text="corte do Z4  ", showarrow=False,
        xanchor="right", yanchor="bottom", font={"color": tema.MUDO, "size": 11},
    )

    return tema.aplicar(
        figura,
        legenda=False,
        altura=300,
        title={"text": "Posição na tabela"},
        xaxis={"title": {"text": ""}, "dtick": 6},
        yaxis={"title": {"text": ""}, "autorange": "reversed",
               "range": [20.5, 0.5], "tickvals": [1, 5, 10, 15, 20]},
    )


def _eficiencia() -> go.Figure:
    """Real contra esperado, nas duas pontas."""
    inter = dados.xg_dos_times().query("sigla == 'INT'").iloc[0]

    categorias = ["Gols<br>marcados", "Gols<br>sofridos", "Pontos"]
    reais = [inter.gols_pro, inter.gols_contra, inter.pontos]
    esperados = [inter.xg, inter.xg_contra, inter.pontos_esperados]

    figura = go.Figure()
    figura.add_trace(
        go.Bar(
            x=categorias, y=esperados, name="Esperado",
            marker={"color": tema.NEUTRO, "line": {"width": 2, "color": tema.SUPERFICIE}},
            hovertemplate="esperado: %{y:.1f}<extra></extra>",
        )
    )
    figura.add_trace(
        go.Bar(
            x=categorias, y=reais, name="Real",
            marker={"color": tema.SERIE_1, "line": {"width": 2, "color": tema.SUPERFICIE}},
            text=[f"{v:.0f}" for v in reais], textposition="outside",
            textfont={"color": tema.TINTA_2},
            hovertemplate="real: %{y:.0f}<extra></extra>",
        )
    )

    return tema.aplicar(
        figura,
        altura=300,
        title={"text": "Real × esperado (xG)"},
        xaxis={"title": {"text": ""}},
        yaxis={"title": {"text": ""}, "rangemode": "tozero",
               "range": [0, max(max(reais), max(esperados)) * 1.2]},
        barmode="group",
        bargap=0.42,
        bargroupgap=0.06,
    )

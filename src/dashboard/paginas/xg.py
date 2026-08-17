"""xG contra gols reais — a eficiência que decidiu a temporada."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from src.dashboard import dados, estilo, tema


def secao(numero: int) -> None:
    por_rodada = dados.xg_por_rodada().sort_values("rodada").copy()
    times = dados.xg_dos_times()
    inter = times.query("sigla == 'INT'").iloc[0]

    posicao_ataque = int(times.eficiencia_ataque.rank()[inter.name])
    posicao_defesa = int(times.eficiencia_defesa.rank(ascending=False)[inter.name])
    desperdicio = abs(inter.eficiencia_ataque) + abs(inter.eficiencia_defesa)

    estilo.secao(
        numero,
        "Foi ineficiência nas duas pontas ao mesmo tempo.",
        f"Marcou {int(inter.gols_pro)} gols com {inter.xg:.1f} de xG e sofreu "
        f"{int(inter.gols_contra)} com {inter.xg_contra:.1f} — o "
        f"<strong>{posicao_ataque}º pior finalizador</strong> e a "
        f"<strong>{posicao_defesa}ª pior defesa em relação ao esperado</strong> entre os 20 "
        f"times. Somadas, as duas pontas custaram cerca de <strong>{desperdicio:.0f} gols</strong>. "
        "No gráfico da esquerda, o vermelho sólido corre abaixo do tracejado e o azul sólido "
        "corre acima: os dois buracos da temporada.",
    )

    st.plotly_chart(_acumulado(por_rodada), use_container_width=True)
    st.plotly_chart(_por_rodada(por_rodada), use_container_width=True)

    with st.expander("Ver dados"):
        st.dataframe(
            por_rodada[["rodada", "mando", "adversario", "gols_pro", "xg_pro",
                        "gols_contra", "xg_contra"]]
            .rename(columns={
                "rodada": "Rodada", "mando": "Mando", "adversario": "Adversário",
                "gols_pro": "Gols", "xg_pro": "xG",
                "gols_contra": "Sofridos", "xg_contra": "xG contra",
            }),
            hide_index=True, use_container_width=True,
        )


def _acumulado(por_rodada) -> go.Figure:
    """Uma escala só: gols e xG têm a mesma unidade, então dividem o eixo."""
    dados_ = por_rodada.assign(
        gols_acum=por_rodada.gols_pro.cumsum(),
        xg_acum=por_rodada.xg_pro.cumsum(),
        sofridos_acum=por_rodada.gols_contra.cumsum(),
        xgc_acum=por_rodada.xg_contra.cumsum(),
    )

    figura = go.Figure()
    series = [
        ("xg_acum", tema.SERIE_1, "xG a favor", "dot"),
        ("gols_acum", tema.SERIE_1, "Gols marcados", "solid"),
        ("xgc_acum", tema.SERIE_2, "xG contra", "dot"),
        ("sofridos_acum", tema.SERIE_2, "Gols sofridos", "solid"),
    ]
    for coluna, cor, rotulo, traco in series:
        figura.add_trace(
            go.Scatter(
                x=dados_.rodada, y=dados_[coluna], mode="lines", name=rotulo,
                line={"color": cor, "width": 2, "dash": traco},
                hovertemplate=f"{rotulo}: %{{y:.1f}}<extra></extra>",
            )
        )

    for coluna, cor in (("gols_acum", tema.SERIE_1), ("sofridos_acum", tema.SERIE_2)):
        figura.add_annotation(
            x=dados_.rodada.iloc[-1], y=dados_[coluna].iloc[-1],
            text=f"  {dados_[coluna].iloc[-1]:.0f}", showarrow=False, xanchor="left",
            font={"color": cor, "size": 12},
        )

    return tema.aplicar(
        figura,
        altura=440,
        title={"text": "Acumulado na temporada — tracejado é o esperado, sólido é o real"},
        xaxis={"title": {"text": "Rodada"}, "dtick": 4, "range": [0, 41]},
        yaxis={"title": {"text": "Gols acumulados"}, "rangemode": "tozero"},
        hovermode="x unified",
        margin={"r": 60},
    )


def _por_rodada(por_rodada) -> go.Figure:
    """Diferença entre gols e xG a cada rodada, divergente em torno de zero."""
    diferenca = por_rodada.gols_pro - por_rodada.xg_pro
    cores = [tema.SERIE_1 if valor >= 0 else tema.SERIE_2 for valor in diferenca]

    figura = go.Figure(
        go.Bar(
            x=por_rodada.rodada, y=diferenca, marker={"color": cores},
            customdata=por_rodada[["adversario", "gols_pro", "xg_pro"]],
            hovertemplate=("rodada %{x} vs %{customdata[0]}<br>"
                           "%{customdata[1]} gols · %{customdata[2]:.2f} xG<extra></extra>"),
            showlegend=False,
        )
    )
    figura.add_hline(y=0, line={"color": tema.EIXO, "width": 1})

    return tema.aplicar(
        figura,
        legenda=False,
        altura=300,
        title={"text": "Gols menos xG por rodada — abaixo de zero é chance desperdiçada"},
        xaxis={"title": {"text": "Rodada"}, "dtick": 4},
        yaxis={"title": {"text": "Gols − xG"}},
        bargap=0.35,
    )

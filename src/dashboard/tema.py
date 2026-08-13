"""Paleta e chrome dos gráficos — tema escuro com o vermelho do Internacional.

O vermelho do clube é o acento da interface e a cor da série principal. O
segundo slot é um azul profundo, usado para o que o adversário fez (gols
sofridos, xG contra) e como polo oposto nas barras divergentes.

A paleta foi validada contra a superfície escura dos cards (`#141416`) no modo
`--pairs all`, que é a exigência das formas de dispersão: banda de luminosidade,
piso de croma, separação para daltonismo e contraste, todos passando. Vale
registrar o que **não** entrou: vermelho + verde mede ΔE 1,8 em deuteranopia —
seriam indistinguíveis para boa parte dos leitores.

Regras que os gráficos seguem:

* uma escala por eixo — nunca dois eixos y no mesmo gráfico;
* a cor acompanha a entidade, não a posição no ranking;
* categorias nominais (técnicos, jogadores) recebem uma cor só, nunca um
  gradiente por valor;
* séries além de duas viram ênfase (uma em cor, o resto recuado) ou tabela.
"""

from __future__ import annotations

# --- categóricas (validadas em all-pairs contra #141416) ---------------------
SERIE_1 = "#e5484d"   # vermelho do clube — o Inter, o que foi feito
SERIE_2 = "#0284c7"   # azul profundo — o adversário, o que foi sofrido

# --- superfícies e tinta -----------------------------------------------------
PAGINA = "#0a0a0b"
SUPERFICIE = "#141416"
BORDA = "rgba(255, 255, 255, 0.07)"

TINTA = "#f5f5f4"
TINTA_2 = "#a1a1a6"
MUDO = "#6b6b70"
GRADE = "#232326"
EIXO = "#2e2e33"

# Cinza de deênfase para a forma "ênfase": o contexto recua, o assunto fica.
NEUTRO = "#3f3f45"

FONTE = 'system-ui, -apple-system, "Segoe UI", sans-serif'


def layout_base(altura: int = 380, legenda: bool = True, **extra) -> dict:
    """Chrome padrão: grade fina, eixos recuados, fundo do card."""
    base = {
        "height": altura,
        "font": {"family": FONTE, "size": 13, "color": TINTA_2},
        "paper_bgcolor": SUPERFICIE,
        "plot_bgcolor": SUPERFICIE,
        # O título ocupa a faixa de cima e a legenda se acomoda abaixo dele.
        "margin": {"l": 56, "r": 24, "t": 88 if legenda else 56, "b": 48},
        "hoverlabel": {
            "font": {"family": FONTE, "size": 13, "color": TINTA},
            "bgcolor": "#1e1e22",
            "bordercolor": EIXO,
        },
        "xaxis": {
            "gridcolor": GRADE, "griddash": "solid", "zeroline": False,
            "linecolor": EIXO, "tickfont": {"color": MUDO},
            "title": {"font": {"color": MUDO, "size": 12}},
        },
        "yaxis": {
            "gridcolor": GRADE, "griddash": "solid", "zeroline": False,
            "linecolor": EIXO, "tickfont": {"color": MUDO},
            "title": {"font": {"color": MUDO, "size": 12}},
        },
        "legend": {
            "orientation": "h", "yanchor": "bottom", "y": 1.03,
            "xanchor": "left", "x": 0,
            "font": {"color": TINTA_2}, "title": {"text": ""},
        },
        "title": {
            "font": {"color": TINTA, "size": 15},
            "x": 0, "xanchor": "left", "y": 0.97, "yanchor": "top",
        },
    }
    for chave, valor in extra.items():
        if isinstance(valor, dict) and isinstance(base.get(chave), dict):
            base[chave] = {**base[chave], **valor}
        else:
            base[chave] = valor
    return base


def aplicar(figura, altura: int = 380, legenda: bool = True, **extra):
    """Aplica o chrome padrão a uma figura Plotly."""
    figura.update_layout(**layout_base(altura, legenda, **extra))
    return figura

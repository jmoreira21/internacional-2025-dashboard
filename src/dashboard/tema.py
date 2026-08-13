"""Paleta e chrome dos gráficos.

As cores vêm de uma paleta validada para daltonismo: os três primeiros slots
passam em todos os pares (necessário para dispersão e mapa de chutes) e quatro
slots passam em pares adjacentes (linhas e barras). Slots além disso não são
gerados — quando há mais séries, o gráfico vira ênfase (uma série colorida, o
resto em cinza) ou vira tabela.

Regras que os gráficos deste app seguem:

* uma escala por eixo — nunca dois eixos y no mesmo gráfico;
* a cor acompanha a entidade, não a posição no ranking;
* categorias nominais (técnicos, jogadores) recebem uma cor só, nunca um
  gradiente por valor, que duplicaria o comprimento da barra na tonalidade;
* verde/vermelho de status são reservados a estado (Z4, rebaixamento) e nunca
  usados como "série 3", e sempre acompanhados de rótulo.
"""

from __future__ import annotations

# Categóricas — ordem fixa. Os 3 primeiros validam em todos os pares.
SERIE_1 = "#2a78d6"   # azul
SERIE_2 = "#eb6834"   # laranja
SERIE_3 = "#1baf7a"   # aqua
SERIE_4 = "#eda100"   # amarelo (só formas adjacentes: linha, barra)

# Status — reservados para estado, sempre com rótulo junto.
CRITICO = "#d03b3b"
ATENCAO = "#fab219"
BOM = "#0ca30c"

# Chrome
SUPERFICIE = "#fcfcfb"
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
MUDO = "#898781"
GRADE = "#e1e0d9"
EIXO = "#c3c2b7"

# Cinza de deênfase, para a forma "ênfase": uma série em cor, o resto recuado.
NEUTRO = "#c3c2b7"

FONTE = 'system-ui, -apple-system, "Segoe UI", sans-serif'


def layout_base(altura: int = 380, **extra) -> dict:
    """Chrome padrão: grade fina, eixos recuados, sem moldura."""
    base = {
        "height": altura,
        "font": {"family": FONTE, "size": 13, "color": TINTA_2},
        "paper_bgcolor": SUPERFICIE,
        "plot_bgcolor": SUPERFICIE,
        "margin": {"l": 60, "r": 24, "t": 48, "b": 48},
        "hoverlabel": {"font": {"family": FONTE, "size": 13}, "bgcolor": SUPERFICIE},
        "xaxis": {
            "gridcolor": GRADE, "griddash": "solid", "zeroline": False,
            "linecolor": EIXO, "tickfont": {"color": MUDO},
            "title": {"font": {"color": TINTA_2}},
        },
        "yaxis": {
            "gridcolor": GRADE, "griddash": "solid", "zeroline": False,
            "linecolor": EIXO, "tickfont": {"color": MUDO},
            "title": {"font": {"color": TINTA_2}},
        },
        "legend": {
            "orientation": "h", "yanchor": "bottom", "y": 1.02,
            "xanchor": "left", "x": 0,
            "font": {"color": TINTA_2}, "title": {"text": ""},
        },
        "title": {"font": {"color": TINTA, "size": 16}, "x": 0, "xanchor": "left"},
    }
    for chave, valor in extra.items():
        if isinstance(valor, dict) and isinstance(base.get(chave), dict):
            base[chave] = {**base[chave], **valor}
        else:
            base[chave] = valor
    return base


def aplicar(figura, altura: int = 380, **extra):
    """Aplica o chrome padrão a uma figura Plotly."""
    figura.update_layout(**layout_base(altura, **extra))
    return figura

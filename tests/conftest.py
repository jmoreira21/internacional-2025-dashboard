"""Fixtures compartilhadas.

Os testes se dividem em dois grupos:

* **unitários** — usam HTML reduzido embutido no próprio teste, rodam sempre e
  cobrem as regras de parsing que já quebraram na prática;
* **reconciliação** — usam o HTML real salvo em `data/raw/`, que não é
  versionado. São pulados com mensagem explicativa quando os coletores ainda
  não rodaram.
"""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from src.scraper import transfermarkt, wikipedia

_HINT = "rode `poetry run python -m src.scraper.{}` (data/raw/ não é versionado)"


def _read_or_skip(path, module: str) -> str:
    if not path.exists():
        pytest.skip(f"{path.name} ausente — " + _HINT.format(module))
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def transfermarkt_matches():
    html = _read_or_skip(transfermarkt.HTML_CACHE, "transfermarkt")
    return transfermarkt.parse_gesamtspielplan(html)


@pytest.fixture(scope="session")
def wikipedia_soup() -> BeautifulSoup:
    html = _read_or_skip(wikipedia.HTML_CACHE, "wikipedia")
    return BeautifulSoup(html, "lxml")


@pytest.fixture(scope="session")
def classificacao(wikipedia_soup):
    return wikipedia.parse_classificacao(wikipedia_soup)

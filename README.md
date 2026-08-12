# internacional-2025-dashboard

Análise do desempenho do **Sport Club Internacional** no Campeonato Brasileiro Série A de 2025 e
das razões pelas quais o time terminou brigando contra o rebaixamento.

O Inter fechou a temporada em **16º lugar**, escapando da queda por **1 ponto**:

| | J | V | E | D | GP | GC | SG | Pts |
|---|---|---|---|---|---|---|---|---|
| **Internacional (16º)** | 38 | 11 | 11 | 16 | 44 | 57 | −13 | **44** |
| Ceará (17º, rebaixado) | 38 | 11 | 10 | 17 | 34 | 40 | −6 | 43 |

Foram três técnicos no ano: **Roger Machado** (rodadas 1–24), **Ramón Díaz** (25–36) e
**Abel Braga** (37–38).

## Stack

Python 3.11+ · Poetry · requests + BeautifulSoup · SQLite · pandas · Streamlit + Plotly

## Instalação

```bash
poetry install
```

## Coleta de dados

```bash
poetry run python -m src.scraper.transfermarkt   # jogo a jogo -> data/raw/*.csv
poetry run python -m src.scraper.wikipedia       # classificação, técnicos -> data/raw/*.csv
poetry run python -m src.scraper.fbref_parser    # xG e finalizações (exige HTML salvo)
poetry run python -m src.etl.validacao           # relatório de qualidade dos dados
poetry run pytest -v                             # testes de reconciliação
```

Ambos os coletores HTTP guardam o HTML baixado em `data/raw/` e aceitam
`--offline`, que reprocessa a cópia local sem repetir a requisição.

## Fontes de dados

| Fonte | Acesso | O que fornece |
|---|---|---|
| Transfermarkt | automático | 380 partidas: rodada, data, mando, placar, posição na tabela |
| Wikipédia (API MediaWiki) | automático | Classificação final, posição por rodada, mudanças de técnicos, artilharia |
| FBref | **manual** (ver abaixo) | xG, chutes, PSxG, distância, posse, passes |

### ⚠️ O FBref exige salvamento manual

O FBref está atrás de um **desafio JavaScript do Cloudflare**. Requisições com `requests` recebem
HTTP **403** com a página `"Just a moment..."` — inclusive em `/robots.txt` e através de proxies de
renderização. Não há como coletar o FBref programaticamente com esta stack.

Para habilitar as análises de xG e finalização, salve as páginas manualmente:

1. Abra <https://fbref.com/pt/equipes/6f7e1f03/Internacional-Estatisticas> no navegador
   (o desafio do Cloudflare passa normalmente na navegação comum).
2. Salve a página como HTML em `data/raw/fbref/`.
3. Repita para as seções *Scores & Fixtures*, *Shooting*, *Passing* e *Possession*.
4. Confira o que foi reconhecido:

   ```bash
   poetry run python -m src.scraper.fbref_parser --list
   ```

O nome dos arquivos não importa: as tabelas são identificadas pelo `id` e as colunas pelo
atributo `data-stat`, que é estável entre as versões em português e inglês da página. O parser
também lê as tabelas que o FBref esconde dentro de comentários HTML — sem isso, só a primeira
tabela de cada página seria visível.

Enquanto o diretório estiver vazio, as análises de xG ficam inativas e o dashboard exibe um
aviso — sem quebrar.

> **Nota sobre o mapa de chutes:** o FBref **não publica coordenadas x/y** de finalizações. A
> tabela de chutes traz minuto, jogador, xG, PSxG, distância, parte do corpo e desfecho. Por isso o
> "mapa de chutes" é implementado como um gráfico **distância × xG**, colorido por desfecho.

## Estrutura

```
src/
├── scraper/      # coleta (HTTP) e parsing (arquivos locais do FBref)
├── etl/          # limpeza e normalização
├── db/           # schema e carga no SQLite
└── dashboard/    # app Streamlit
data/raw/         # dados brutos (no .gitignore)
tests/            # testes de parsing e reconciliação
```

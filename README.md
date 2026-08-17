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
poetry run python -m src.scraper.fotmob          # xG e mapa de chutes -> data/raw/*.csv
poetry run python -m src.scraper.fbref_parser    # stats por jogador (exige HTML salvo)
poetry run python -m src.etl.validacao           # relatório de qualidade dos dados
poetry run python -m src.db.carga                # monta o SQLite a partir dos CSVs
poetry run pytest -v                             # testes de reconciliação
```

Ambos os coletores HTTP guardam o HTML baixado em `data/raw/` e aceitam
`--offline`, que reprocessa a cópia local sem repetir a requisição.

## Fontes de dados

| Fonte | Acesso | O que fornece |
|---|---|---|
| Transfermarkt | automático | 380 partidas: rodada, data, mando, placar, posição na tabela |
| Wikipédia (API MediaWiki) | automático | Classificação final, posição por rodada, mudanças de técnicos, artilharia |
| FotMob (API pública) | automático | xG por chute, coordenadas, xGOT, xG da temporada dos 20 times |
| FBref | **manual** (ver abaixo) | Estatísticas por jogador: gols, assistências, chutes, minutos |

### ⚠️ O FBref não publica xG do Brasileirão

Ao contrário do que se poderia esperar, **nenhuma tabela do FBref para a Série A traz xG** — nem
distância de chute, nem as tabelas de passes e posse de bola. O FBref só disponibiliza dados
avançados para competições selecionadas, e o Brasileirão não está entre elas.

Por isso o xG e o mapa de chutes vêm do **FotMob**, cuja API pública traz shotmap com coordenadas
`x`/`y`, xG e xGOT por finalização. Do FBref aproveitamos as estatísticas por jogador.

### O FBref exige salvamento manual

O FBref está atrás de um **desafio JavaScript do Cloudflare**. Requisições com `requests` recebem
HTTP **403** com a página `"Just a moment..."` — inclusive em `/robots.txt` e através de proxies de
renderização. Não há como coletar o FBref programaticamente com esta stack.

Para habilitar as análises de xG e finalização, salve as páginas manualmente:

1. Abra <https://fbref.com/pt/equipes/6f7e1f03/Internacional-Estatisticas> no navegador
   (o desafio do Cloudflare passa normalmente na navegação comum).
2. Salve a página como HTML em `data/raw/fbref/`.
3. Confira o que foi reconhecido:

   ```bash
   poetry run python -m src.scraper.fbref_parser --list
   ```

O nome dos arquivos não importa: as tabelas são identificadas pelo `id` e as colunas pelo
atributo `data-stat`, que é estável entre as versões em português e inglês da página. O parser
também lê as tabelas que o FBref esconde dentro de comentários HTML — sem isso, só a primeira
tabela de cada página seria visível.

Enquanto o diretório estiver vazio, as análises por jogador ficam inativas e o dashboard exibe um
aviso — sem quebrar. O xG não depende disso: vem do FotMob.

### Qual xG usar

As duas agregações do próprio FotMob não batem exatamente. Somando os chutes do Inter chega-se a
**55,2 xG** a favor e **46,7** contra, enquanto a tabela da temporada traz **54,63** e **43,74** —
~1% de diferença no ataque e ~7% na defesa, que não se explica por pênaltis, chutes bloqueados nem
gols contra.

Como os dados de chute são auditáveis e reconciliam com o placar (44:57), use a **soma do shotmap**
para análise por partida, e a **tabela da temporada** apenas para comparar com os outros times.

> **Gols contra:** o FotMob os marca como `eventType='Goal'` no time de quem chutou, com
> `isOwnGoal=True` e sem xG. Sem tratar isso, o Inter apareceria com 47 gols em vez de 44.

## Dashboard

```bash
poetry run streamlit run src/dashboard/app.py
```

A tela é organizada como **um argumento**, não como um painel de monitoramento. A abertura dá o
desfecho e cada seção sustenta uma afirmação com a evidência abaixo:

1. Não foi falta de criar chances
2. Foi ineficiência nas duas pontas ao mesmo tempo
3. Todos os 44 gols saíram de dentro da área
4. Longe do Beira-Rio, o time desabava
5. Trocar de técnico não mudou o patamar
6. O ataque inteiro passava por Alan Patrick
7. A conta só fechou na última rodada

Cada seção traz um "Ver dados" com a tabela por trás do gráfico, e o rodapé lista fontes e
ressalvas.

As cores saem de uma paleta validada para daltonismo (`src/dashboard/tema.py`): os três primeiros
slots passam em todos os pares, o que é exigência das formas de dispersão, e quatro passam em pares
adjacentes. Categorias nominais — técnicos, jogadores, situações de jogo — recebem **uma cor só**,
nunca um gradiente por valor, que duplicaria o comprimento da barra na tonalidade. Nenhum gráfico
usa dois eixos y.

O tema é claro e fixo (`.streamlit/config.toml`), porque as cores foram validadas contra essa
superfície.

## Banco de dados

`data/internacional_2025.db` — SQLite, sem servidor nem credenciais. **Não é versionado**: é
reconstruído inteiro a partir de `data/raw/` com `python -m src.db.carga`, e rodar a carga duas
vezes produz exatamente o mesmo conteúdo.

| Tabela | Linhas | Conteúdo |
|---|---|---|
| `times` | 20 | dimensão com os ids de cada fonte |
| `partidas` | 380 | campeonato inteiro |
| `classificacao` | 20 | tabela final |
| `posicoes_rodada` | 760 | posição de cada time em cada rodada |
| `tecnicos` | 3 | períodos de comando no Inter |
| `xg_times` | 20 | xG e pontos esperados da temporada |
| `chutes` | 987 | finalizações com coordenadas e xG |
| `jogadores` | 47 | estatísticas individuais do FBref |

Views prontas: `vw_jogos_inter`, `vw_xg_por_rodada`, `vw_desempenho_tecnico`.

Cada fonte escreve o nome do clube de um jeito — "Atlético-MG", "Atlético Mineiro", "Atletico MG" —
e apenas **2 dos 20** têm grafia idêntica nas três. O cruzamento usa uma chave normalizada (sem
acentos nem sufixos de estado ou patrocínio) e falha explicitamente se algum clube não casar. O
mapeamento foi verificado comparando gols marcados e sofridos time a time nas três fontes: os 20
batem.

As chaves estrangeiras são declaradas **e ativadas** via `PRAGMA foreign_keys`, que no SQLite vale
por conexão — sem ele seriam apenas documentação.

## Estrutura

```
src/
├── scraper/      # transfermarkt, wikipedia, fotmob (HTTP) e fbref_parser (local)
├── etl/          # times (dimensão cruzada), validacao (relatório de qualidade)
├── db/           # schema (DDL + views) e carga
└── dashboard/    # app Streamlit
data/raw/         # dados brutos (no .gitignore)
tests/            # testes de parsing, reconciliação e schema
```

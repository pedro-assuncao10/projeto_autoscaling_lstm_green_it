# Wikipédia em inglês (2015–2026)

> Base **reservada para o futuro**: horizontes de horas, meses e anos. Não serve para
> prever 10 minutos, porque a menor granularidade disponível é **1 hora**.

## Origem

| Item | Valor |
|---|---|
| O que é | Total de páginas vistas por hora na Wikipédia em inglês |
| Fonte | API oficial da Wikimedia (Pageviews), endpoint agregado |
| Endereço | `https://wikimedia.org/api/rest_v1/metrics/pageviews/aggregate/en.wikipedia/all-access/all-agents/hourly/<início>/<fim>` |
| Filtros | `all-access` (computador + celular + app) · `all-agents` (humanos **e** robôs) |
| Formato original | JSON, um item por hora |
| Fuso | UTC |
| Baixado em | 08/10/2026, com `python src/baixar_wikipedia.py` |
| Guardado em | `reproducao/dados/wikipedia_en.wikipedia_all-agents_1h.csv` (fora do git) |

**Por que `all-agents`:** o autoscaler precisa atender **toda** a carga que chega ao
servidor, inclusive a de robôs. Para estudar só o comportamento humano, existe a opção
`user`: `python src/baixar_wikipedia.py en.wikipedia user`.

## Passos

| # | Passo | Detalhe |
|---|---|---|
| 1 | Baixar ano a ano | a API não aceita o período inteiro de uma vez; pausa de 5 s entre os pedidos |
| 2 | Converter de JSON para CSV | **nenhum valor é alterado** — a contagem por hora já vem pronta da Wikimedia |
| 3 | Calcular req/s | acessos por hora ÷ 3600 |

A API às vezes recusa pedidos por excesso (erro HTTP 429). O script espera e tenta de
novo, com espera crescente (15 s, 30 s, 60 s…).

## Resultado

| Medida | Valor |
|---|---|
| Período (UTC) | 01/07/2015 00:00 a 08/10/2026 00:00 |
| Horas | 98.800 (11,3 anos) |
| Requisições por segundo | mínimo 301 · média 3.695 · máximo 41.059 |

Horas por ano, como vieram da API:

| Ano | Horas | Observação |
|---|---|---|
| 2015 | 4.416 | começa em 01/07 |
| 2016 | 8.784 | ano bissexto, completo |
| 2017–2019 | 8.760 | completos |
| 2020 | 8.784 | ano bissexto, completo |
| 2021 | 8.760 | completo |
| 2022 | 8.759 | **falta 1 hora** |
| 2023 | 8.752 | **faltam 8 horas** |
| 2024 | 8.784 | ano bissexto, completo |
| 2025 | 8.760 | completo |
| 2026 | 6.721 | até 08/10 |

## Pontos a verificar antes de usar

- **Horas que faltam (2022 e 2023):** localizar e decidir se viram `valido = 0`
- **Pico de 41.059 req/s:** cerca de 11 vezes a média. Provável ação de robôs ou evento
  pontual. Decidir se fica, sai ou se usamos a série `user`
- **Mudanças de definição da Wikimedia** ao longo dos anos (ex.: classificação de robôs)
  podem criar degraus na série que não são mudança real de demanda

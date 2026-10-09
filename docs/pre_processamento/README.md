# Pré-processamento dos dados

Registro de **tudo o que foi feito com cada base de dados**, desde o download até o
arquivo usado no treino da LSTM. Escrito no momento em que o passo é feito, para não
precisar reconstruir depois.

**Regra:** os arquivos originais (`reproducao/dados/brutos/`) **nunca são alterados**.
Cada passo lê o original e grava um arquivo **novo**. Qualquer resultado pode ser
regenerado rodando os scripts listados aqui.

## Bases

| # | Base | Granularidade | Período | Uso | Documento |
|---|---|---|---|---|---|
| 1 | NASA-HTTP (1995) | 1 minuto | 62 dias | previsão de 10 min (como nos artigos) | [01_nasa.md](01_nasa.md) |
| 2 | Copa do Mundo FIFA (1998) | 1 minuto | 87 dias | previsão de 10 min (como nos artigos) | [02_copa_1998.md](02_copa_1998.md) |
| 3 | Wikipédia (inglês) | 1 hora | 11,3 anos | **futuro**: padrões de horas, meses e anos | [03_wikipedia.md](03_wikipedia.md) |

Outras bases públicas pesquisadas (com CPU, instâncias etc.) estão no
[catálogo de bases](../bases_de_dados/README.md).

## Etapas comuns a todas as bases

| Etapa | Feita em | Situação |
|---|---|---|
| 1. Download dos arquivos originais | `src/baixar_tracos.py`, `src/baixar_wikipedia.py` | ✅ |
| 2. Agregação em requisições por intervalo (minuto ou hora) | `src/preparar_traco.py` | ✅ NASA · ✅ Copa |
| 3. Marcação de períodos sem medição (`valido = 0`) | `src/preparar_traco.py` | ✅ NASA |
| 4. Divisão treino/teste: **70/30 na ordem do tempo** | `src/dados.py`, na hora do treino | definido |
| 5. Normalização min-max (0 a 1), **calculada só no treino** | `src/dados.py`, na hora do treino | definido |
| 6. Tratamento de valores extremos | — | **a decidir** |

Etapas 4 e 5 não geram arquivo: acontecem dentro do treino, a cada execução.

## Formato dos arquivos gerados

CSV UTF-8, separador vírgula, decimal com ponto, **horário sempre em UTC**.

| Coluna | Significado |
|---|---|
| `timestamp` | início do intervalo, ISO 8601 UTC |
| `requests_per_minute` (ou `_per_hour`) | quantas requisições caíram no intervalo |
| `requests_per_second` | o mesmo valor ÷ 60 (ou ÷ 3600) |
| `valido` | 1 = medido; 0 = **sem medição** (servidor fora do ar). Só em NASA e Copa |

> **Por que a coluna `valido`:** zero requisições pode significar "ninguém acessou" ou
> "o servidor estava desligado". Para a rede são coisas muito diferentes: se tratarmos
> a queda do servidor como tráfego zero, ela aprende uma queda de demanda que nunca existiu.

## Por que agregar por minuto

É o procedimento da literatura que estamos reproduzindo:

- **Dang-Quang & Yoo (2021)** — NASA e FIFA agregados por minuto, LSTM/Bi-LSTM
- **Guruge & Priyadarshana (2025)** — NASA e FIFA agregados por minuto, 70/30 temporal

A variável que a rede aprende a prever é **a taxa de requisições**, não o uso de CPU.

## Histórico de alterações

| Data | O que mudou | Por quê |
|---|---|---|
| 08/10/2026 | Download da NASA, Copa e Wikipédia | início do pré-processamento |
| 08/10/2026 | **Correção:** intervalo do furacão Erin na NASA estava 4 h adiantado | o horário oficial está no fuso local (−0400) e era lido como UTC. Ver [01_nasa.md](01_nasa.md) |
| 09/10/2026 | Copa agregada por minuto: 1.352.804.107 requisições, igual ao publicado | 3 arquivos precisaram ser baixados de novo (tempo esgotado). Ver [02_copa_1998.md](02_copa_1998.md) |

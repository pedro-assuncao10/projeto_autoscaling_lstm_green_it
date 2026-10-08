# Dados

## `exemplo_entrada.csv`

**Amostra para visualizar o formato de entrada.** Não é usada no experimento —
serve para você ver exatamente o que a rede recebe.

| Coluna | Unidade | Papel |
|---|---|---|
| `timestamp` | ISO 8601 UTC | instante do registro |
| `requests_per_minute` | req/min | **a série que a rede prevê** |
| `requests_per_second` | req/s | a mesma informação, na unidade do schema do projeto |

A amostra cobre um dia útil das 07h às 18h, a cada 15 minutos, com:

- a subida da manhã (2.180 → 9.100 req/min)
- a queda do almoço, por volta das 12h
- a segunda subida da tarde
- **uma rajada às 14h15**, chegando a 21.305 req/min — é o caso difícil
- a descida do fim do expediente

> O experimento usa `trace_sintetico.csv`, gerado por `src/gerar_trace.py` com
> **resolução de 1 minuto** (igual ao pré-processamento que os artigos fazem com os
> traços NASA e FIFA) e várias semanas de duração, para a rede ver o ciclo semanal.

## Como isso vira pods

Com capacidade de 500 requisições por minuto por pod:

| Carga | Conta | Pods |
|---|---|---|
| 2.180 req/min | 2.180 ÷ 500 = 4,4 | mínimo (10) |
| 9.100 req/min | 9.100 ÷ 500 = 18,2 | **19** |
| 21.305 req/min (rajada) | 21.305 ÷ 500 = 42,6 | **43** |

O objetivo da previsão é chegar a 43 pods **antes** das 14h15, e não depois.

---

# Traços reais (Internet Traffic Archive)

São os dois traços canônicos da literatura de autoscaling. Baixados e processados
pelos scripts; **não vão para o git** (grandes e reprodutíveis).

```bash
python3 src/baixar_tracos.py nasa                 # ~37 MB
python3 src/preparar_traco.py nasa dados/nasa_1min.csv

python3 src/baixar_tracos.py fifa 73 74 75        # ~590 MB
python3 src/preparar_traco.py fifa dados/fifa_1min.csv
```

## NASA-HTTP (1995) — `dados/nasa_1min.csv`

Logs do Kennedy Space Center, julho e agosto de 1995.

| | |
|---|---|
| Requisições | **3.461.612** — confere com o número publicado no artigo |
| Período | 01/07/1995 04:00 a 01/09/1995 03:59 UTC (62 dias) |
| Minutos | 89.280, sendo 87.016 válidos |
| Carga | mediana 33 · p95 96 · p99 129 · **máx 405** req/min |
| Pico ÷ mediana | **12,3×** |

**Furacão Erin.** O servidor ficou fora do ar de 01/08 14:52 a 03/08 04:36 — 2.264
minutos. Esses minutos têm `valido = 0`: zero ali **não é tráfego zero, é ausência de
medição**. Tratar como zero ensinaria a rede a prever uma queda que nunca houve.
O `dados.py` descarta essa janela e usa o maior trecho contínuo.

> O artigo original menciona o furacão, mas não diz como tratou a lacuna.

## FIFA World Cup (1998) — `dados/fifa_1min.csv`

Formato binário: 20 bytes por requisição, *big endian* — timestamp, cliente,
objeto, tamanho, método, status, tipo e servidor. Só o timestamp é usado.

Os dias 73 a 75 cobrem as **semifinais** (Brasil × Holanda e França × Croácia).

| | |
|---|---|
| Requisições | **96.364.239** (subconjunto; o traço completo tem 1,35 bilhão) |
| Período | 06/07/1998 22:00 a 09/07/1998 22:00 UTC (3 dias) |
| Minutos | 4.321, todos válidos |
| Carga | mediana 11.954 · p95 114.415 · **máx 229.426** req/min |
| Pico ÷ mediana | **19,2×** |

Para mais dias: `python3 src/baixar_tracos.py fifa 76 77 78` (a final foi em 12/07).

## Qual usar para quê

| Traço | Serve para |
|---|---|
| **NASA** | Treino e teste principais: 62 dias dão ciclo diário **e semanal** |
| **FIFA** | Caso difícil: só 3 dias, mas com picos de 19× — testa a reação a rajada |
| **Sintético** | Controle: perfil conhecido, útil para depurar o código |

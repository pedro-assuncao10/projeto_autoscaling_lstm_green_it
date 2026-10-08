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

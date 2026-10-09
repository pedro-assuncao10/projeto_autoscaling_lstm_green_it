# Algoritmo proposto — versão 0.1

**Data:** 09/10/2026
**Status:** ⏳ aguardando validação do dono do projeto. Nenhum código escrito ainda.

**Ideia:** o melhor dos dois mundos.

- **Gandhi et al. (2011)** planeja **o dia todo** (a carga de base)
- **Dang-Quang & Yoo (2021)** prevê **os próximos minutos** com Bi-LSTM e decide os pods
  com o Algoritmo 1

Gandhi usa um reativo ingênuo para o que foge do padrão; **aqui esse papel passa para a
Bi-LSTM de Dang-Quang**. Os problemas conhecidos (ver Decisão 003) ficam de lado nesta
primeira versão: o objetivo é colocar para testar.

---

## Visão geral

```
              ┌──────────────────────────────────────────────┐
1x por dia    │ NÍVEL 1 — PLANO DO DIA          (Gandhi 2011) │
(00:00)       │ últimos 7 dias → base de cada hora → escada  │
              │ com poucos degraus → pods_base(t)            │
              └───────────────────────┬──────────────────────┘
                                      │ piso
              ┌───────────────────────▼──────────────────────┐
a cada        │ NÍVEL 2 — CORREÇÃO DO MINUTO (Dang-Quang 2021)│
minuto        │ últimos 10 min → Bi-LSTM → carga prevista    │
              │ → pods_lstm → Algoritmo 1 (CDT, RRS)         │
              └───────────────────────┬──────────────────────┘
                                      │
                       pods(t) = max(pods_base, pods_lstm),
                       sem nunca descer abaixo de pods_base
```

---

## Parâmetros

| Símbolo | Significado | Valor inicial | Origem |
|---|---|---|---|
| `C` | requisições por minuto que **um pod** atende | 500 req/min | Dang-Quang & Yoo (2021), Copa |
| `D` | dias de histórico para o plano | 7 | Gandhi et al. (2011) |
| `p` | percentil usado na base | 90 | Gandhi et al. (2011) |
| `c` | custo de cada degrau na escada | `Var/4` | Gandhi et al. (2011) |
| `J` | minutos de histórico da Bi-LSTM | 10 | Dang-Quang & Yoo (2021) |
| `H` | minutos à frente previstos pela Bi-LSTM | 10 | decisão do projeto (artigo: 1 e 5) |
| `CDT` | espera mínima entre decisões | 1 min | Dang-Quang & Yoo (2021) |
| `RRS` | fração do excesso removida ao descer | 0,60 | Dang-Quang & Yoo (2021) |
| `pods_min` | mínimo absoluto de pods | 10 | Dang-Quang & Yoo (2021) |
| `pods_max` | máximo de pods | definir pelo pico da Copa / `C` | — |

---

## Nível 1 — Plano do dia (Gandhi et al., 2011)

Roda **uma vez por dia, à 00:00**, antes do dia começar.

```
ENTRADA: carga por minuto dos últimos D = 7 dias

1. PADRÃO POR HORA
   para cada hora h = 0..23:
       base_hora[h] = percentil p=90 da carga na hora h, nos últimos 7 dias
       (mesmo critério de Gandhi: "Predictive/1hr")

2. ESCADA COM POUCOS DEGRAUS  (discretização por programação dinâmica)
   dividir as 24 horas em n intervalos [t0,t1], [t1,t2], ..., [tn-1, 24h]
   em cada intervalo, valor do degrau = média de base_hora no intervalo
   escolher os intervalos que minimizam:
         Σ (base_hora − degrau)²   +   c · n          com c = Var(base_hora) / 4
   → poucos degraus = poucas mudanças de capacidade no dia
     (Gandhi: aceitável ~1 mudança a cada 4–6 h)

3. PODS DA BASE
   para cada minuto t do dia:
       pods_base(t) = max(pods_min, ⌈ degrau(t) / C ⌉)

SAÍDA: pods_base(t) para as 24 horas — fixo até a próxima meia-noite
```

**Diferença em relação a Gandhi:** ele converte a carga em servidores com um modelo de
fila (M/G/1/PS). Aqui usamos a fórmula de Dang-Quang (`carga ÷ C`), para os dois níveis
usarem a mesma régua.

---

## Nível 2 — Correção do minuto (Dang-Quang & Yoo, 2021)

Roda **a cada minuto**.

```
ENTRADA: carga real dos últimos J = 10 minutos; pods atuais; pods_base(t)

1. PREVISÃO
   Bi-LSTM recebe os 10 últimos minutos
   → devolve a carga prevista para t+1, t+2, ..., t+H   (H = 10)

2. PODS PELA PREVISÃO
   carga_alvo = prevista(t+1)                       ← como no Algoritmo 1 do artigo
   pods_lstm  = ⌈ carga_alvo / C ⌉

3. JUNTAR COM O PLANO DO DIA  (regra do máximo, igual ao HPA com dois gatilhos)
   pods_desejado = max(pods_base(t), pods_lstm)

4. ALGORITMO 1 (Dang-Quang), com o plano do dia como piso
   se passou menos de CDT = 1 min desde a última mudança:
       não faz nada
   senão, se pods_desejado > pods_atual:
       sobe direto para pods_desejado                    (subida imediata)
   senão, se pods_desejado < pods_atual:
       excesso   = pods_atual − pods_desejado
       remove    = ⌊ excesso × RRS ⌋                     (só 60% do excesso)
       pods_novo = max(pods_base(t), pods_atual − remove)  ← nunca abaixo do plano
   senão:
       mantém

SAÍDA: pods(t+1)
```

### O que vem de cada artigo

| Passo | Origem |
|---|---|
| Plano do dia, percentil 90 de 7 dias, escada por programação dinâmica | Gandhi et al. (2011) |
| Bi-LSTM com 10 minutos de entrada | Dang-Quang & Yoo (2021) |
| `pods = carga ÷ C`, CDT, RRS, `pods_min` | Dang-Quang & Yoo (2021) |
| Reativo cobrindo só o que passa da base | Gandhi et al. (2011), com a Bi-LSTM no lugar do reativo ingênuo |
| `max(base, lstm)` | regra do HPA com vários gatilhos (`docs/algoritmos.md`, seção 1.4) |
| Previsão de 10 minutos (não só 1 e 5) | decisão do projeto |

---

## Como vai ser testado (offline, na base da Copa)

### Divisão dos dados

| Parte | Uso |
|---|---|
| Primeiros 70% do tempo | treinar a Bi-LSTM (como Dang-Quang) |
| Últimos 30% (~26 dias) | **teste**. Cada dia de teste é planejado com os 7 dias anteriores (como Gandhi, mas em ~26 dias em vez de 1) |

### Concorrentes

| # | Estratégia | O que é |
|---|---|---|
| 1 | Fixo | pods fixos no máximo (sem autoscaler) — referência de desperdício |
| 2 | Reativo | decide pela carga atual, desce só após 5 min (imitação do HPA) |
| 3 | Gandhi — só plano | Predictive/var: só o nível 1 |
| 4 | Gandhi — híbrido | Hybrid/var: nível 1 + reativo ingênuo de 10 min |
| 5 | Dang-Quang | Bi-LSTM + Algoritmo 1, sem plano do dia |
| 6 | **Proposta** | nível 1 + nível 2 |
| 7 | Oráculo | conhece a carga futura real — teto do ganho possível |

### Métricas (as dos dois artigos)

| Métrica | De onde | O que mostra |
|---|---|---|
| θU, TU | Dang-Quang (SPEC) | quanto e por quanto tempo **faltou** pod |
| θO, TO | Dang-Quang (SPEC) | quanto e por quanto tempo **sobrou** pod |
| εn | Dang-Quang (SPEC) | ganho sobre não ter autoscaler |
| % de intervalos com SLA violado | Gandhi | carga maior que a capacidade |
| número de mudanças de escala | Gandhi | estabilidade |
| pods-minuto | — | estimativa do custo e, depois, da energia |

---

## Pontos para o dono do projeto validar

1. **Peça do dia:** Gandhi (2011, percentil 90 de 7 dias + escada) ou Guruge (2025, Prophet)?
2. **Qual previsão decide os pods:** `t+1` (como o artigo) ou o **maior valor dos próximos 10 minutos** (mais seguro, gasta mais)?
3. **Capacidade do pod:** 500 req/min (o valor do artigo para a Copa)?
4. **Plano do dia como piso:** o nível 2 nunca desce abaixo do plano. Concorda?

## Referências

- DANG-QUANG, N.-M.; YOO, M. *Deep Learning-Based Autoscaling Using Bidirectional LSTM
  for Kubernetes.* Applied Sciences, v. 11, n. 9, 3835, 2021. Algoritmo 1.
- GANDHI, A. et al. *Minimizing Data Center SLA Violations and Power Consumption via
  Hybrid Resource Provisioning.* IGCC 2011. Resumo:
  `revisao_bibliografica/resumos/05_gandhi_2011_hybrid_provisioning.md`
- Decisão 003: `docs/decisoes/003_horizonte_curto_e_plano_do_dia.md`

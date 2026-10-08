# CarbonScaler (Hanafy et al., 2023)

**Referência:** HANAFY, W. A.; LIANG, Q.; BASHIR, N.; IRWIN, D.; SHENOY, P. *CarbonScaler: Leveraging Cloud Workload Elasticity for Optimizing Carbon-Efficiency.* Proc. ACM Meas. Anal. Comput. Syst., v. 7, n. 3, art. 57, dez. 2023. DOI: 10.1145/3626788. arXiv: 2302.08681.

**Instituição:** University of Massachusetts Amherst
**Tipo:** pesquisa primária (propõe algoritmo, implementa e mede)
**Veículo:** SIGMETRICS / POMACS — revisado por pares, veículo forte
**Código:** https://github.com/umassos/CarbonScaler

---

## Ideia central

Em vez de **pausar** um job quando a energia da rede está suja e retomá-lo quando
está limpa (*suspend-resume*), **variar o número de servidores**: escalar para cima
quando o carbono está baixo e para baixo quando está alto. Chamam isso de
*carbon scaling*.

## Problema atacado

O *suspend-resume* (ex.: *Let's Wait Awhile*) economiza carbono, mas atrasa muito o
término dos jobs — de 7 a 10 vezes em alguns casos, porque a intensidade de carbono
muda devagar e o job pode ficar horas parado.

## Como fizeram

**Formulação.** Um job chega com mínimo de servidores *m*, máximo *M*, duração
estimada *l* e prazo *T*. O tempo é dividido em fatias (15 min ou 1 h), cada uma
com uma previsão de intensidade de carbono *cᵢ*.

**Curva de capacidade marginal.** Quanto de vazão cada servidor *a mais* acrescenta.
Na prática há retorno decrescente (lei de Amdahl): o 8º servidor rende menos que o 2º.

**Algoritmo guloso.** Para cada par (fatia, servidor) calcula `MCⱼ / cᵢ` (trabalho
marginal por unidade de carbono), ordena e aloca do maior para o menor até completar
o trabalho. Com capacidade marginal decrescente, provam que a solução é **ótima**
(Federgruen & Groenevelt, 1986). Complexidade O(nM log nM).

**Robustez.** Ao fim de cada fatia compara progresso real com o planejado e
recalcula o cronograma se desviar além de um limiar.

**Componentes** (Go, ~2.500 linhas):

| Componente | Função |
|---|---|
| Carbon Profiler | Roda o job 1 min em cada quantidade de servidores para levantar a curva marginal |
| Carbon AutoScaler | Controlador Kubernetes sobre o Kubeflow; altera o número de réplicas |
| Carbon Advisor | Simulador; erro médio < 5% contra os experimentos reais |

## Montagem experimental

| Item | Detalhe |
|---|---|
| Hardware CPU | Cluster **físico**: 8 servidores Xeon E5-2620, 16 núcleos, rede 10G |
| Hardware GPU | AWS, 8 instâncias p2.xlarge (NVIDIA K80) |
| Medição | **RAPL + PowerAPI** (CPU), DCGM (GPU), Metrics Server (uso) |
| Cargas | N-body em MPI; treino de ResNet18, EfficientNetB1, VGG16 (PyTorch) |
| Traços de carbono | electricityMap, horários, jan/2020–dez/2022 |
| Escolha de regiões | Média × coeficiente de variação de 37 regiões AWS → Holanda (alta) e Ontário (baixa) |
| Baselines | Carbon-agnostic, suspend-resume, escala estática, oráculo de escala estática |
| Repetições | 15 execuções reais e 100 simuladas, IC de 95% |

## Resultados

- **51%** menos carbono que execução agnóstica; **37%** menos que suspend-resume; **8%** menos que a melhor escala estática
- Sem folga de prazo: 33% contra o agnóstico
- Escala estática mal escolhida pode **aumentar** o carbono em até 20%
- Economia correlaciona **0,82** com o coeficiente de variação da rede. Índia: carbono alto mas estável → quase nenhuma economia
- Com **30% de erro** na previsão de carbono, perdem só ~4% (p95): importa acertar picos e vales, não o valor exato
- Custo extra: 5–10% em cargas escaláveis, nunca acima de 18%

## Relevância para a dissertação

**Delimita o espaço, explicitamente (seção 2.4):** cargas **interativas** são
sensíveis a latência, não admitem deslocamento temporal, e escalar só faz sentido em
resposta à demanda — por isso eles se restringem a **batch**. Uma aplicação web com
SLA está no território que declararam fora do escopo.

**Custo de troca ignorado:** assumem custo de *scaling* desprezível (nota de rodapé 5)
e reconhecem 20–40 s de overhead fora da decisão (seção 5.8). O termo de *cold start*
`K(Δn⁺)` da proposta trata exatamente isso.

**Alerta:** em aplicação interativa a demanda manda, então não dá para adiar carga.
O termo de carbono `I(t)` só muda o tamanho da folga aceitável. Como a economia depende
do coeficiente de variação, é preciso **medir cedo o do SIN** (dados horários do ONS).
Rede limpa *e* estável pode render quase nada.

> ⚠️ Atualização após ler o survey (resumo 02): aplicações interativas e cold start
> **não** são lacunas isoladas — já existem CASPER, CASA e Kreutz et al. A contribuição
> está na **combinação** dos elementos.

## O que reaproveitar

1. Critério média × coeficiente de variação, aplicado aos subsistemas do SIN
2. Baseline **oráculo** (demanda futura perfeita): mostra o teto do ganho e separa erro do controlador de erro do preditor
3. Simulador validado contra a bancada real (< 5% de erro) para extrapolar além do hardware disponível
4. Injeção de erro na previsão para medir robustez ao erro da LSTM
5. 15 repetições com IC de 95% como padrão de relato
6. Ler o código antes de escrever o controlador

## Leituras derivadas

- **The War of the Efficiencies** — Hanafy et al., HotCarbon 2023 (conflito energia × carbono)
- **Ecovisor** — Souza et al., ASPLOS 2023
- **SmartWatts** — Fieni et al., CCGrid 2020 (potência por container)
- **AutoScale** — Gandhi et al., ACM TOCS 2012 (autoscaling para aplicações interativas)

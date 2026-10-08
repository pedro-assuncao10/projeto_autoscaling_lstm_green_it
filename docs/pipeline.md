# Pipeline experimental — autoscaling sustentável

Documento de referência do projeto. **É um documento vivo**: cada fase será refinada
conforme o trabalho avança.

**Regra de ouro:** se um resultado não pode ser regenerado por um comando, ele não
existe. Nada de passo manual não registrado.

---

## Princípio: compor, não reinventar

A proposta é uma **metodologia reproduzível** que qualquer pessoa possa aplicar para
obter autoscaling sustentável em Kubernetes, **montada sobre ferramentas que já existem**.

Compor ferramentas, sozinho, é integração. A contribuição científica está em três coisas:

1. **A metodologia**: como combinar as peças, medir e avaliar de forma reproduzível
2. **As peças que faltam**: previsão de demanda com Transfer Learning e a política de decisão energética
3. **A avaliação empírica**: evidência de que a composição economiza energia sem violar o SLA,
   comparada com cada ferramenta isolada

### O que é reaproveitado e o que é próprio

| Função | Ferramenta | Origem |
|---|---|---|
| Orquestração | Kubernetes (k3s) | reaproveitado |
| Geração de carga | k6 | reaproveitado |
| Coleta de métricas | Prometheus, node-exporter, cAdvisor, kube-state-metrics | reaproveitado |
| Medição de energia | RAPL (leitura direta) + Scaphandre | reaproveitado |
| Atribuição de energia por pod | **modelo** estático/dinâmico do KubeWatt | modelo reaproveitado¹ |
| Intensidade de carbono | fator de emissão do SIN (MCTI / ONS) | dado público |
| Atuação da escala | **KEDA** (cria e gerencia o HPA) | reaproveitado |
| Escala reativa | HPA via gatilho de CPU do KEDA | reaproveitado |
| Escala por agenda (baseline) | KEDA *cron scaler* (equivalente ao *scheduled scaling* da AWS) | reaproveitado |
| Escala por carbono (baseline) | Carbon-Aware KEDA Operator | reaproveitado |
| Agrupar pods em poucos nós | kube-scheduler com `MostAllocated` + descheduler `HighNodeUtilization` | reaproveitado |
| Escala de máquinas | Cluster Autoscaler, provedor `externalgrpc` | reaproveitado |
| Desligar e ligar máquinas | suspensão (S3) + Wake-on-LAN | reaproveitado |
| **Previsão de demanda + Transfer Learning** | LSTM | **próprio** |
| **Política de decisão em dois níveis** | pods (`J(n)`) e máquinas, com energia, matriz, *cold start* e SLA | **próprio** |
| **Provedor `externalgrpc` para máquinas físicas** | liga e suspende nós do laboratório | **próprio** (pequeno) |
| **Schema e gerador do dataset** | perfis k6 + consolidação | **próprio** |
| **Protocolo de avaliação** | portões, repetições, estatística | **próprio** |

¹ A ferramenta KubeWatt exige iDRAC/Redfish, indisponível no ambiente. Aplicamos o
**modelo de alocação** dela sobre os dados do RAPL, não o código.

---

## Dois níveis de escala

Ver `docs/decisoes/002_dois_niveis_de_escala.md`.

| Nível | Decide | Ritmo | Horizonte da previsão |
|---|---|---|---|
| **Pods** | réplicas `n` | 15 s | maior que `t_boot` do pod (segundos) |
| **Máquinas** | nós ligados `m` | minutos | maior que `t_acordar` do nó (segundos a minutos) |

A mesma LSTM prevê a demanda; cada nível a consulta no seu horizonte.

---

## Visão geral

```
FASE 0  Ambiente e reprodutibilidade
   │
FASE 1  Aplicação sob teste (CRUD com carga de CPU previsível)
   │
FASE 2  Instrumentação (RAPL, Scaphandre, Prometheus, k6)
   │
FASE 3  Calibração energética  ──────────► modelo P(u), potência estática
   │                                        [PORTÃO 1 e 2]
FASE 4  Geração do dataset (schema oficial)
   │
FASE 5  Previsão de demanda (baselines → LSTM → Transfer Learning)
   │
FASE 6  Política de decisão J(n)
   │
FASE 7  Controlador (publica a decisão; o KEDA executa)
   │
FASE 8  Avaliação comparativa  ──────────► [PORTÃO 3]
   │
FASE 9  Análise, conversão para carbono e pacote de replicação
```

**Portões** são critérios de aceitação. Não avance sem passar.

---

## FASE 0 — Ambiente e reprodutibilidade

### 0.1 Arquitetura

| Papel | Máquina | O que roda |
|---|---|---|
| **SUT — plano de controle** | PC do laboratório nº 1, **sempre ligado** | servidor k3s, KEDA, Cluster Autoscaler, leitor RAPL |
| **SUT — nós de trabalho** | PCs do laboratório nº 2… (≥ 1) | agente k3s, aplicação, leitor RAPL, Scaphandre, cAdvisor |
| **Cliente** | Notebook | k6, Prometheus, Grafana, previsor e política, análise |

O Prometheus fica **fora** do SUT: ferramentas de monitoramento aumentam o consumo
entre 1,47% e 12,86% (Dinga et al., ICSOC 2023). Precedente: KubeWatt.

**No mínimo duas máquinas físicas** no SUT, para existir escala de máquinas.
Cada nó tem seu próprio leitor RAPL.

O SUT precisa ser **máquina física** (VM não expõe RAPL). Ver
`docs/decisoes/001_medicao_energetica_por_software.md`.

### 0.2 Sincronização de relógio ⚠️

As duas máquinas geram séries que serão cruzadas por timestamp. Com relógios
desalinhados, a energia de um instante é casada com a carga de outro, e o resultado
sai distorcido sem nenhum aviso.

```bash
sudo apt install -y chrony && sudo systemctl enable --now chrony
chronyc tracking               # offset deve ficar abaixo de 50 ms
timedatectl set-timezone UTC   # tudo em UTC, nos dois lados
```

**Todo timestamp gravado é UTC, em ISO 8601 com milissegundos.**

### 0.3 Versões fixadas

Registrar em `experimentos/ambiente.yaml` e **nunca atualizar no meio de uma campanha**:

```yaml
so: {distro: ..., kernel: ...}
hardware: {cpu: ..., nucleos: ..., ram: ..., dominios_rapl: [...]}
k3s: v1.xx.x
keda: v2.xx.x
python: 3.xx.x
framework_ml: {nome: ..., versao: ...}
k6: v0.xx.x
prometheus: v2.xx.x
scaphandre: v1.x.x
imagem_app: registro/app@sha256:...    # digest, nunca ':latest'
seed_global: 42
```

### 0.4 Higiene da máquina antes de cada sessão

```bash
sudo bash scripts/preparar_server.sh --aplicar   # governor, suspensão, timers do apt
sudo systemctl isolate multi-user.target         # desliga a GUI
sudo swapoff -a                                  # se houver RAM sobrando
```

Registrar em `meta.json` de cada execução: governor, temperatura inicial, swap, uptime,
processos ativos. **Se algo mudou, a execução não é comparável.**

### 0.5 Determinismo

- Semente única (`seed_global`) para NumPy, framework de ML e ruído dos perfis
- Perfis do k6 com taxa de chegada fixa (`constant-arrival-rate`), não `ramping-vus`
- Nenhum `:latest` em imagem de container — sempre digest
- Tudo versionado: manifestos, perfis do k6, configuração da política

---

## FASE 1 — Aplicação sob teste

### 1.1 Requisitos

- CRUD simples (a aplicação em si é irrelevante para a tese)
- **Um endpoint com consumo de CPU previsível e ajustável** — sem isso a carga não
  move o consumo e não há o que medir
- Sem estado local: sessão e dados no banco
- Tempo de inicialização conhecido e estável (entra no termo de *cold start*)

### 1.2 Endpoints mínimos

| Rota | Função |
|---|---|
| `GET /health` | *readiness probe* |
| `GET /items`, `POST /items` | CRUD, carga leve |
| `GET /work?n=N` | **carga de CPU controlada** — endpoint dos experimentos |
| `GET /metrics` | métricas da aplicação (RPS, latência, erros) |

Calibrar `N` para que uma réplica sature perto de 100% de CPU sob carga conhecida.

### 1.3 Manifestos

Em `experimentos/k8s/`: `deployment.yaml`, `service.yaml`, `scaledobject.yaml`.

Definir com cuidado:

- `resources.requests.cpu` e `limits.cpu` — determinam quantas réplicas cabem
- `readinessProbe` — quando o pod entra no balanceamento (fim do *cold start*)
- `terminationGracePeriodSeconds`

### 1.4 Medir o *cold start*

Subir e derrubar réplicas repetidamente e medir:

- `t_boot`: tempo entre a decisão e o pod ficar `Ready`
- `P_boot`: potência extra durante a inicialização

### 1.5 Medir os estados de energia dos nós

Para cada nó de trabalho:

| Medida | Como |
|---|---|
| Suspensão funciona? | `sudo systemctl suspend` |
| Acorda pela rede? | Wake-on-LAN a partir do plano de controle (`wakeonlan <MAC>`) |
| `t_acordar` | do pacote WoL até o nó ficar `Ready` no Kubernetes |
| `t_esvaziar` | do *drain* até o nó ficar sem pods da aplicação |
| `E_troca_no` | energia gasta para suspender e acordar (RAPL, quando o nó está ativo) |

Se a suspensão não funcionar no hardware, a alternativa é **esvaziar o nó sem desligar**
(economia menor, mas mensurável).

**Artefato:** imagem publicada com digest, manifestos versionados, `t_boot`, `P_boot`,
`t_acordar`, `t_esvaziar`, `E_troca_no`.

---

## FASE 2 — Instrumentação

### 2.1 O que é coletado

Coleta a **1 s**, consolidada em **15 s** no dataset (Fase 4).

| Fonte | Métrica | Onde |
|---|---|---|
| RAPL (script próprio) | `package`, `core`, `dram` (se houver) → watts | SUT |
| Scaphandre | consumo por processo e container | SUT |
| cAdvisor | CPU e memória por container | SUT |
| node-exporter | CPU, memória, frequência, temperatura, disco, rede do nó | SUT |
| kube-state-metrics | réplicas desejadas e prontas | SUT |
| k6 e `/metrics` da aplicação | RPS, latência média/p95/p99, erros, conexões | Cliente |
| Previsor e política | previsão e decisões | Cliente |

### 2.2 Leitor RAPL

Script próprio, ~50 linhas, em `controlador/medicao/rapl.py`:

- Lê `/sys/class/powercap/intel-rapl:*/energy_uj` (exige root)
- Potência = Δenergia ÷ Δtempo
- **Tratar o *wraparound*** em `max_energy_range_uj`
- Agregar múltiplos sockets
- Exporta para o Prometheus

Ponto de partida: `monitoring/rapl.py` do CarbonScaler (MIT), **com correções** — ele
soma o `core` junto com o `package` (contagem dupla) e grava 10 W fictícios quando a
leitura falha. Ver `docs/algoritmos.md`, seção 4.8.

O Scaphandre é usado para a atribuição por processo; o leitor próprio é a referência
do total, para conferir a soma.

### 2.3 Registro de decisões

Cada ciclo da política grava **uma linha**. É o que permite explicar qualquer escala na defesa:

```
ts, demanda_prevista, horizonte, n_atual, n_escolhido,
E_prevista[n], K[n], S[n], J[n] (vetor completo),
I_carbono, lambda, motivo, latencia_decisao_ms
```

### 2.4 Validação da instrumentação

- Potência atribuída aos containers + potência estática ≈ total do RAPL
- Teste dos containers ociosos (réplica do KubeWatt): container parado recebe **zero**
- Sobrecarga do Scaphandre medida e reportada

---

## FASE 3 — Calibração energética

### 3.1 Linha de base ociosa

Cluster de pé, aplicação com zero réplicas, 10 minutos, RAPL a 1 s.

**Saída:** `P_estatico` (média) e desvio padrão.

### PORTÃO 1 — o instrumento funciona?

- [ ] RAPL lê e o contador avança
- [ ] Potência ociosa estável: coeficiente de variação **< 5%** em 10 min
- [ ] Sem tarefas de fundo disparando durante a medição

### 3.2 Curva potência × utilização

Carga em degraus (10%, 20%, … 100% de CPU), 5 min cada, 3 repetições alternadas.

```
P(u) = P_estatico + (P_max − P_estatico) · (2u − u^r)
```

(Fan et al., 2007; `r ≈ 1,4` como ponto de partida). **Não usar reta**: o consumo
satura em carga alta, como o KubeWatt mostrou.

**Saídas:** `P_estatico`, `P_max`, `r`, R², erro residual.

### 3.2b Sobrecarga por réplica ⚠️

Antes do piloto: com **carga zero**, medir a potência com 0, 1, 2, … N réplicas ociosas
(10 min cada, 3 repetições alternadas).

```
sobrecarga(n) = P(n réplicas ociosas) − P(0 réplicas)
```

Num nó único, a CPU total é ditada pela demanda, não pelo número de réplicas. Se a
sobrecarga for desprezível, o autoscaler terá pouco a economizar num nó só. Ver
`docs/algoritmos.md`, "Síntese".

**Joelho do SMT:** repetir a curva da 3.2 verificando o achatamento acima do número de
núcleos físicos (efeito observado no KubeWatt).

### 3.2c Potência por estado do nó

| Estado | Medição |
|---|---|
| Nó ativo com carga | RAPL — curva `P(u)` da 3.2 |
| Nó ativo, **vazio** | RAPL — potência estática do nó |
| Nó **suspenso** | **sem leitura RAPL** → contado como 0 e declarado |

> A economia de suspender um nó, medida por RAPL, é um **limite inferior**: o consumo de
> placa-mãe, disco, ventoinhas e fonte também desaparece, mas o RAPL nunca o mediu.

### 3.3 Atribuição por pod

Modelo do KubeWatt:

```
potência(pod) = P_dinamica(nó) × CPU(pod) ÷ Σ CPU(pods)
```

A parte estática **não** é distribuída: é o custo de estar ligado, e o autoscaler
não age sobre ela.

### 3.4 Piloto de sensibilidade

**O experimento mais importante do projeto**, e ele vem antes de qualquer LSTM.

- Carga fixa (ex.: 200 req/s por 5 min)
- Cenário A: **2 réplicas fixas**. Cenário B: **6 réplicas fixas**. Sem autoscaler.
- 5 repetições cada, **alternando a ordem** (A, B, A, B, …)
- Descartar os primeiros 60 s de cada execução

### PORTÃO 2 — o sinal aparece?

- [ ] A diferença de energia entre A e B é **maior que a variação entre repetições do mesmo cenário**
- [ ] Mann-Whitney com p < 0,05
- [ ] Tamanho de efeito relatado

**Se não passar:** o instrumento não distingue 2 de 6 réplicas, e nunca vai distinguir
HPA de preditivo. Reformular a escala do experimento **antes** de seguir.

---

## FASE 4 — Geração do dataset

### 4.1 Perfis de carga

Roteiros do k6 em `experimentos/k6/`:

| Perfil | Forma | Uso |
|---|---|---|
| `comercial` | pico entre 9h e 18h, menor no fim de semana | treino |
| `noturno` | pico no fim do dia | treino |
| `rajadas` | picos curtos e imprevisíveis | **teste** (caso difícil) |
| `lote` | carga alta de madrugada | **teste** (domínio diferente, para o TL) |

Um "dia" de 24 h roda comprimido (ex.: 1 h de relógio). **Registrar o fator de
compressão**: ele altera o peso relativo do *cold start*.

Cada perfil deve cobrir **semanas simuladas**, para a LSTM ver a sazonalidade semanal
(dias úteis × fim de semana).

### 4.2 Schema oficial

**Granularidade: 15 s.** Uma linha por intervalo, por execução.
**Formato:** CSV UTF-8, separador vírgula, decimal com ponto, cabeçalho idêntico aos nomes abaixo.

#### Identificação

| Coluna | Unidade | Descrição |
|---|---|---|
| `timestamp` | ISO 8601 UTC, ms | início do intervalo |
| `experiment_id` | texto | identificador único da execução |
| `node_id` | texto | nó do cluster (anônimo) |
| `profile` | texto | perfil de carga |
| `repetition` | inteiro | número da repetição |
| `autoscaler` | texto | estratégia ativa: `fixo`, `hpa`, `cron`, `carbon_keda`, `preditivo`, `oraculo` |

#### Demanda — **o que a LSTM prevê**

| Coluna | Unidade | Papel |
|---|---|---|
| `requests_per_second` | req/s | **alvo da previsão** |
| `active_connections` | inteiro | entrada auxiliar |

> A previsão é feita sobre a **demanda**, não sobre a CPU. A CPU por pod cai quando o
> autoscaler sobe réplicas, mesmo com a demanda subindo — ela reflete a decisão já
> tomada, não a necessidade.

#### Desempenho — SLA

| Coluna | Unidade | Papel |
|---|---|---|
| `http_latency_mean_ms` | ms | referência |
| `http_latency_p95_ms` | ms | **SLA** |
| `http_latency_p99_ms` | ms | cauda |
| `http_errors_per_second` | erros/s | violação dura |

#### Kubernetes

| Coluna | Unidade | Papel |
|---|---|---|
| `replicas_desired` | inteiro | decisão do autoscaler |
| `replicas_ready` | inteiro | capacidade efetiva |
| `pods_starting` | inteiro | *cold starts* em andamento |
| `node_state` | texto | `ativo`, `esvaziando`, `suspenso`, `acordando` |
| `nodes_active` | inteiro | nós ligados no cluster naquele instante |

> ⚠️ **As colunas de réplicas nunca são alvo da LSTM.** Elas registram o que o
> autoscaler ativo decidiu durante a coleta; aprender isso seria copiar os atrasos
> do HPA. Servem ao modelo de energia e à avaliação.

#### Aplicação

| Coluna | Unidade | Papel |
|---|---|---|
| `app_cpu_cores` | núcleos | soma de todos os pods da aplicação |
| `app_memory_bytes` | bytes | soma de todos os pods da aplicação |

#### Infraestrutura do nó

| Coluna | Unidade | Papel |
|---|---|---|
| `node_cpu_usage_ratio` | 0,00–1,00 | inclui SO e ruído de fundo |
| `node_memory_usage_bytes` | bytes | |
| `cpu_frequency_mhz` | MHz | correlação com DVFS |
| `cpu_temperature_celsius` | °C | controle de *throttling* |
| `disk_io_bytes_per_second` | bytes/s | leitura + escrita |
| `network_rx_bytes_per_second` | bytes/s | |
| `network_tx_bytes_per_second` | bytes/s | |

#### Energia

| Coluna | Unidade | Papel |
|---|---|---|
| `rapl_package_watts` | W | **medido** — pacote do processador, não o servidor |
| `rapl_core_watts` | W | medido |
| `rapl_dram_watts` | W | medido, se o processador expuser; vazio caso contrário |
| `power_static_watts` | W | constante da calibração (Fase 3) |
| `power_dynamic_watts` | W | `rapl_package_watts − power_static_watts` |
| `app_power_watts` | W | **estimado** pelo modelo de atribuição |
| `energy_joules_interval` | J | energia **no intervalo** (não acumulada) |

#### Carbono

| Coluna | Unidade | Papel |
|---|---|---|
| `carbon_intensity_gco2_kwh` | gCO₂/kWh | cruzado pelo timestamp (fator do SIN) |
| `emissions_gco2_interval` | gCO₂ | `energy_joules_interval ÷ 3,6·10⁶ × carbon_intensity_gco2_kwh` |

### 4.3 Estrutura de arquivos

```
dados/
├── bruto/<profile>_<repetition>_<autoscaler>_<ts>/
│   ├── rapl.csv            1 s
│   ├── scaphandre.csv      1 s
│   ├── prometheus.csv      1 s
│   ├── k6.csv              1 s
│   ├── decisoes.csv        por ciclo (quando houver política)
│   └── meta.json           versões, hardware, governor, temperatura, seed
└── processado/
    └── dataset_15s.csv     schema oficial, todas as execuções
```

### 4.4 Separação treino/teste ⚠️

**Por perfil, nunca aleatória.** Série temporal embaralhada vaza informação do futuro
e infla o resultado.

- Treino: `comercial`, `noturno`
- Teste: `rajadas`, `lote` — **nunca vistos no treino**

O k6 tem dois papéis distintos: aqui ele **gera os dados**; na Fase 8 ele **executa
os testes**, com os perfis reservados.

---

## FASE 5 — Previsão de demanda

### 5.1 Baselines primeiro

Antes de qualquer rede neural, com o **mesmo alvo** (`requests_per_second`):

| Baseline | O que faz | Por que importa |
|---|---|---|
| Persistência | demanda futura = demanda atual | piso mínimo |
| Média móvel | média das últimas janelas | suaviza ruído |
| **Perfil histórico por horário** | média do mesmo horário e dia da semana | **é o que o escalonamento por agenda já faz** |
| Regressão com *lags* | t−1, t−2, …, hora, dia da semana | modelo simples forte |

> O **perfil histórico por horário** é o concorrente decisivo. Se a LSTM não o vencer,
> a rede neural não se justifica: bastaria o *cron scaler* do KEDA. A LSTM só agrega
> valor se captar **quando hoje foge do padrão**: o pico veio maior ou mais cedo.

### 5.2 LSTM

- Entrada: janela de `w` passos de `requests_per_second` + hora do dia + dia da semana
- Saída: demanda para o horizonte `h`
- **`h` maior que `t_boot`** (Fase 1): prever para antes disso não adianta, o pod não fica pronto a tempo
- **Validação temporal** (janela deslizante), nunca embaralhada
- Métricas: MAE, MAPE, RMSE **por horizonte**

**Regra:** se um baseline empatar, ele vence. É mais barato de treinar e executar, o
que já é um argumento energético.

### 5.3 Transfer Learning

| Cenário | Descrição |
|---|---|
| **A — do zero** | treinar no perfil de destino a partir de pesos aleatórios |
| **B — *fine-tuning*** | pré-treinar no perfil de origem, congelar as camadas iniciais, ajustar a final |

Medir nos dois, **com RAPL, no mesmo hardware**:

- joules por sessão de treino
- épocas até convergir
- MAPE final
- **joules por ponto de MAPE ganho**

**Saídas:** modelos versionados com hash; `experimentos/resultados/tl_comparacao.csv`.

---

## FASE 6 — Política de decisão

### 6.1 A função

```
J(n) = α·Ê(n)·(1 + λ·Î(t))  +  β·K(Δn⁺)  +  γ·S(n)

n* = arg min J(n),  para n em [n_min, n_max]
```

| Termo | O que é | De onde vem |
|---|---|---|
| `Ê(n)` | energia prevista com `n` réplicas | demanda prevista (Fase 5) + `P(u)` (Fase 3) |
| `Î(t)` | intensidade de carbono **normalizada** pela média (1,0 = típico) | fator do SIN por mês e hora |
| `λ` | peso do carbono — **pequeno**, porque é secundário | varredura |
| `K(Δn⁺)` | custo do *cold start*, só quando sobe: `Δn⁺ · P_boot · t_boot` | Fase 1 |
| `S(n)` | penalidade de SLA, cresce rápido quando a capacidade fica abaixo da demanda | modelo de fila ou empírico |

### 6.2 A faixa segura

O carbono **nunca** tira o sistema da faixa que atende o SLA:

```
n_min(SLA) ≤ n ≤ n_max(útil)
```

Dentro dela: matriz limpa → mais folga; matriz suja → menos folga. O termo `γ` domina.

A matriz energética brasileira varia **mais entre meses** (período seco, térmicas
despachadas) do que entre horas. Incluir o mês em `Î(t)` é tão importante quanto a hora.

### 6.3 Nível de máquinas

Depois de escolher `n*` pods para a demanda prevista no horizonte longo:

```
m* = menor número de nós que acomoda n* pods (pelos requests) + folga

liga um nó se:     previsão em t + t_acordar exige mais nós que os ativos
suspende um nó se: previsão até t + h_nó cabe nos demais nós
                   e a energia economizada no período supera E_troca_no
```

- **Histerese**: exigir a condição de suspender por um tempo mínimo, para não oscilar
- **Nunca** suspender o nó do plano de controle
- O carbono (`Î(t)`) pode antecipar a suspensão em horário de matriz suja, **sem** tirar
  o sistema da faixa segura

### 6.4 Varredura de pesos

Variar `α`, `β`, `γ`, `λ` e desenhar a **fronteira de Pareto** entre energia e latência.
É um resultado por si só.

---

## FASE 7 — Controlador

### 7.1 Arquitetura: a política decide, o KEDA executa

Em vez de escrever diretamente no Deployment, a política **publica o número de réplicas
desejado como métrica**, e o KEDA o executa. Nada de reimplementar atuação de escala.

```
a cada ciclo (ex.: 15 s), no cliente:
  1. lê a demanda recente no Prometheus
  2. a LSTM prevê a demanda para t+h
  3. calcula J(n) para todo n na faixa segura
  4. publica n* como métrica: autoscaler_desired_replicas
  5. grava a linha de decisão
```

No SUT, um `ScaledObject` do KEDA com **dois gatilhos**:

```yaml
triggers:
  - type: cpu                      # reativo: a rede de segurança
    metricType: Utilization
    metadata: {value: "60"}
  - type: prometheus               # proativo: a decisão da política
    metadata:
      serverAddress: http://<cliente>:9090
      query: autoscaler_desired_replicas
      threshold: "1"               # réplicas = ceil(valor / 1) = n*
```

### 7.2 Segurança sem código extra

- **Com vários gatilhos, o HPA usa o maior valor.** Isso implementa nativamente a
  regra `max(reativo, preditivo)`: a política só antecipa capacidade, nunca remove a
  que o reativo julgou necessária
- `minReplicaCount` e `maxReplicaCount` como limites rígidos
- Se a política parar mas o Prometheus continuar de pé, a série fica vazia, o KEDA a trata
  como 0 e o gatilho de CPU decide sozinho. **Se o próprio Prometheus ficar inacessível**,
  o HPA deixa de reduzir réplicas. Ver `docs/algoritmos.md`, seção 2.5
- **A tolerância de 10% do HPA vale sobre a métrica publicada:** com muitas réplicas,
  ajustes pequenos são ignorados. Ver `docs/algoritmos.md`, seção 2.4
- O processo roda **no cliente**, fora do SUT; seu consumo é medido **em separado** e reportado

### 7.3 Atuação no nível de máquinas

| Peça | Função |
|---|---|
| kube-scheduler com `MostAllocated` | coloca pods novos nos nós já ocupados, deixando outros vazios |
| descheduler `HighNodeUtilization` | reagrupa pods depois de uma redução, esvaziando nós |
| Cluster Autoscaler + `externalgrpc` | decide e pede a remoção ou adição de nós |
| Provedor gRPC próprio | traduz "remover nó" em *drain* + suspensão, e "adicionar" em Wake-on-LAN |

Para o baseline reativo, o Cluster Autoscaler roda com os padrões (limiar de 0,5 sobre
requests, 10 min). Na proposta, a decisão `m*` da política é que dispara o provedor.

---

## FASE 8 — Avaliação

### 8.1 Concorrentes

Cada ferramenta isolada, contra a composição:

| Estratégia | Implementação | Papel |
|---|---|---|
| Alocação fixa | réplicas constantes (várias) | piso e teto |
| **Reativo** | KEDA só com gatilho de CPU (= HPA) | o concorrente principal |
| **Agenda** | KEDA *cron scaler* com o perfil histórico | o "já existe pronto" |
| **Carbono reativo** | Carbon-Aware KEDA Operator | escala por carbono sem previsão |
| **Proposta** | KEDA com gatilho de CPU + gatilho da política | a composição |
| **Oráculo** | política com a demanda futura real | teto do ganho possível |
| **Nós: todos ligados** | sem escala de máquinas | referência de consumo máximo |
| **Nós: reativo** | Cluster Autoscaler com os padrões | o "já existe pronto" para máquinas |
| **Nós: proposta** | decisão `m*` com previsão | a composição completa |

O oráculo separa *"a política é ruim"* de *"a previsão é ruim"*.

### 8.2 Protocolo

- Perfis **reservados** (`rajadas`, `lote`), não usados no treino
- **≥ 15 repetições** por combinação
- **Ordem alternada** entre estratégias
- Linha de base ociosa medida **antes e depois** de cada execução
- Aquecimento de 60 s descartado
- Reinício limpo do cluster entre execuções

### 8.3 Métricas

| Dimensão | Métrica |
|---|---|
| Energia | joules por requisição; energia dinâmica total |
| Carbono | gCO₂e por requisição (SCI) |
| Desempenho | p95 e p99; violações de SLA; erros |
| Estabilidade | eventos de escala; *cold starts*; oscilação |
| Previsão | MAE e MAPE por horizonte |
| Custo do ML | joules de treino; do zero × *fine-tuning* |
| Sobrecarga | consumo da própria política |
| Máquinas | nós-hora ativos; número de suspensões; SLA durante `t_acordar` |
| Energia de nós | por nó ativo (medida) + suspensos (0, declarado) — **limite inferior** |

### 8.4 Estatística

- **Mediana e IC 95%** por reamostragem (*bootstrap*)
- **Mann-Whitney** para comparar estratégias
- **Tamanho de efeito** sempre junto do valor-p
- Variabilidade entre repetições **sempre reportada**

### PORTÃO 3 — o resultado se sustenta?

- [ ] Ganho energético fora do intervalo de confiança do reativo **e** da agenda
- [ ] SLA **não piorou** em relação ao reativo
- [ ] Resultado se mantém nos dois perfis reservados
- [ ] Ganho ainda existe descontando o consumo da própria política

---

## FASE 9 — Análise e replicação

### 9.1 Conversão para carbono

```
CO₂ evitado = energia economizada × fator de emissão do SIN
```

Fator do MCTI **por mês**. Reportar também no formato SCI, com `R = requisição`.

### 9.2 O que sempre declarar

- RAPL mede **o pacote do processador**, não o servidor
- Sem referência física: o erro **absoluto** não é conhecido; a comparação é **relativa**
- `app_power_watts` é **estimado** por modelo de atribuição
- Tráfego sintético; um único nó

### 9.3 Pacote de replicação

A entrega que torna a metodologia utilizável por outras pessoas:

```
├── ambiente.yaml           versões exatas
├── k8s/                    manifestos + ScaledObjects
├── k6/                     perfis de carga
├── politica/               previsor, J(n) e configuração
├── medicao/                leitor RAPL e consolidação no schema
├── analise/                notebooks que geram cada figura
├── dados/                  bruto e processado
└── README                  como reproduzir do zero
```

**Teste final:** apagar tudo e reconstruir a partir do repositório. Se não der, não é reproduzível.

---

## Mapa para a dissertação

| Fases | Capítulo |
|---|---|
| 0 a 4 | IV — Metodologia, bancada e dataset |
| 5 a 7 | V — Previsão, política e composição das ferramentas |
| 8 e 9 | VI — Avaliação experimental |

## Ordem de execução sugerida

1. **Fases 0 → 3 (Portão 2)** — o piloto decide se o projeto é viável
2. **Fase 4** — dataset
3. **Fase 5.1** — baselines, inclusive o perfil histórico por horário
4. **Fase 5.2** — LSTM
5. **Fases 6 e 7** — política e integração com o KEDA
6. **Fase 8** — avaliação contra cada ferramenta isolada
7. **Fase 5.3** — Transfer Learning, por último (é o diferencial, não a fundação)

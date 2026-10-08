# Algoritmos existentes — fichamentos técnicos

Estudo do **código-fonte** e dos **artigos** das ferramentas que a metodologia
reaproveita. O objetivo não é só usar as ferramentas, mas entender a regra de decisão
de cada uma e **identificar onde a proposta intervém**.

Cada fichamento segue o mesmo formato:

1. Referência (artigo, repositório, versão exata do código lido)
2. Entradas e saídas
3. O algoritmo, passo a passo, com o trecho do código ou a equação
4. Exemplo numérico
5. Limitações
6. **Pontos de intervenção** — onde a proposta muda o comportamento

## Índice

| # | Algoritmo | Papel no projeto | Licença | Status |
|---|---|---|---|---|
| 1 | **HPA** (Kubernetes) | baseline reativo principal | Apache-2.0 | ✅ |
| 2 | **KEDA** (gatilhos Prometheus e cron, fórmula, fallback) | atuação e baseline de agenda | Apache-2.0 | ✅ |
| 3 | **Carbon-Aware KEDA Operator** | baseline de carbono | MIT | ✅ |
| 4 | **CarbonScaler** (algoritmo guloso + leitor RAPL) | referência de escala por carbono; leitor RAPL | MIT | ✅ |
| 5 | **KubeWatt** (divisão estática/dinâmica) | atribuição de energia | sem licença — só o modelo | ✅ |
| 6 | **Modelo de potência de Fan et al. (2007)** | estimativa `P(u)` | artigo | ✅ |
| 7 | Cluster Autoscaler (provedor `externalgrpc`) | escala de máquinas; baseline reativo de nós | Apache-2.0 | pendente |
| 8 | kube-scheduler `MostAllocated` + descheduler `HighNodeUtilization` | agrupar pods para esvaziar nós | Apache-2.0 | pendente |

---

# 1. HPA — Horizontal Pod Autoscaler

## 1.1 Referência

| Item | Valor |
|---|---|
| Repositório | `github.com/kubernetes/kubernetes` |
| Licença | Apache-2.0 |
| Código lido | commit `f9831f7c949f` (16/09/2026) |
| Documentação | kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/ |

| Arquivo | Conteúdo |
|---|---|
| `pkg/controller/podautoscaler/replica_calculator.go` | cálculo do número de réplicas |
| `pkg/controller/podautoscaler/horizontal.go` | laço de controle, múltiplas métricas, estabilização, limites |
| `pkg/controller/podautoscaler/metrics/utilization.go` | razão de utilização |
| `pkg/controller/podautoscaler/config/v1alpha1/defaults.go` | parâmetros padrão do controlador |
| `pkg/apis/autoscaling/v2/defaults.go` | políticas padrão de subida e descida |

> ⚠️ Os nomes de função e números de linha mudam entre versões. Ao citar na
> dissertação, fixar a versão do Kubernetes usada nos experimentos e reler o código
> dessa versão.

## 1.2 Entradas e saídas

**Entradas**
- Réplicas atuais do Deployment
- Uso de CPU de cada pod, vindo do metrics-server (média de uma janela **passada**)
- `requests.cpu` de cada pod
- Alvo de utilização (ex.: 60%)
- Estado de cada pod: pronto, pendente, sendo removido, sem métrica
- Histórico das recomendações recentes
- `minReplicas`, `maxReplicas` e as políticas de `behavior`

**Saída**
- Novo valor de `.spec.replicas`

## 1.3 Parâmetros padrão

| Parâmetro | Padrão | Flag do `kube-controller-manager` |
|---|---|---|
| Período do laço | **15 s** | `--horizontal-pod-autoscaler-sync-period` |
| Tolerância | **0,1** (10%) | `--horizontal-pod-autoscaler-tolerance` |
| Janela de estabilização na descida | **300 s** | `--horizontal-pod-autoscaler-downscale-stabilization` |
| Janela de estabilização na subida | **0 s** | via `behavior.scaleUp` |
| Período de inicialização de CPU | **5 min** | `--horizontal-pod-autoscaler-cpu-initialization-period` |
| Atraso inicial de prontidão | **30 s** | `--horizontal-pod-autoscaler-initial-readiness-delay` |
| Limite de subida | **+4 pods ou +100%** a cada 15 s (o maior) | via `behavior.scaleUp.policies` |
| Limite de descida | **−100%** a cada 15 s | via `behavior.scaleDown.policies` |

Todos esses valores devem ser **registrados** em `experimentos/ambiente.yaml`: eles
definem o baseline.

## 1.4 O algoritmo, passo a passo

O laço roda a cada 15 s e executa seis etapas.

### Etapa 1 — Classificar os pods (`groupPods`)

Cada pod cai em uma de quatro categorias:

| Categoria | Critério | Tratamento |
|---|---|---|
| **ignorado** | sendo removido ou já terminado | fora da conta |
| **não pronto** | `Pending`; ou, para CPU, ainda dentro dos 5 min de inicialização e não `Ready` | fora da primeira conta |
| **sem métrica** | o metrics-server não devolveu dado | tratado na etapa 4 |
| **pronto** | todo o resto | entra na conta |

```go
if pod.Status.Phase == v1.PodPending {
    unreadyPods.Insert(pod.Name)
    continue
}
// Pod still within possible initialisation period.
if pod.Status.StartTime.Add(cpuInitializationPeriod).After(time.Now()) {
    unready = condition.Status == v1.ConditionFalse || metric.Timestamp.Before(...)
}
```

**Por quê:** um pod recém-criado tem pico de CPU na inicialização, que enganaria a conta.

### Etapa 2 — Razão de utilização (`GetResourceUtilizationRatio`)

```
utilização = (Σ uso de CPU dos pods) × 100 / (Σ requests.cpu dos pods)
razão      = utilização / alvo
```

```go
currentUtilization = int32((metricsTotal * 100) / requestsTotal)
return float64(currentUtilization) / float64(targetUtilization), ...
```

Dois detalhes importantes:

- É uma razão de **somas**, não a média das razões de cada pod
- A referência é o **`requests`**, não a capacidade da máquina: um `requests` mal
  dimensionado distorce toda a decisão

### Etapa 3 — Tolerância

```go
func (t Tolerances) isWithin(usageRatio float64) bool {
    return (1.0-t.scaleDown) <= usageRatio && usageRatio <= (1.0+t.scaleUp)
}
```

Se `0,9 ≤ razão ≤ 1,1`, **mantém as réplicas atuais**. Evita oscilar por ruído.

A tolerância pode ser configurada **por HPA e separadamente para subir e descer**
(`behavior.scaleUp.tolerance`, `behavior.scaleDown.tolerance`). Isso depende da versão:
recurso *alpha* no 1.33, ativo por padrão desde o 1.35, estável no 1.37.

### Etapa 4 — Calcular as réplicas

**Caso simples** (nenhum pod sem métrica, e não está subindo com pods não prontos):

```
réplicas = ⌈ razão × pods_prontos ⌉
```

```go
return ceilToInt32(usageRatio * float64(readyPodCount)), ...
```

Repare: multiplica pelos pods **prontos**, não pelas réplicas atuais.

**Caso com incerteza** — o HPA preenche as lacunas de forma **conservadora** e refaz a conta:

| Situação | Suposição |
|---|---|
| Descendo, pod sem métrica | assume que ele usa **100%** do request |
| Subindo, pod sem métrica | assume que ele usa **0%** |
| Subindo, pod não pronto | assume que ele usa **0%** |

Se a nova razão **inverter a direção** (a conta original mandava subir e a nova manda
descer, ou vice-versa), ele **não mexe em nada**.

```go
if tolerances.isWithin(newUsageRatio) || (usageRatio < 1.0 && newUsageRatio > 1.0) || (usageRatio > 1.0 && newUsageRatio < 1.0) {
    // return the current replicas if ... the new usage ratio would cause a change in scale direction
    return currentReplicas, ...
}
```

### Etapa 5 — Várias métricas: vale a maior (`computeReplicasForMetrics`)

Com mais de uma métrica, calcula uma recomendação para cada e fica com a **maior**:

```go
if replicas == 0 || replicaCountProposal > replicas {
    replicas = replicaCountProposal
}
```

**Esta regra é a base do desenho do controlador** (`docs/pipeline.md`, Fase 7): o gatilho
de CPU e o gatilho preditivo convivem, e prevalece o maior. O preditivo só antecipa
capacidade, nunca remove a que o reativo julgou necessária.

### Etapa 6 — Estabilizar e limitar (`stabilizeRecommendationWithBehaviors`)

O HPA guarda as recomendações recentes e aplica duas janelas:

```go
if rec.timestamp.After(upCutoff) {
    upRecommendation = min(rec.recommendation, upRecommendation)
}
if rec.timestamp.After(downCutoff) {
    downRecommendation = max(rec.recommendation, downRecommendation)
}
```

| Direção | Regra | Efeito com o padrão |
|---|---|---|
| **Descer** | usa a **maior** recomendação dos últimos 300 s | só reduz se durante 5 min inteiros ninguém pediu mais |
| **Subir** | usa a **menor** recomendação da janela | janela padrão de 0 s → sobe na hora |

Depois aplica os limites de taxa: subir no máximo **+4 pods ou +100%** a cada 15 s
(o maior dos dois), e respeitar `minReplicas` e `maxReplicas`.

Sem `behavior` configurado (modo legado), o limite de subida é
`max(2 × réplicas_atuais, 4)`.

## 1.5 Pseudocódigo consolidado

```
a cada 15 s:
    prontos, não_prontos, sem_métrica ← classificar(pods)

    razão ← (Σ uso_CPU / Σ requests) / alvo          # só com os prontos

    se não há incerteza:
        se 0,9 ≤ razão ≤ 1,1:  proposta ← réplicas_atuais
        senão:                  proposta ← ⌈razão × |prontos|⌉
    senão:
        preencher lacunas de forma conservadora
        refazer a razão
        se mudou de direção ou ficou na tolerância: proposta ← réplicas_atuais
        senão: proposta ← ⌈nova_razão × |pods com métrica|⌉

    proposta ← máximo entre as propostas de todas as métricas

    se descendo: proposta ← máximo das propostas dos últimos 300 s
    proposta ← limitar(proposta, taxa, minReplicas, maxReplicas)

    .spec.replicas ← proposta
```

## 1.6 Exemplo numérico

Alvo de 60%, `requests.cpu = 500m` por pod, 4 réplicas prontas.

**Instante 1 — a carga sobe:**

| | |
|---|---|
| Uso somado | 1.800m |
| Requests somados | 4 × 500m = 2.000m |
| Utilização | 1.800 × 100 / 2.000 = **90%** |
| Razão | 90 / 60 = **1,5** → fora da tolerância |
| Proposta | ⌈1,5 × 4⌉ = **6** |
| Limite de subida | máx(+4, +100%) = até 8 → **6 réplicas** |

**Instante 2 — 15 s depois, os 2 pods novos ainda estão iniciando:**

Eles são "não prontos" e ficam fora da conta. A carga continua sobre os 4 pods antigos,
e a razão continua alta. **O HPA não enxerga que a capacidade já está a caminho.**

**Instantes seguintes — a carga cai para 600m:**

Utilização = 600 × 100 / 3.000 = 20%. Razão = 0,33. Proposta = ⌈0,33 × 6⌉ = **2**.

Mas nos últimos 300 s houve uma recomendação de 6. **O HPA mantém 6 réplicas por até
5 minutos** depois da queda.

## 1.7 Limitações

| Limitação | Onde no código | Consequência |
|---|---|---|
| **Reage ao passado** | a métrica do metrics-server é média de uma janela já transcorrida | a decisão chega depois da demanda |
| **Não vê capacidade a caminho** | `groupPods` exclui pods em inicialização | pode pedir réplicas demais durante o *cold start* |
| **Decide por `requests`, não por demanda** | `metricsTotal * 100 / requestsTotal` | depende de um dimensionamento manual correto |
| **Soma esconde desequilíbrio** | razão de somas, não por pod | um pod saturado com os outros ociosos não dispara escala |
| **Descida lenta por projeto** | janela de 300 s com `max` | réplicas ociosas por até 5 min = **energia desperdiçada** |
| **Supõe escala linear** | `⌈razão × prontos⌉` | ignora retorno decrescente (lei de Amdahl, ver CarbonScaler) |
| **Energia não existe** | nenhuma entrada é energética | nenhuma decisão considera consumo ou matriz energética |
| **Custo do *cold start* não existe** | nenhum termo de custo de subida | sobe e desce sem pesar a energia de iniciar pods |

## 1.8 Pontos de intervenção

Três níveis, **do menos ao mais invasivo**. A metodologia usa só os dois primeiros.

### Nível 1 — Configuração (sem código)

| O que ajustar | Onde | Relação com a proposta |
|---|---|---|
| Janela de descida | `behavior.scaleDown.stabilizationWindowSeconds` | reduzir o desperdício pós-pico; pode ser **ajustada pela matriz energética** |
| Tolerância de subida e descida | `behavior.scale*.tolerance` | assimetria: subir fácil, descer com cautela, ou o contrário |
| Políticas de taxa | `behavior.scale*.policies` | limitar *cold starts* em sequência |

Estes parâmetros sozinhos já formam um **baseline adicional**: o "HPA bem ajustado".
Se a proposta não vencer o HPA bem ajustado, a banca vai notar.

### Nível 2 — Métrica externa (a proposta)

Sem alterar o código do HPA. A política publica o número de réplicas desejado e o
KEDA o entrega como métrica. A **regra do máximo** (etapa 5) combina com o gatilho de CPU.

| Limitação do HPA | Como a métrica externa resolve |
|---|---|
| Reage ao passado | a métrica já é a **demanda prevista** para `t + h` |
| Não vê capacidade a caminho | o horizonte `h` é maior que `t_boot`: a réplica fica pronta antes do pico |
| Decide por `requests` | decide por **requisições/s** previstas |
| Energia não existe | `J(n)` inclui `Ê(n)` e a matriz energética |
| Custo do *cold start* não existe | `J(n)` inclui `K(Δn⁺)` |
| Descida lenta | a política pode baixar a recomendação cedo — mas o gatilho de CPU e a janela ainda seguram (ver abaixo) |

> ⚠️ **Consequência da regra do máximo:** a métrica preditiva consegue **antecipar a
> subida**, mas **não consegue acelerar a descida** enquanto o gatilho de CPU pedir
> mais réplicas, e a janela de 300 s continua valendo sobre o resultado combinado.
> Para economizar na descida é preciso **também** o nível 1: reduzir a janela de
> estabilização. Isso precisa ser medido — é onde mora boa parte da economia e também
> o risco de oscilação.

### Nível 3 — Alterar o código (evitar)

Um *fork* do controlador permitiria, por exemplo, contar pods em inicialização como
capacidade futura. **Não será feito:** quebra a reprodutibilidade, prende a metodologia
a uma versão e contradiz o princípio de compor ferramentas existentes.

## 1.9 O que registrar nos experimentos

- Versão exata do Kubernetes e do KEDA
- Todos os parâmetros da seção 1.3, inclusive os que ficaram no padrão
- Todo `behavior` aplicado
- As condições do HPA a cada ciclo (`ScaleDownStabilized`, `ScaleUpLimit`,
  `TooManyReplicas`…): mostram **por que** ele não escalou quando deveria

```bash
kubectl get hpa -w
kubectl describe hpa <nome>          # condições e eventos
kubectl get hpa <nome> -o yaml       # behavior efetivo, com os padrões preenchidos
```


---

# 2. KEDA — Kubernetes Event-driven Autoscaling

## 2.1 Referência

| Item | Valor |
|---|---|
| Repositório | `github.com/kedacore/keda` |
| Licença | Apache-2.0 |
| Código lido | release **v2.20.2** (31/07/2026) |
| Documentação | keda.sh/docs |

| Arquivo | Conteúdo |
|---|---|
| `controllers/keda/hpa.go` | transforma o `ScaledObject` em um HPA |
| `pkg/scaling/executor/scale_scaledobjects.go` | ativação: escala de/para zero e *cooldown* |
| `pkg/scalers/prometheus_scaler.go` | gatilho Prometheus |
| `pkg/scalers/cron_scaler.go` | gatilho por agenda |
| `pkg/scaling/modifiers/formula.go` | fórmula que combina gatilhos |
| `pkg/fallback/fallback.go` | comportamento quando um gatilho falha |
| `apis/keda/v1alpha1/*_types.go` | parâmetros e padrões |

## 2.2 A ideia central: o KEDA não decide a escala

O ponto mais importante do código: **o KEDA não tem algoritmo próprio de escala entre
1 e N réplicas.** Ele faz três coisas:

1. **Cria e mantém um HPA** a partir do `ScaledObject`
2. **Serve métricas externas** para esse HPA (atua como *metrics adapter*)
3. **Cuida só da faixa 0 ↔ 1**, que o HPA não sabe fazer

Quem calcula quantas réplicas usar é o **algoritmo do HPA** (seção 1), com tudo o que
ele tem: tolerância de 10%, janela de 300 s, limites de taxa, regra do máximo.

```
ScaledObject ──► KEDA cria o HPA ──► HPA pergunta o valor das métricas
                                        │
                     KEDA consulta o gatilho (Prometheus, cron...) e responde
                                        │
                     HPA aplica o algoritmo da seção 1 ──► .spec.replicas
```

**Consequência para o projeto:** todas as limitações do HPA continuam valendo para a
proposta. Usar o KEDA não as remove — só permite entregar uma métrica melhor ao HPA.

## 2.3 Parâmetros padrão

| Parâmetro | Padrão | Efeito |
|---|---|---|
| `pollingInterval` | **30 s** | frequência com que o KEDA checa se os gatilhos estão ativos |
| `cooldownPeriod` | **300 s** | tempo sem gatilho ativo antes de voltar a **zero** |
| `initialCooldownPeriod` | **0 s** | carência após criar o `ScaledObject` |
| `minReplicaCount` | **0** | permite escalar a zero |
| `maxReplicaCount` | **100** | |
| `metricType` (métricas externas) | **`AverageValue`** | define como o HPA converte a métrica em réplicas |
| `fallback.behavior` | **`static`** | |
| `prometheus.ignoreNullValues` | **`true`** | resultado vazio vira 0, sem erro |

> ⚠️ **`pollingInterval` e `cooldownPeriod` só valem para a faixa 0 ↔ 1.** Entre 1 e N,
> o ritmo é o do HPA (15 s) e a descida segue a janela de 300 s do HPA. Com
> `minReplicaCount ≥ 1`, o `cooldownPeriod` não tem efeito nenhum.

## 2.4 O algoritmo, passo a passo

### Etapa 1 — Construir o HPA (`getScaledObjectMetricSpecs`)

Cada gatilho vira uma entrada `metrics` do HPA:

| Tipo de gatilho | Vira no HPA |
|---|---|
| `cpu`, `memory` | métrica **Resource** — igual a um HPA comum |
| todos os outros (Prometheus, cron...) | métrica **External**, servida pelo KEDA |

O `behavior` do HPA é copiado de `advanced.horizontalPodAutoscalerConfig.behavior`.
**É por aqui que se ajusta a janela de estabilização** (nível 1 de intervenção da seção 1.8).

### Etapa 2 — Converter a métrica externa em réplicas

Com o padrão `AverageValue`, o HPA usa `GetExternalPerPodMetricReplicas`:

```go
usageRatio := float64(usage) / (float64(targetUsagePerPod) * float64(replicaCount))
if !tolerances.isWithin(usageRatio) {
    replicaCount = ceilToInt32(float64(usage) / float64(targetUsagePerPod))
}
```

Ou seja:

```
réplicas = ⌈ valor_da_métrica / threshold ⌉      (se sair da tolerância)
```

Com `threshold: 1`, publicar o valor `n` pede **exatamente `n` réplicas**.

> ⚠️ **A tolerância de 10% continua valendo**, calculada sobre `n / réplicas_atuais`.
> Com 10 réplicas, publicar 11 dá razão 1,1 — dentro da tolerância — e **nada muda**.
> A política só consegue ajustes finos quando há poucas réplicas. Com muitas, só mudanças
> de mais de 10% passam. Ajustável pela tolerância configurável (seção 1.4, etapa 3).

### Etapa 3 — Gatilho Prometheus (`GetMetricsAndActivity`)

```go
val, err := s.ExecutePromQuery(ctx)
...
return []external_metrics.ExternalMetricValue{metric}, val > s.metadata.ActivationThreshold, nil
```

- Executa a consulta PromQL, que precisa devolver **um único valor**
- **Resultado vazio**, `NaN` ou `Inf`: com `ignoreNullValues: true` (padrão), vira **0** sem erro
- **Mais de um valor**: erro
- O gatilho é "ativo" se `valor > activationThreshold` (padrão 0)

### Etapa 4 — Gatilho cron (`cron_scaler.go`)

```go
metricValue := float64(0)
if isWithinInterval {
    metricValue = float64(s.metadata.DesiredReplicas)
}
```

| Dentro da janela `start`–`end` | Fora da janela |
|---|---|
| métrica = `desiredReplicas` → pede esse número | métrica = 0 → os outros gatilhos decidem |

É um **degrau**: um valor fixo em cada horário, sem olhar a demanda real. Para montar o
baseline de agenda a partir do perfil histórico, usa-se **vários gatilhos cron**, um por
faixa de horário, e a regra do máximo do HPA combina todos.

### Etapa 5 — Fórmula entre gatilhos (`scalingModifiers`)

Opcional. Combina os valores dos gatilhos externos numa expressão
(biblioteca `expr-lang`) e gera **uma única métrica composta**:

```yaml
advanced:
  scalingModifiers:
    formula: "(previsao + carbono) / 2"
    target: "1"
```

Os gatilhos externos são **substituídos** pela métrica composta; os de CPU e memória
**continuam separados** e a regra do máximo segue valendo entre eles.

### Etapa 6 — Ativação 0 ↔ 1 (`RequestScale`)

A cada `pollingInterval`:

| Situação | Ação |
|---|---|
| Algum gatilho ativo e réplicas = 0 | sobe para 1 (ou `minReplicaCount`) |
| Nenhum gatilho ativo há mais que `cooldownPeriod`, `minReplicaCount = 0` | desce a zero |
| Resto | deixa o HPA trabalhar |

### Etapa 7 — Falha de um gatilho (`fallback`)

Se um gatilho falhar mais que `failureThreshold` vezes seguidas, o KEDA passa a
responder um valor que leva o HPA a `fallback.replicas`. Comportamentos:
`static`, `currentReplicas`, `currentReplicasIfHigher`, `currentReplicasIfLower`,
`scalingModifiers`.

## 2.5 O que acontece quando a política falha

Esta seção corrige uma afirmação simplificada do `docs/pipeline.md`. O comportamento
depende de **como** a falha acontece:

| Falha | O que o KEDA vê | Resultado |
|---|---|---|
| A política para, **Prometheus continua de pé** | série vazia → `ignoreNullValues` → **0** | o gatilho pede 0; **a CPU decide sozinha** ✅ |
| **O Prometheus fica inacessível** (ele está no notebook) | erro na consulta | regra do HPA: com métrica inválida, **não desce abaixo do atual** — sobe pela CPU, mas não economiza |
| Idem, com `fallback` configurado | após `failureThreshold` falhas | vai para `fallback.replicas` |

> ⚠️ **Dependência de rede:** com o Prometheus no cliente, o KEDA no SUT depende do
> notebook para funcionar. Se o notebook desligar no meio de um experimento, o cluster
> **para de reduzir réplicas**. Registrar e monitorar.

## 2.6 Exemplo — a composição do projeto

```yaml
spec:
  minReplicaCount: 1
  maxReplicaCount: 10
  advanced:
    horizontalPodAutoscalerConfig:
      behavior:
        scaleDown:
          stabilizationWindowSeconds: 60      # nível 1: descida mais rápida
  triggers:
    - type: cpu
      metricType: Utilization
      metadata: {value: "60"}
    - type: prometheus
      metadata:
        serverAddress: http://<cliente>:9090
        query: autoscaler_desired_replicas
        threshold: "1"
```

**Cenário:** 4 réplicas, política publica 7, CPU pede 5.

| Métrica | Conta | Proposta |
|---|---|---|
| CPU | algoritmo da seção 1 | 5 |
| Prometheus | ⌈7 / 1⌉; razão 7/4 = 1,75, fora da tolerância | 7 |
| **Máximo** | | **7** |
| Limite de subida | +4 ou +100% sobre 4 → até 8 | **7 réplicas** |

**Na descida:** a política publica 2, a CPU pede 3. O máximo é 3 — e, com a janela
reduzida para 60 s, o HPA pode chegar a 3 um minuto depois, em vez de cinco.

## 2.7 Limitações

| Limitação | Onde no código | Consequência |
|---|---|---|
| **Herda tudo do HPA** | o KEDA só gera o HPA | tolerância, janelas e regra do máximo continuam |
| **Tolerância de 10% sobre a métrica externa** | `GetExternalPerPodMetricReplicas` | ajustes pequenos ignorados com muitas réplicas |
| **Cron é um degrau cego** | `metricValue = DesiredReplicas` | não reage a um dia diferente do padrão |
| **Consulta PromQL precisa devolver um valor** | erro com `len(result) > 1` | a política deve publicar uma série única |
| **`ignoreNullValues` mascara falhas** | vazio vira 0 sem erro | uma política quebrada parece "pedir zero" |
| **Energia não existe** | nenhum gatilho energético nativo | depende de métrica externa |

## 2.8 Pontos de intervenção

| Nível | O que muda | Como |
|---|---|---|
| **1 — Configuração** | janela de descida, tolerâncias, taxa | `advanced.horizontalPodAutoscalerConfig.behavior` |
| **1 — Configuração** | baseline de agenda | vários gatilhos `cron` a partir do perfil histórico por horário |
| **2 — Métrica externa** | a decisão da política `J(n)` | gatilho `prometheus` com `threshold: 1` |
| **2 — Métrica externa** | matriz energética como gatilho separado | gatilho `prometheus` com a intensidade de carbono + `scalingModifiers.formula` |
| **2 — Segurança** | comportamento em falha | `fallback` com `currentReplicasIfHigher` |
| **3 — Código** | escalador próprio via gRPC (*external scaler*) | possível sem *fork* do KEDA, mas **desnecessário**: o gatilho Prometheus basta |

## 2.9 O que registrar nos experimentos

- Versão do KEDA
- O `ScaledObject` completo, inclusive os campos que ficaram no padrão
- O HPA gerado pelo KEDA:

```bash
kubectl get scaledobject <nome> -o yaml
kubectl get hpa keda-hpa-<nome> -o yaml       # o HPA real, com behavior efetivo
kubectl describe hpa keda-hpa-<nome>          # condições: ScaleDownStabilized, ScaleUpLimit...
kubectl get --raw "/apis/external.metrics.k8s.io/v1beta1/namespaces/<ns>/s0-prometheus?labelSelector=scaledobject.keda.sh%2Fname%3D<nome>"
                                              # o valor que o KEDA está entregando ao HPA
```


---

# 3. Carbon-Aware KEDA Operator (Microsoft)

## 3.1 Referência

| Item | Valor |
|---|---|
| Repositório | `github.com/Azure/carbon-aware-keda-operator` |
| Licença | MIT (alguns arquivos trazem cabeçalho Apache-2.0) |
| Código lido | commit `a2e60941c140` (03/09/2026) |
| Última release | **v0.2.0 (abr/2023)**, API `v1alpha1` |
| Dependência | compilado contra **KEDA v2.10** e `k8s.io/api` v0.26 |
| Contexto | *Carbon-Aware Computing White Paper* (Microsoft, 2023) |

| Arquivo | Conteúdo |
|---|---|
| `controllers/carbonawarekedascaler_controller.go` | laço de controle |
| `controllers/max_replica_getter.go` | escolhe o limite de réplicas pela intensidade de carbono |
| `controllers/eco_mode_setter.go` | quando desligar o modo econômico |
| `controllers/carbon_forecast_fetcher.go` | leitura dos dados de carbono |
| `api/v1alpha1/carbonawarekedascaler_types.go` | configuração |

> ⚠️ **Projeto praticamente parado.** Os únicos commits desde nov/2023 são de
> manutenção de CI. Compatibilidade com KEDA 2.20 **não testada pelos autores** —
> precisa ser verificada antes de usar como baseline.

## 3.2 A ideia central: um teto, não uma decisão

O operador **não escolhe quantas réplicas usar**. A cada 5 minutos ele **reescreve o
`maxReplicaCount` do `ScaledObject`** conforme a intensidade de carbono do momento:

```
energia limpa → teto alto   → o HPA escala livremente
energia suja  → teto baixo  → o HPA fica limitado, mesmo com demanda alta
```

Quem decide dentro do teto continua sendo o HPA (seção 1), via KEDA (seção 2).

## 3.3 Entradas e saídas

**Entradas**
- Série de intensidade de carbono (gCO₂/kWh) em um **ConfigMap**, com
  `timestamp`, `duration` (min) e `value`
- Faixas de carbono e o teto de réplicas de cada faixa
- Regras para desligar o modo econômico

**Saída**
- Novo `spec.maxReplicaCount` no `ScaledObject` (ou `ScaledJob`)

O operador **não consulta APIs de carbono**. Quem preenche o ConfigMap é um componente
separado (*kubernetes-carbon-intensity-exporter*, que usa o Carbon Aware SDK e o
WattTime). Existe também um modo *mock* que gera valores **aleatórios entre 529 e 580
gCO₂/kWh**, a cada 5 min.

## 3.4 O algoritmo, passo a passo

### Etapa 1 — Ler a intensidade atual (`findCarbonForecast`)

Procura no ConfigMap o registro cujo intervalo contém o instante atual:

```go
if (t.Equal(cf.Timestamp) || t.After(cf.Timestamp)) && t.Before(cf.Timestamp.Add(time.Duration(cf.Duration)*time.Minute)) {
    return &cf
}
```

> Apesar do nome *forecast*, **só o valor do momento atual é usado** para escolher o
> teto. A previsão futura no ConfigMap não entra na decisão — o operador é **reativo**
> à matriz energética.

### Etapa 2 — Verificar se o modo econômico deve ser desligado (`setEcoMode`)

Em ordem, desliga se:

| Regra | Configuração | Efeito |
|---|---|---|
| Agenda específica | `ecoModeOff.customSchedule` (início e fim em RFC 3339) | ex.: Black Friday |
| Agenda recorrente | `ecoModeOff.recurringSchedule` (cron) | ex.: horário comercial |
| **Carbono alto por tempo demais** | `ecoModeOff.carbonIntensityDuration` | ver abaixo |

A terceira regra é contraintuitiva, e é deliberada:

```go
if currentForecast.Value >= float64(carbonIntensityThreshold) {
    meetsThresholdCount++
}
...
if meetsThresholdCount == int(durationMins) {
    ecoModeStatus.IsDisabled = true
```

**Se a energia ficou suja durante todo o período configurado, o operador libera o
teto.** É uma válvula de segurança: evita manter a aplicação estrangulada por horas
seguidas.

Com o modo econômico desligado, o teto vira `ecoModeOff.maxReplicas`.

### Etapa 3 — Escolher o teto pela faixa (`getMaxReplicas`)

As faixas são ordenadas pelo limiar, e a intensidade é encaixada em `(anterior, atual]`:

```go
for index, element := range configs {
    var lowerBound float64 = 0
    if index > 0 {
        lowerBound = float64(configs[index-1].CarbonIntensityThreshold)
    }
    var upperBound float64 = float64(element.CarbonIntensityThreshold)
    if ci > lowerBound && ci <= upperBound {
        return element.MaxReplicas, nil
    }
}
return configs[len(configs)-1].MaxReplicas, nil
```

Acima da última faixa, vale o teto da última.

### Etapa 4 — Aplicar e reagendar

Escreve o teto em `scaledObject.Spec.MaxReplicaCount` e agenda a próxima execução para
o próximo múltiplo de 5 minutos (ou a duração do registro de carbono).

**Não há nenhuma consulta ao HPA, à demanda ou às réplicas atuais.** O comentário no
topo de `eco_mode_setter.go` diz que o caso "teto menor que o desejado pelo HPA" é
tratado no laço de controle, **mas esse tratamento não existe no código**.

## 3.5 Interação com o HPA — o efeito mais importante

Confirmado no código do HPA (`horizontal.go`, `reconcileAutoscaler`):

```go
} else if currentReplicas > hpa.Spec.MaxReplicas {
    rescaleReason = "Current number of replicas above Spec.MaxReplicas"
    desiredReplicas = hpa.Spec.MaxReplicas
    needsMetricComputation = false
```

**Quando o operador baixa o teto abaixo das réplicas atuais, o HPA corta imediatamente
para o teto** — sem calcular métricas, sem janela de estabilização de 300 s e sem
limite de taxa de descida.

| Situação | Resultado |
|---|---|
| Energia fica suja com a aplicação em pico | réplicas cortadas **de uma vez** para o teto |
| Demanda sobe com energia suja | o HPA quer mais, mas fica em `TooManyReplicas` → **SLA degrada** |
| Energia fica limpa | teto sobe; o HPA volta a escalar normalmente, com os limites de subida |

É exatamente o comportamento que a **faixa segura** da proposta evita
(`docs/pipeline.md`, Fase 6.2): no operador, o carbono **pode** tirar o sistema da
faixa que atende o SLA.

## 3.6 Exemplo numérico

Configuração:

```yaml
maxReplicasByCarbonIntensity:
  - carbonIntensityThreshold: 100    # (0, 100]   → até 10 réplicas
    maxReplicas: 10
  - carbonIntensityThreshold: 300    # (100, 300] → até 6
    maxReplicas: 6
  - carbonIntensityThreshold: 500    # (300, 500] e acima → até 3
    maxReplicas: 3
ecoModeOff:
  maxReplicas: 10
  carbonIntensityDuration:
    carbonIntensityThreshold: 450
    overrideEcoAfterDurationInMins: 120
```

| Horário | Carbono | Demanda pede | Teto | Réplicas |
|---|---|---|---|---|
| 14h | 80 | 8 | 10 | **8** |
| 19h | 320 | 8 | 3 | **3** — corte imediato de 8 para 3 |
| 19h05 | 330 | 9 | 3 | **3** — `TooManyReplicas`, latência sobe |
| 21h | 470 (há 2 h ≥ 450) | 9 | modo econômico desligado → 10 | **9** |

## 3.7 Limitações

| Limitação | Onde no código | Consequência |
|---|---|---|
| **Teto, não alvo** | só escreve `maxReplicaCount` | não economiza quando a demanda já está abaixo do teto |
| **Ignora a demanda e o SLA** | nenhuma leitura do HPA ou de métricas | pode estrangular a aplicação em pico |
| **Corte abrupto** | HPA pula a estabilização quando `atual > max` | quedas de capacidade instantâneas |
| **Reativo ao carbono** | usa só o valor do instante atual | a previsão disponível no ConfigMap é desperdiçada |
| **Granularidade de 5 min** | `requeueInterval := int32(5)` | defasagem entre a matriz e o teto |
| **Faixas manuais** | `maxReplicasByCarbonIntensity` | sem relação com o consumo real ou a eficiência |
| **Não mede energia** | nenhuma entrada energética | decide por carbono, sem saber quanto cada réplica consome |
| **Intensidade exatamente 0 cai na última faixa** | `ci > lowerBound` com `lowerBound = 0` | energia 100% limpa recebe o teto mais restritivo |
| **Manutenção** | sem mudanças funcionais desde 2023; KEDA 2.10 | risco de incompatibilidade |

## 3.8 Pontos de intervenção e uso no projeto

### Como baseline

Representa a abordagem **"carbono como restrição rígida"**. Configuração para os
experimentos:

- ConfigMap preenchido com o **fator de emissão do SIN** (MCTI / ONS), no formato
  `timestamp`, `duration`, `value` — não é preciso o exportador da Microsoft
- As mesmas faixas usadas na normalização de `Î(t)` da proposta, para a comparação ser justa
- **Registrar sempre** a condição `TooManyReplicas` do HPA: é a evidência de SLA sacrificado

### O que a proposta muda em relação a ele

| Operador | Proposta |
|---|---|
| carbono define um **teto rígido** | carbono **modula a folga** dentro da faixa segura (`λ` pequeno) |
| ignora demanda e SLA | `γ·S(n)` domina a decisão |
| reage ao carbono atual | usa a série do SIN, incluindo o mês |
| não mede energia | `Ê(n)` calibrado com RAPL |
| corte abrupto | respeita a janela de descida do HPA |

### O que pode ser reaproveitado

- **O formato do ConfigMap** (`timestamp`, `duration`, `value`) como padrão para
  publicar a intensidade de carbono no cluster
- **A válvula "sujo por tempo demais"**: uma boa ideia de segurança, que pode entrar
  na proposta como limite para a redução de folga
- **As métricas Prometheus** que ele exporta (`carbon intensity`, `max replicas`),
  úteis para os gráficos comparativos

## 3.9 O que registrar nos experimentos

```bash
kubectl get carbonawarekedascaler <nome> -o yaml       # configuração e condições
kubectl get scaledobject <nome> -o jsonpath='{.spec.maxReplicaCount}'
kubectl describe hpa keda-hpa-<nome>                   # TooManyReplicas = SLA limitado
kubectl get events --field-selector reason=MaxReplicaCountReconciled
```


---

# 4. CarbonScaler (UMass Amherst)

## 4.1 Referência

| Item | Valor |
|---|---|
| Artigo | HANAFY, W. A. et al. *CarbonScaler.* Proc. ACM POMACS, v. 7, n. 3, 2023. DOI 10.1145/3626788 |
| Resumo | `revisao_bibliografica/resumos/01_carbonscaler.md` |
| Repositório | `github.com/umassos/CarbonScaler` |
| Licença | MIT (cabeçalhos dos arquivos Go em Apache-2.0) |
| Código lido | commit `a274e4cf291a` (23/10/2023) — **último commit** |

| Arquivo | Conteúdo |
|---|---|
| `src/controllers/carbon_scaler.go` | **o algoritmo guloso** |
| `src/controllers/profiles.go` | leitura do perfil de capacidade e potência |
| `src/profiles/*.csv` | perfis medidos (réplicas × vazão × potência) |
| `src/controllers/carbonscalermpijob_controller.go` | aplica o cronograma ao job |
| `carbon_service/carbon_service.py` | serviço que publica intensidade e "previsão" de carbono |
| `monitoring/rapl.py` | **leitor RAPL em Python** |
| `monitoring/power_server.py` | expõe as leituras via HTTP |

## 4.2 A ideia central

Para um **job batch** com prazo, montar **antes de começar** um cronograma de quantos
servidores usar em cada fatia de tempo, alocando capacidade onde ela produz **mais
trabalho por unidade de carbono**. Diferente do HPA e do KEDA, não reage a nada: planeja.

## 4.3 Entradas e saídas

**Entradas**
- Perfil da aplicação: vazão e potência para cada número de réplicas
- Intensidade de carbono prevista para cada fatia até o prazo
- Mínimo e máximo de réplicas, prazo (em fatias), tamanho total do trabalho, progresso

**Saída**
- Cronograma: número de réplicas por fatia de tempo

## 4.4 O perfil — a peça mais reaproveitável

```csv
nodes,throughput,power
0,0.0,0.0
1,1757.89,54.78
2,3496.40,109.80
3,5104.39,161.22
4,6661.95,217.61
5,8073.21,273.15
6,9447.75,331.23
7,10747.78,390.73
```

`profiles.go` deriva os **valores marginais** — quanto a réplica `n` acrescenta:

```go
p.MarginalThroughput = p.Throughput - base_throughput
p.MarginalPower = p.Power - base_power
```

| Réplica | Vazão marginal | Potência marginal | Vazão por watt marginal |
|---|---|---|---|
| 1ª | 1.757,9 | 54,8 W | 32,1 |
| 2ª | 1.738,5 | 55,0 W | 31,6 |
| 4ª | 1.557,6 | 56,4 W | 27,6 |
| 7ª | 1.300,0 | 59,5 W | **21,8** |

A 7ª réplica rende **32% menos trabalho por watt** que a 1ª. É o retorno decrescente
medido — exatamente o que o `⌈razão × prontos⌉` do HPA ignora (seção 1.7).

## 4.5 O algoritmo, passo a passo (`ComputeSchedule`)

### Etapa 1 — Pontuar cada par (fatia, réplica)

```go
for i := 0; i < int(jobSpec.DeadLine); i++ {
    for j := int(jobSpec.MinReplicas); j <= max_nodes; j++ {
        value := profile_map[j].MarginalThroughput /
                 (profile_map[j].MarginalPower * s.CarbonStatus.CarbonIntensityPrediction[i])
```

```
pontuação(i, j) = vazão_marginal(j) / (potência_marginal(j) × carbono(i))
                = trabalho extra por grama de CO₂ emitido a mais
```

### Etapa 2 — Ordenar da maior pontuação para a menor

### Etapa 3 — Alocar gulosamente até completar o trabalho

```go
for done < remaining_work {
    for i, item := range mar_cap_carbon_list {
        if item.nodes == jobSpec.MinReplicas {
            schedule[item.time] = int32(item.nodes)       // abre a fatia com o mínimo
            ...
        } else if item.nodes == schedule[item.time]+1 {
            schedule[item.time] = int32(item.nodes)       // acrescenta uma réplica
            ...
    }
    // remove o item usado e recalcula o trabalho previsto
    done = compute_done(schedule, profile_map, float64(s.timeSlot))
}
```

A regra `schedule[time]+1` garante que as réplicas de uma fatia sejam acrescentadas
**em ordem**: a 3ª só entra depois da 2ª.

Se a lista acabar antes de completar o trabalho: `"Deadline too tight"`, erro.

### Etapa 4 — Executar o cronograma

A cada fatia, `ComputeSchedule` avança o índice e `GetReplicas` devolve o número
programado, que é escrito nas réplicas do `MPIJob`. Se o cronograma acabar antes do job,
**cai para o mínimo de réplicas**.

## 4.6 Artigo × código ⚠️

O repositório público **não implementa tudo que o artigo descreve**:

| Aspecto | Artigo | Código público |
|---|---|---|
| Pontuação | `MC_j / c_i` | `MC_j / (ΔP_j × c_i)` — inclui a **potência marginal** |
| Recálculo | quando progresso ou carbono desviam do plano | **não existe**; cai para o mínimo se o cronograma acabar |
| Carbon Profiler | mede o perfil automaticamente | **ausente**; perfis são CSV fixos |
| Carbon Advisor (simulador) | usado na maioria dos resultados | **ausente** |
| Previsão de carbono | serviços comerciais | `predict_carbon_real` devolve o **traço futuro real** (oráculo) |
| Aplicações | ML e MPI | só `MPIJob` do Kubeflow; perfis só de N-body |
| Tempo | fatias de 1 h | fatia simulada de **300 s** (compressão de tempo) |

Duas consequências:

1. **A prova de otimalidade** do artigo assume capacidade marginal decrescente. Com a
   potência marginal no denominador, a condição passa a ser sobre a **razão**, que não é
   garantidamente monótona. No perfil de N-body ela é; em outra aplicação, precisa ser verificada.
2. **Os resultados de robustez a erro de previsão** (30% de erro → 4% de perda) vêm do
   simulador, que não está no repositório. O protótipo em Kubernetes usou previsão perfeita.

Isso não invalida o artigo, mas define o que se pode citar como "implementado" e o que
é "descrito". **Cite o artigo pelas ideias, o código pelo que ele faz.**

## 4.7 Exemplo numérico

Perfil acima, carbono em 3 fatias: `[100, 400, 150]` gCO₂/kWh, mínimo 1, máximo 3.

| Par | Vazão marg. | Pot. marg. (W) | Carbono | Pontuação |
|---|---|---|---|---|
| (0, 1) | 1757,9 | 54,8 | 100 | **0,321** |
| (0, 2) | 1738,5 | 55,0 | 100 | **0,316** |
| (0, 3) | 1608,0 | 51,4 | 100 | **0,313** |
| (2, 1) | 1757,9 | 54,8 | 150 | **0,214** |
| (2, 2) | 1738,5 | 55,0 | 150 | 0,211 |
| (1, 1) | 1757,9 | 54,8 | 400 | 0,080 |

Aloca na ordem: fatia 0 até 3 réplicas, depois fatia 2... e a fatia 1, a mais suja, só
recebe servidores se o trabalho não couber no resto.

## 4.8 O leitor RAPL (`monitoring/rapl.py`)

Relevante porque o pipeline prevê um leitor RAPL próprio (`docs/pipeline.md`, Fase 2.2).
Este é um ponto de partida com licença MIT — **mas tem problemas que precisam ser corrigidos
antes de reaproveitar**.

**O que faz certo**
- Percorre a árvore `/sys/class/powercap/intel-rapl` (funciona também em AMD)
- **Trata o *wraparound***: `if diff < 0: diff = self.max_values[v] + diff`
- Separa domínios e subdomínios

**Problemas encontrados**

| Problema | Trecho | Efeito |
|---|---|---|
| **Soma dupla** | `read_average_power` soma o `package` **e** os subdomínios (`core`, `uncore`) | `core` já está dentro do `package` → **potência total inflada**. No seu Ryzen, o `core` seria contado duas vezes |
| **Falha silenciosa** | `except: print("Static Power"); power = 10` | sem root ou sem RAPL, grava **10 W fictícios** como se fossem medidos |
| **Relógio de parede** | `datetime.now()` para calcular a duração | ajuste do NTP no meio da amostra distorce a potência; usar `time.monotonic()` |
| **Remoção durante iteração** | `dirnames.remove(d)` dentro do `for d in dirnames` | pode pular diretórios; hoje não afeta, mas é frágil |
| **Amostragem por `sleep`** | `time.sleep(time_period)` entre leituras | deriva acumulada ao longo de horas |

**Correção mínima para o projeto:** somar só os domínios de topo (`package-N`, e `dram`
quando for domínio separado), falhar com erro em vez de inventar valor, usar relógio
monotônico e registrar o timestamp UTC junto de cada amostra.

## 4.9 Limitações

| Limitação | Consequência |
|---|---|
| **Só batch com prazo** | não se aplica a serviço web sem "trabalho total" definido |
| **Plano fixo no início** | não reage a demanda nem a desvio (no código público) |
| **Perfil estático** | mudou a aplicação ou o hardware, precisa medir de novo |
| **Custo de troca ignorado** | assume que mudar o número de réplicas é gratuito (nota 5 do artigo) |
| **Sem SLA** | a restrição é o prazo, não a latência |
| **Projeto parado desde 2023** | |

## 4.10 O que a proposta aproveita e o que muda

### Aproveita

- **O perfil `réplicas × vazão × potência`** como formato do modelo de energia `Ê(n)`
  (Fase 3 do pipeline): medir a potência com 1, 2, … N réplicas sob carga
- **A potência marginal**: é ela que diz se vale a pena a próxima réplica
- **O leitor RAPL**, com as correções da seção 4.8
- **O critério "trabalho por carbono marginal"**, adaptado

### Adapta para aplicação interativa

O CarbonScaler pergunta: *"em qual fatia de tempo esta réplica rende mais trabalho por
grama de CO₂?"* — pergunta que só faz sentido quando o trabalho pode ser adiado.

Num serviço web, a demanda não espera. A pergunta vira:

> *"Dada a demanda prevista agora, a próxima réplica reduz o risco de violar o SLA o
> suficiente para justificar a energia e o carbono que ela acrescenta?"*

É exatamente a comparação entre `γ·S(n)` e `α·Ê(n)·(1 + λ·Î(t)) + β·K(Δn⁺)` na função
de custo: acrescentar réplicas enquanto o **ganho marginal de SLA** superar o **custo
marginal de energia e carbono**. O CarbonScaler dá a forma do raciocínio; a proposta
troca "trabalho adiável" por "SLA imediato" e acrescenta o custo de troca que ele ignora.


---

# 5. KubeWatt (University of Groningen)

## 5.1 Referência

| Item | Valor |
|---|---|
| Artigo | PIJNACKER, B.; SETZ, B.; ANDRIKOPOULOS, V. *Container-level Energy Observability in Kubernetes Clusters.* arXiv:2504.10702, 2025 |
| Resumo | `revisao_bibliografica/resumos/03_kubewatt.md` |
| Repositório | `github.com/bjornpijnacker/kubewatt` (Java) |
| Licença | **nenhuma** — pode ser lido e citado; o código **não** pode ser copiado nem modificado |
| Código lido | commit `56fa828a1f86` (12/06/2025) |

O repositório inclui slides de apresentação na **ICT4S 2025**. Verificar se há versão
publicada nos anais antes de citar só o preprint.

> Como não há licença, o projeto **reimplementa a equação** publicada no artigo, que é
> permitido, e **não reaproveita o código**. O código foi lido apenas para entender os detalhes.

| Arquivo | Conteúdo |
|---|---|
| `estimator/ContainerPowerEstimator.java` | **a equação de atribuição** |
| `initializer/BaseInitializer.java` | potência estática com cluster vazio |
| `initializer/BootstrapInitializer.java` | potência estática por regressão |
| `collector/container/KubernetesContainerUtilizationCollector.java` | CPU por container |
| `collector/power/PowerCollector.java` | interface da fonte de potência |

## 5.2 A ideia central

Separar a potência do nó em duas partes e **só distribuir a parte que depende de carga**:

```
potência_nó = estática + dinâmica
potência(container) = dinâmica × CPU(container) / Σ CPU(containers)
```

## 5.3 Entradas e saídas

**Entradas**
- Potência do nó (Redfish/iDRAC)
- CPU de cada container (`metrics.k8s.io`)
- Potência estática do nó (calculada uma vez, na inicialização)
- Lista de pods do plano de controle (expressões regulares)

**Saída**
- Potência em watts por container, exportada para o Prometheus

## 5.4 O algoritmo, passo a passo

### Etapa 1 — Atribuição (`getContainerPowerUsage`)

```java
var staticPower = Math.min(nodeStaticPower.get(node), power);
var dynamicPower = power - staticPower;

// remove pods do plano de controle: já estão na parte estática
utilization = utilization.entrySet().stream()
    .filter(entry -> controlPlanePods.stream().noneMatch(p -> entry.getValue().podName().matches(p)))
    ...

var cpuTotal = utilization.values().stream().mapToDouble(ContainerValue::value).sum();
... cpuTotal == 0 ? 0 : (container.value() / cpuTotal) * dynamicPower
```

Três detalhes do código que o artigo não menciona:

| Detalhe | Efeito |
|---|---|
| `min(estática, medida)` | a dinâmica nunca fica negativa, mesmo com ruído na leitura |
| Plano de controle excluído por nome | o consumo **acima do ocioso** do plano de controle é repartido entre os containers da aplicação |
| `cpuTotal == 0` → todos recebem 0 | a potência dinâmica **desaparece** da conta — há um `TODO` no código reconhecendo isso |

### Etapa 2 — Potência estática, cluster vazio (`BaseInitializer`)

- Verifica que só existem pods do plano de controle; senão, aborta
- Mede a cada **15 s** durante **5 min**
- Estática = **média** das leituras

### Etapa 3 — Potência estática, cluster em uso (`BootstrapInitializer`)

1. Coleta **CPU do nó e potência** a cada 15 s por **30 min**
2. Valida a distribuição: divide a CPU (normalizada pelo número de CPUs) em faixas de
   10% entre 20% e 80%; toda faixa precisa ter ao menos uma fração (`minMult`) das
   amostras da maior. Se falhar, **coleta mais 30 min**
3. **Se o nó tem SMT** (*hyperthreading*), descarta as amostras com CPU acima do número
   de núcleos físicos
4. Regressão **linear** (`PolynomialCurveFitter.create(1)`)
5. Estática = `intercepto + inclinação × CPU média do plano de controle`

```java
if (Config.get().bootstrapInitializer().nodeHasSmt().get(node)) {
    int nCpu = nodeNumCpus.get(node).getNumber().intValue() / 2;
    observations.put(node, observations.get(node).stream().filter(o -> o.getX() <= nCpu).toList());
}
var d1Poly = fitter.fit(observations.get(node));
return d1Poly[0] + cpUtil * d1Poly[1];
```

## 5.5 Artigo × código

| Aspecto | Artigo | Código |
|---|---|---|
| Corte da regressão | "metade inferior da CPU" | **núcleos físicos**, e só se SMT estiver configurado |
| Estática | valor da regressão | intercepto **mais** o consumo do plano de controle |
| Verificação de uniformidade | faixas de 10% | faixas **e** um teste Kolmogorov-Smirnov que só é registrado em log (marcado `!! TEMP`) |
| Verificação de amplitude (mín. < 20%, máx. > 80%) | descrita | **comentada** no código |
| Curva de potência completa | não usada | código comentado: *"parece aproximar muito bem uma relação linear"* |

**O "por que linear" explica a saturação do artigo.** No gráfico da regressão, a
potência satura perto de 470 W. O código mostra o motivo: acima do número de núcleos
**físicos**, ocupar *threads* SMT adicionais acrescenta pouca potência. Abaixo disso a
relação é quase linear. Não é uma curvatura geral — é um **efeito do SMT**.

> **No seu Ryzen 7 3700U (4 núcleos, 8 threads), espere o mesmo:** potência crescendo
> quase linearmente até ~4 threads ocupadas e achatando depois. Isso precisa aparecer
> na calibração da Fase 3.

## 5.6 Limitações

| Limitação | Consequência |
|---|---|
| **Só Redfish** | inutilizável sem iDRAC — é o caso do projeto |
| **Atribuição só por CPU** | memória, disco e rede não entram |
| **Janelas desalinhadas** | potência do Redfish é média de 1 min; CPU do `metrics.k8s.io` tem janela própria |
| **Conservação não garantida** | com CPU total zero, a potência dinâmica some |
| **Muitas chamadas à API** | lista namespaces e lê cada pod individualmente a cada ciclo |
| **Estática fixa** | calculada uma vez; temperatura e envelhecimento não entram |

## 5.7 Como a proposta usa

| Peça | Implementação no projeto |
|---|---|
| Fonte de potência | leitor RAPL (seção 4.8, corrigido), somando só os domínios de topo |
| Estática | modo base: cluster vazio, 5 min a 15 s — **antes de cada sessão** |
| Atribuição | a mesma equação, aplicada na **consolidação dos dados** (Fase 4), não em tempo real |
| CPU por container | cAdvisor, na **mesma janela** da potência |
| Conservação | verificar `Σ containers + estática ≈ total`; tratar `cpuTotal == 0` atribuindo a dinâmica a "sistema" |

---

# 6. Modelo de potência de Fan, Weber e Barroso (Google, 2007)

## 6.1 Referência

| Item | Valor |
|---|---|
| Artigo | FAN, X.; WEBER, W.-D.; BARROSO, L. A. *Power Provisioning for a Warehouse-sized Computer.* ISCA 2007 |
| PDF | static.googleusercontent.com/media/research.google.com/en//archive/power_provisioning.pdf (conferido) |
| Código | não há — é um modelo analítico |

## 6.2 O modelo

A potência **total do sistema** em função da utilização média de CPU `u` (0 a 1):

```
linear:      P(u) = P_ocioso + (P_pico − P_ocioso) · u
não linear:  P(u) = P_ocioso + (P_pico − P_ocioso) · (2u − u^r)
```

- `r` é um **parâmetro de calibração** escolhido para minimizar o erro quadrático
- No artigo, `r = 1,4` para aquela família de máquinas
- **Uma calibração por classe de hardware**

Nas palavras dos autores: *"a calibration parameter r that minimizes the squared error
is chosen (a value of 1.4 in this case). For each class of machines deployed, one set
of calibration experiments is needed."*

## 6.3 Propriedades

- `u = 0` → `P_ocioso`; `u = 1` → `P_pico`
- Com `r > 1`, a curva é **côncava**: fica acima da reta
- **Potência marginal**: `dP/du = (P_pico − P_ocioso) · (2 − r·u^(r−1))` — **cai** conforme a utilização sobe
- `r = 1` recupera o modelo linear

## 6.4 Exemplo numérico

`P_ocioso = 20 W`, `P_pico = 60 W`, `r = 1,4`:

| `u` | Não linear | Linear | Diferença | Potência marginal |
|---|---|---|---|---|
| 0% | 20,0 W | 20,0 W | — | 0,80 W por ponto percentual |
| 25% | 34,3 W | 30,0 W | +14% | 0,48 |
| 50% | 44,8 W | 40,0 W | +12% | 0,38 |
| 75% | 53,3 W | 50,0 W | +7% | 0,30 |
| 100% | 60,0 W | 60,0 W | — | 0,24 |

O primeiro ponto percentual de CPU custa **3,3 vezes** mais potência que o último.

## 6.5 Como foi validado — e o que isso permite afirmar

| Nível | Validação | Resultado |
|---|---|---|
| Máquina individual | medição × modelo, visual (barras de erro) | "razoavelmente preciso" — **sem número** |
| Grupo de centenas de máquinas (PDU) | medido × estimado | **erro < 1%** depois de remover um deslocamento fixo (switches de rede) |

O "< 1%" vale para **agregados grandes**, onde os erros individuais se compensam.
**Para um nó só, não há garantia desse nível de precisão.**

Outros pontos do artigo:

- Mede **potência total do sistema** (na tomada / PDU), **não** RAPL
- Nos servidores de 2007, a potência ociosa **nunca ficava abaixo de 50% do pico**

## 6.6 Limitações

| Limitação | Consequência para o projeto |
|---|---|
| **Um único sinal: CPU** | memória, disco e rede ignorados |
| **Calibrado com potência total** | com RAPL (só processador), `P_ocioso`, `P_pico` e `r` precisam ser **recalibrados** |
| **Hardware de 2007** | DVFS e estados de repouso modernos mudam o formato da curva |
| **Não modela SMT** | não captura o achatamento acima dos núcleos físicos (seção 5.5) |
| **Precisão comprovada só em agregado** | para um nó, o erro precisa ser medido |

## 6.7 Como a proposta usa

Base do modelo de energia `Ê(n)` (Fase 3 do pipeline), **com duas extensões**:

1. **Por partes, com joelho nos núcleos físicos:** um trecho até o número de núcleos
   físicos e outro, mais achatado, para as *threads* SMT
2. **Calibrado com RAPL**, e o erro para **um nó** medido e reportado

---

# Síntese: o que os seis algoritmos revelam juntos

## Uma implicação crítica para o Portão 2

Juntando o modelo de Fan (seção 6) com a atribuição do KubeWatt (seção 5), surge uma
questão que **pode decidir o projeto**:

> **Num único nó, a potência depende da CPU total usada — e a CPU total é determinada
> pela demanda, não pelo número de réplicas.**

Servir 500 req/s com 2 réplicas ou com 6 exige, em princípio, o mesmo trabalho de CPU.
Se `u` não muda, `P(u)` não muda. **O número de réplicas, por si só, quase não mexeria
no consumo de um nó.**

O que pode fazer diferença, em sentidos opostos:

| Efeito | Direção | Tamanho esperado |
|---|---|---|
| Sobrecarga por réplica (processos, sondas de saúde, *runtime*) | mais réplicas → **mais** energia | pequeno |
| *Cold start* (iniciar pods) | escalar mais → **mais** energia | pequeno, mas repetido |
| Espalhamento entre núcleos: mais processos mantêm mais núcleos acordados, sem repouso profundo | mais réplicas → **mais** energia | depende do hardware e do governor |
| Contenção e trocas de contexto com poucas réplicas saturadas | menos réplicas → **mais** energia por requisição | depende da carga |

Nos artigos lidos, a economia vem de **desligar ou esvaziar máquinas inteiras**: o
perfil do CarbonScaler mede **servidores** (54,8 W cada), não pods. Num nó fixo, esse
mecanismo não existe.

**Não é uma conclusão — é uma hipótese a testar primeiro.** O piloto do Portão 2
(2 × 6 réplicas, carga fixa) é exatamente o experimento que responde. Se a diferença
for desprezível, as saídas são:

1. **Mais de um nó físico**, com a escala de pods liberando nós que entram em repouso
   ou são desligados (consolidação) — é onde está a economia grande
2. **Focar nos efeitos de um nó**: sobrecarga por réplica, *cold start* e espalhamento
   entre núcleos — economia menor, mas mensurável e honesta
3. **Medir a sobrecarga por réplica isoladamente** antes de tudo: `P(n réplicas ociosas) − P(0)`

Por isso, a Fase 3 do pipeline passa a incluir a medição da **sobrecarga por réplica**.

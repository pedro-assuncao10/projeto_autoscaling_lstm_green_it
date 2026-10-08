# Decisão 002 — Escala em dois níveis: pods e máquinas

**Data:** 17/09/2026
**Status:** aceita

---

## Contexto

A leitura dos algoritmos (`docs/algoritmos.md`, "Síntese") mostrou que, **num único nó**,
a potência depende da CPU total usada, e a CPU total é ditada pela demanda, não pelo
número de réplicas. A economia grande de energia vem de **esvaziar e desligar máquinas
inteiras** — o que só existe com mais de um nó.

## Decisão

O projeto trata **os dois níveis**, de forma coordenada:

| Nível | O que escala | Ritmo | Economia esperada |
|---|---|---|---|
| **Pods** | número de réplicas | segundos (ciclo de 15 s) | pequena: sobrecarga por réplica, *cold start*, núcleos ociosos |
| **Máquinas** | número de nós ligados | minutos | grande: a máquina inteira deixa de consumir |

A mesma previsão de demanda (LSTM) alimenta os dois, com **horizontes diferentes**.

## Por que os dois

- Só pods: economia pequena, mas a decisão é rápida e barata
- Só máquinas: economia grande, mas ligar uma máquina leva de segundos a minutos —
  sem previsão, o SLA quebra enquanto ela acorda
- Juntos: os pods reagem rápido; as máquinas acompanham a tendência. **É onde a previsão
  mais vale**, porque o tempo para acordar um nó é muito maior que o de subir um pod

## Peças reaproveitadas

| Função | Ferramenta | Observação |
|---|---|---|
| Juntar pods em poucos nós | kube-scheduler com pontuação **`MostAllocated`** | configuração, sem código |
| Reagrupar depois de reduzir pods | **descheduler**, estratégia `HighNodeUtilization` | exige `MostAllocated`, segundo a documentação |
| Decidir quando esvaziar/ligar nós | **Cluster Autoscaler** com provedor **`externalgrpc`** | permite plugar máquinas físicas via gRPC, sem *fork* |
| Desligar e ligar a máquina | suspensão (ACPI S3) + **Wake-on-LAN** | a ser verificado no hardware do lab |

Parâmetros padrão do Cluster Autoscaler (baseline reativo de nós):

| Parâmetro | Padrão |
|---|---|
| `scale-down-utilization-threshold` | **0,5** — calculado sobre **requests**, não uso real |
| `scale-down-unneeded-time` | **10 min** |
| `scale-down-delay-after-add` | **10 min** |

## Requisitos de infraestrutura

- **No mínimo 2 máquinas físicas** no laboratório como sistema sob teste, mais o notebook como cliente
- Nó do plano de controle **sempre ligado** (não pode ser desligado)
- Ao menos um nó de trabalho que possa ser **suspenso e acordado remotamente**:
  - BIOS com Wake-on-LAN habilitado e rede **cabeada**
  - Suspensão para RAM (S3) funcionando: `systemctl suspend`
  - Verificar tempo de acordar até o nó ficar `Ready` no Kubernetes

## Consequências para a medição

> ⚠️ **A economia de desligar máquinas medida por RAPL é um limite inferior.**

O RAPL só enxerga o processador. Quando uma máquina é suspensa, some também o consumo
de placa-mãe, disco, ventoinhas e fonte — que o RAPL nunca mediu. E uma máquina suspensa
**não tem leitura RAPL**: seu consumo em repouso (alguns watts) não é mensurável por
software.

Reportar como:

- energia de nós ativos: **medida** (RAPL de cada nó)
- energia de nós suspensos: **zero no RAPL**, declarado explicitamente
- a economia total: **limite inferior** da economia real

## Riscos

| Risco | Mitigação |
|---|---|
| Hardware do lab sem Wake-on-LAN ou S3 | testar antes; alternativa: esvaziar o nó sem desligar (economia menor, mensurável) |
| Tempo para acordar maior que o horizonte de previsão | medir o tempo real; ajustar o horizonte do nível de nós |
| Oscilação: ligar e desligar máquinas repetidamente | histerese e custo de troca de nó na política |
| Plano de controle concentrado num nó | esse nó nunca é desligado; a economia vem dos nós de trabalho |

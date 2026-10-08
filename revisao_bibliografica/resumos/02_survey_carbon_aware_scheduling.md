# A Survey on Task Scheduling in Carbon-Aware Container Orchestration (Yang et al., 2025)

**Referência:** YANG, J.; SAAD, Z.; WU, J.; NIU, X.; LEUNG, H.; DREW, S. *A Survey on Task Scheduling in Carbon-Aware Container Orchestration.* arXiv:2508.05949, ago. 2025.

**Instituições:** University of Calgary; Wuhan University
**Tipo:** pesquisa secundária (revisão de literatura; não propõe nem mede nada)

> ⚠️ **Preprint, sem revisão por pares.** O cabeçalho tem formato ACM, mas o DOI é
> um marcador de posição. Citar pelo arXiv e usar como **mapa** da literatura, não como
> autoridade. Sempre citar o artigo original, não a descrição do survey.

---

## Ideia central

Revisão de 54 trabalhos sobre como tornar o **escalonamento do Kubernetes** mais
eficiente em energia e carbono, organizada numa taxonomia de dois eixos.

## Scheduling × autoscaling — não confundir

| Termo | Pergunta | Exemplo |
|---|---|---|
| *Scheduling* (tema do survey) | **Em qual máquina (nó)** cada pod roda? | kube-scheduler, EETS, PEAKS |
| *Autoscaling* (tema da dissertação) | **Quantas réplicas** existem? | HPA, KEDA, CarbonScaler |

Um pod **não** é uma máquina: uma máquina roda vários pods. "Autoscaling" nem está
entre as palavras-chave de busca do survey, então esses trabalhos aparecem dispersos.

## Metodologia

| Etapa | Detalhe |
|---|---|
| Protocolo | PRISMA (preferido a MOOSE, Cochrane, ROBIS, GRADE) |
| Bases | ACM DL, IEEE Xplore, SpringerLink; Google Scholar e Connected Papers |
| Palavras-chave | "virtualization", "Kubernetes scheduling", "carbon intensity", "federated learning" |
| Literatura cinzenta | Google, Microsoft, Green Software Foundation |
| Inclusão | Alto impacto, tema aderente, metodologia documentada |
| Exclusão | Fora do escopo, fonte inverificável, desatualizado (salvo seminal) |
| Resultado | 54 trabalhos |

**Crítica:** o diagrama PRISMA não informa quantos artigos saíram em cada etapa, só o
total final. Assim a revisão não é reprodutível.

## Taxonomia

Eixos: **como otimiza** (hardware × software) e **objetivo** (energia × carbono).

| | Eficiência energética | Consciência de carbono |
|---|---|---|
| **Hardware** | PEAKS, NPAKS, HEATS; gestão de custo de data center | KCSS (multicritério); CarbonScaler, Google CICS, Caspian (IBM), SCALE (ING) |
| **Software** | RL/DRL (RLKube, EETS, HunterPlus); heurísticas (GreenPod, FOA-Energy); **medição (Kepler, KubeWatt)** | DRL (Smart-Kube, GreenFlow); serverless (CASA, KEDA, GreenCourier); prioridade por carbono (CASPER, PCAPS) |

**Atenção às categorias:**
- **EETS, HunterPlus, PEAKS** → **escalonadores** (decidem onde rodar)
- **Kepler, KubeWatt** → **medidores** (só estimam consumo por container)

A dissertação cairia em **software × (energia + carbono)**, mas a taxonomia não tem
categoria para autoscaling.

## Pontos relevantes

### 1. Medição por container pode errar (seção 7.1.3)

> ⚠️ **O survey descreve este resultado de forma errada.** Conferido no original
> (resumo 03): os **66,4 W de RMSE são no nível do nó inteiro**, não por container, e
> vêm principalmente do **atraso** entre as fontes (o iDRAC atualiza a cada 1 min). Na
> energia total do teste, o erro do Kepler é **menor que 1%**.

Os problemas reais do Kepler **por container** são de atribuição, não de total:

- Atribui ~100 W a containers ociosos que nem estão rodando (~6,25 W cada)
- Após remover pods, joga potência dinâmica em "system_processes"

**Proposta do KubeWatt:** separar potência **estática** (ociosa) de **dinâmica** e
distribuir só a dinâmica, proporcional ao uso de CPU. Acerta a estática com < 0,2% de erro.

**Scaphandre:** o survey não o avaliou. Quem compara Kepler e Scaphandre é
Centofanti et al. (2024) — ver resumo 03.

**Implicação:** métrica principal no **nível do nó**; atribuição por container tratada
como estimativa e declarada como tal.

### 2. HPA já avaliado por energia e SLA

**Jawaddi et al.** (2025, *J. Grid Computing*) modelam o HPA como processo de decisão
de Markov e usam verificação probabilística de modelos. Combinar latência com energia
dá o melhor resultado. **Diferença:** modelo formal, sem medição física, sem previsão.

### 3. Autoscaling com carbono já existe na indústria

**Carbon-Aware KEDA Operator:** limita o `MaxReplicaCount` pela intensidade de carbono
(WattTime, Electricity Maps). **Diferença:** reativo, teto rígido, sem previsão, pode
violar SLA. → **Candidato a segunda baseline.**

### 4. Justificativa para a LSTM

- Seção 3.5, limitações do escalonador padrão: *"reativo, não preditivo"*
- Seção 8.3: *"a predição de carga continua pouco desenvolvida e é vital para o
  escalonamento eficiente sob demanda dinâmica"*

### 5. Métrica padronizada: SCI

*Software Carbon Intensity* (Green Software Foundation):

    SCI = (E × I + M) / R

E = energia; I = intensidade de carbono; M = emissões embutidas; R = unidade funcional.
Com R = requisição → **gCO₂e por requisição**, compatível com joules por requisição.

### 6. Dados de contexto

- Data centers dos EUA: 176 TWh em 2023 (4,4%), até 580 TWh (12%) em 2028
- Irlanda: data centers podem chegar a 32% da eletricidade nacional em 2026

## A lacuna, refinada

Elementos que **já existem** isoladamente:

| Trabalho | O que já faz |
|---|---|
| Kreutz, Wiesner, Vitali (2025) | Escala horizontal de microsserviços sob orçamento horário de carbono, aplicação interativa |
| CASPER (Souza et al., 2023) | Provisionamento consciente de carbono para serviços web com restrição de latência |
| CASA (Qi et al., 2024) | Cold start × carbono × SLO, em serverless |

**Não aparece em nenhum dos 54 trabalhos:** *Transfer Learning*.

**Contribuição defensável = a combinação:** autoscaling **preditivo** para serviço web
de longa duração + energia **medida fisicamente** com atribuição validada + *cold start*
como custo energético + custo do pipeline de ML reduzido por *Transfer Learning*.

## Problemas de qualidade

- Referências trocadas: orçamento de carbono citado como [99] no texto, é o [121];
  HunterPlus aparece como [125] e [102]; DL2 duplicado
- Descreve o CarbonScaler como ajuste de "taxa de utilização", quando ajusta o
  **número** de servidores
- Descrições superficiais, percentuais sem contexto
- **Reporta o RMSE de 66,4 W do Kepler como erro por container**, quando no original é o
  erro do nó inteiro, causado por latência (ver resumo 03)

## O que reaproveitar

1. Taxonomia de dois eixos para posicionar o trabalho no Capítulo III
2. Protocolo PRISMA — **reportando os números de cada etapa** e incluindo "autoscaling"
   e "horizontal pod autoscaler" nas palavras-chave
3. Modelo estático/dinâmico do KubeWatt para atribuir energia
4. SCI como métrica padronizada
5. Carbon-Aware KEDA como segunda baseline

## Próximas leituras (prioridade)

1. **KubeWatt** — Pijnacker, Setz, Andrikopoulos. arXiv:2504.10702, 2025.
   https://arxiv.org/abs/2504.10702 — *define a validade da medição*
2. **Jawaddi et al.** — *Analyzing Energy-Efficient and Kubernetes-Based Autoscaling of
   Microservices Using Probabilistic Model Checking*, J. Grid Computing, 2025
3. **CASA** — Qi et al., IGSC 2024
4. **Kreutz, Wiesner, Vitali** — arXiv:2506.21422, 2025
5. **CASPER** — Souza et al., IGSC 2023
6. **Carrión** — *Kubernetes Scheduling: Taxonomy, Ongoing Issues and Challenges*,
   ACM Computing Surveys, 2022 (survey revisado por pares)

# Catálogo de bases de dados

Bases públicas pesquisadas para o projeto: **o que cada uma traz** e para que serve.
Levantamento feito em 08/10/2026. Bases marcadas como "não baixada" foram só
documentadas, a partir das páginas oficiais.

## A pergunta que guia a escolha

Para comparar com o autoscaler do Kubernetes (HPA, que escala por **CPU**) e treinar a
LSTM com **requisições**, o ideal é uma base que traga, no mesmo intervalo de tempo:

1. **requisições** (a demanda que a LSTM prevê)
2. **CPU** (o que o HPA usa para decidir)
3. idealmente, **quantos pods/instâncias** estavam ativos

## Resumo

| Base | Requisições | CPU | Pods/instâncias | Granularidade | Duração | Situação |
|---|:-:|:-:|:-:|---|---|---|
| NASA-HTTP (1995) | ✅ | ❌ | ❌ | por requisição → agregamos por minuto | 62 dias | **em uso** |
| Copa do Mundo (1998) | ✅ | ❌ | ❌ | por requisição → agregamos por minuto | ~88 dias | **em uso** |
| Wikipédia (2015–2026) | ✅ | ❌ | ❌ | 1 hora | 11,3 anos | baixada, reservada |
| **Huawei Private 2023** | ✅ por segundo | ✅ por minuto | ✅ | 1 s / 1 min | 234 dias (141 com dados) | não baixada — **a mais completa** |
| Huawei Public 2023 | ✅ por minuto | ❌ | ❌ | 1 min | 26 dias | não baixada |
| Huawei Cold Start 2025 | ✅ | ? | ? | — | 31 dias | não baixada |
| Alibaba Microservices 2022 | ✅ normalizada (0–1) | ✅ normalizada (0–1) | ✅ (por container) | 1 min | 13 dias | não baixada |
| Azure Functions 2019 | ✅ por minuto | ❌ | ❌ | 1 min | 14 dias | não baixada |
| Azure VM V1 (2017) / V2 (2019) | ❌ | ✅ | ❌ | 5 min | ~30 dias | não baixada |
| Google Cluster 2019 (Borg) | ❌ | ✅ | ❌ | 5 min | 31 dias (maio/2019) | não baixada |
| Bitbrains GWA-T-12 | ❌ | ✅ | ❌ | 5 min | 1 a 3 meses | não baixada |

**Conclusão:** só **Huawei Private 2023** e **Alibaba 2022** trazem requisições e CPU
juntas. Na Alibaba os valores são **normalizados** (não dá para saber quantas
requisições reais eram). A Huawei Private é a única com valores reais de requisições,
CPU **e** número de instâncias, ou seja, a demanda, o recurso e a decisão do autoscaler.

---

## Bases em uso

Detalhes do pré-processamento em [../pre_processamento/](../pre_processamento/).

### NASA-HTTP (1995)
- **O que traz:** um registro por acesso ao site do Kennedy Space Center: endereço de
  quem acessou, data e hora, página pedida, código de resposta (200, 404…) e tamanho da
  resposta em bytes
- **Não traz:** CPU, memória, nada sobre o servidor
- **Fonte:** Internet Traffic Archive — `ita.ee.lbl.gov/html/contrib/NASA-HTTP.html`

### Copa do Mundo FIFA (1998)
- **O que traz:** um registro por acesso ao site oficial da Copa: horário, cliente,
  objeto pedido, tamanho em bytes, método HTTP, código de resposta, tipo de arquivo e
  **qual dos servidores atendeu**
- **Não traz:** CPU, memória
- **Fonte:** Internet Traffic Archive — `ita.ee.lbl.gov/html/contrib/WorldCup.html`

### Wikipédia — Pageviews (2015–2026)
- **O que traz:** total de páginas vistas por hora (humanos + robôs, ou só humanos)
- **Não traz:** CPU, minuto a minuto
- **Fonte:** API Wikimedia Pageviews — `wikimedia.org/api/rest_v1/`

---

## Bases com requisições **e** CPU

### Huawei Cloud Private Functions Trace 2023 ⭐
- **O que é:** funções *serverless* da plataforma interna da Huawei Cloud
- **O que traz, por função:**

  | Métrica | Granularidade | Unidade |
  |---|---|---|
  | Requisições | **por segundo** | contagem |
  | Atraso da função (tempo de execução) | por segundo | ms |
  | Atraso da plataforma | por segundo | ms |
  | Uso de CPU | por minuto | % |
  | Uso de memória | por minuto | % |
  | Limite de CPU | por minuto | núcleos (normalizado) |
  | Limite de memória | por minuto | MB |
  | **Instâncias** (equivalente a pods) | — | contagem |

- **Tamanho:** 200 funções, período de 234 dias, **141 dias com dados**
- **Por que interessa:** é a única base encontrada com **demanda (requisições), recurso
  (CPU) e decisão de escala (instâncias)** juntos, com valores reais. Permite medir a
  relação requisições × CPU e comparar a LSTM com o que a plataforma realmente fez. A
  duração (vários meses) também permite estudar padrões semanais e mensais
- **Cuidado:** é *serverless* (funções), não aplicação web em Kubernetes; a lógica de
  escala é parecida (instâncias sob demanda), mas precisa ser declarada
- **Licença:** CC BY 4.0
- **Artigo:** JOOSEN, A. et al. *How Does It Function? Characterizing Long-term Trends
  in Production Serverless Workloads.* ACM SoCC 2023. arXiv:2312.10127
- **Fonte:** `github.com/sir-lab/data-release`

### Alibaba Cluster Trace — Microservices v2022
- **O que é:** microsserviços em produção na Alibaba, em mais de 10 mil servidores
- **O que traz (tabelas, a cada 60 s):**

  | Tabela | Colunas principais |
  |---|---|
  | `Node` | nó, uso de CPU, uso de memória |
  | `MSResource` | microsserviço, container, nó, **uso de CPU**, uso de memória |
  | `MSRTMCR` | microsserviço, container, **taxa de chamadas** (MCR) por tipo de comunicação, tempo de resposta |
  | `MSCallGraph` | quem chamou quem, em cada requisição, com tempo de resposta |

- **Tamanho:** 13 dias, ~28 mil microsserviços, ~470 mil containers, **~2 TB compactados**
- **Limitação importante:** CPU e taxa de chamadas foram **normalizadas** (0 a 1) pela
  Alibaba. Dá para ver a forma da série, mas **não quantas requisições reais** chegavam
- **Fonte:** `github.com/alibaba/clusterdata/tree/master/cluster-trace-microservices-v2022`
- Existe também a v2021, com só 12 horas

---

## Bases só com requisições

### Huawei Cloud Public Functions Trace 2023
- **O que traz:** requisições **por minuto** por função, custo de *cold start*, tamanho
  do pacote, linguagem
- **Tamanho:** 5.019 funções, 26 dias seguidos
- **Licença / fonte:** CC BY 4.0 — `github.com/sir-lab/data-release`

### Huawei Public Cold Start Traces 2025
- **O que traz:** 85 bilhões de requisições e eventos de *cold start* em 5 regiões, com
  19 métricas por função (lista não verificada)
- **Duração:** 31 dias
- **Artigo:** *Serverless Cold Starts and Where to Find Them*, EuroSys 2025
- **Licença / fonte:** CC BY 4.0 — `github.com/sir-lab/data-release`
- **Interesse:** o *cold start* é um custo energético que a proposta quer modelar

### Azure Functions Dataset 2019
- **O que traz:** invocações **por minuto** de cada função; distribuição (não série) do
  tempo de execução por função e da memória por aplicação
- **Duração:** 14 dias (julho/2019)
- **Fonte:** `github.com/Azure/AzurePublicDataset` — licença CC BY 4.0

---

## Bases só com CPU (sem requisições)

Úteis para estudar previsão de uso de máquinas, mas **não** para prever demanda de
uma aplicação web.

### Azure VM Traces V1 (2017) e V2 (2019)
- **O que traz:** uso de CPU de máquinas virtuais (mínimo, média, máximo) a cada 5 min;
  tamanho e tempo de vida de cada VM
- **Tamanho:** ~2 milhões (V1) e ~2,6 milhões (V2) de VMs
- **Fonte:** `github.com/Azure/AzurePublicDataset` — licença CC BY 4.0

### Google Cluster Workload Traces 2019 (Borg)
- **O que traz:** uso de CPU e memória das tarefas a cada 5 min (com histogramas),
  eventos de criação e término, reservas de recursos
- **Tamanho:** 8 clusters, maio/2019; distribuído pelo BigQuery
- **Fonte:** `github.com/google/cluster-data`

### Bitbrains GWA-T-12
- **O que traz:** CPU, memória, disco e rede de 1.750 VMs, a cada 5 min
- **Partes:** `fastStorage` (1.250 VMs) e `Rnd` (500 VMs)
- **Fonte:** Grid Workloads Archive — `gwa.ewi.tudelft.nl/datasets/gwa-t-12-bitbrains`

---

## Recomendação

| Uso | Base |
|---|---|
| Reproduzir os artigos (previsão de 10 min, número de pods) | **NASA e Copa** (em uso) |
| Estudar a relação requisições × CPU × instâncias com dados reais | **Huawei Private 2023** |
| Padrões longos (meses, anos) | Wikipédia (1 h) ou Huawei Private (141 dias) |
| Base própria com requisições + CPU + energia | **gerada na bancada**: k6 reproduzindo NASA/Copa no cluster |

## Pontos a confirmar antes de baixar qualquer uma

- Huawei Private: tamanho em disco, formato dos arquivos, se as instâncias vêm por minuto
- Huawei Cold Start 2025: lista exata das 19 métricas
- Alibaba: se a normalização é por microsserviço ou global

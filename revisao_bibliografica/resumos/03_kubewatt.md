# KubeWatt (Pijnacker, Setz e Andrikopoulos, 2025)

**Referência:** PIJNACKER, B.; SETZ, B.; ANDRIKOPOULOS, V. *Container-level Energy Observability in Kubernetes Clusters.* arXiv:2504.10702, abr. 2025.

**Instituição:** University of Groningen (Holanda)
**Tipo:** pesquisa primária (avalia uma ferramenta e propõe outra)
**Status:** preprint, 11 páginas
**Código:** https://github.com/bjornpijnacker/kubewatt (Java)
**Dados e scripts:** https://doi.org/10.5281/zenodo.14332659

---

## Correção sobre o survey (resumo 02)

O survey diz que o Kepler tem **66,4 W de erro por container**. **Está errado.**

- Os 66,4 W de RMSE são do **nó inteiro** (total do Kepler × total do iDRAC)
- A causa é principalmente **atraso**: o iDRAC atualiza a cada 1 minuto
- Na **energia total** do teste, o erro do Kepler é **< 1%**

O problema do Kepler não é o total, é **a divisão entre containers**.

## Ideia central

Avaliar se o Kepler (ferramenta da CNCF) atribui energia corretamente a cada container.
Como não atribui, propõem o KubeWatt.

## Perguntas de pesquisa

- **RQ1:** Quão bem o Kepler atribui consumo a containers num nó Kubernetes?
- **RQ2:** Quão precisa é a potência estática no modo de inicialização base?
- **RQ3:** E no modo bootstrap?
- **RQ4:** Quão bem o KubeWatt atribui consumo a containers?

## Montagem experimental

| Papel | Máquina |
|---|---|
| Sistema sob teste (SUT) | Dell PowerEdge R640, 2× Xeon Gold 6226R (32 núcleos / 64 threads), 96 GB, Fedora Server 40 |
| Cliente (TC) | Lenovo ThinkCentre M910q, i3-6100T, 8 GB — roda **Prometheus e Grafana** |

- **Prometheus fora do SUT** *"para que o processamento de dados não afete o consumo
  do sistema sob teste"* → precedente para a arquitetura da dissertação
- **Referência:** iDRAC9 via Redfish, **conferido com medidor de tomada externo**
- Cluster de **um nó** (RKE 1.5.8), pods desnecessários removidos
- **Kepler 0.7.2** — versões mais novas têm bug de valores aleatórios incorretos
  (issue #1344); plataforma via Redfish, componentes via RAPL

| Fonte | Métrica |
|---|---|
| iDRAC | `power_control_avg_consumed_watts` (média de 1 min) |
| cAdvisor | `container_cpu_usage_seconds_total` |
| Kepler | `container_joules_total`, `container_cpu_instructions_total` |

## Experimentos com o Kepler

**Teste 1 — carga simples:** `stress-ng --cpu 32 --timeout 5m`, pausa de 5 min,
3 repetições, com **16 containers ociosos** (que não deveriam receber energia).

**Teste 2 — remoção de pods:** 64 containers ociosos + carga de 8 CPUs; após 2 min,
apaga os ociosos. 4 repetições.

### Resultados

| Achado | Detalhe |
|---|---|
| Total do nó | RMSE 66,4 W (latência); energia total < 1% de erro |
| Containers ociosos | ~**100 W** atribuídos ao namespace ocioso (~6,25 W cada), sem estarem rodando |
| Pico falso | Ao fim da carga, porque o iDRAC atrasa até 1 min em relação à CPU |
| Remoção de pods | Potência dinâmica migra indevidamente para "system_processes" |

**Resposta à RQ1:** o Kepler **não produz medida confiável por container**. Os erros
parecem ser do próprio modelo de alocação.

## O KubeWatt

### Modelo

Divide a potência do nó em:

- **Estática:** custo de estar ligado, **incluindo o plano de controle do Kubernetes**.
  Reportada como um número único, não distribuída.
- **Dinâmica:** total − estática. Distribuída pelo uso de CPU:

      potência(container) = potência_dinâmica(nó) × CPU(container) / Σ CPU(containers)

Container parado → CPU zero → potência zero.

Detalhe: usa a soma da CPU **dos containers**, não a CPU do nó (que inclui processos do
sistema já contados na parte estática).

### Modos de operação

| Modo | Como funciona | Quando usar |
|---|---|---|
| **Base** | Cluster vazio; mede a cada 15 s por 5 min; média | Preferido |
| **Bootstrap** | Cluster em uso; coleta 30 min a cada 15 s; buckets de 10% entre 20% e 80% de CPU; regressão linear **só abaixo de 50% de CPU** | Cluster que não pode ser esvaziado |
| **Estimador** | Usa a estática e exporta potência por container para o Prometheus | Operação normal |

Componentes: `PowerCollector` (interface; só existe `RedfishPowerCollector`) e
`MetricsCollector` (API `metrics.k8s.io`). Instalação via Helm.

## Resultados do KubeWatt

| RQ | Resultado |
|---|---|
| RQ2 (base) | 6 testes entre 198,75 e 199,15 W; real 199,1 W → **erro < 0,2%** |
| RQ3 (bootstrap) | 198,44 / 199,58 / 199,41 W → dentro de **0,7 W**; R² de 0,88 a 0,92; levou **3,5 h, 4 h e 13 h** |
| RQ4 (containers) | Carga recebe a potência esperada; ociosos recebem zero; **sem número de erro por container**, só gráficos |

Observação na regressão: a potência sobe com a CPU e depois **satura** perto de 470 W.
O consumo **não é linear** em toda a faixa.

## Limitações declaradas

- Um único servidor
- Só carga artificial (`stress-ng`)
- Só funciona com iDRAC/Redfish; **em nuvem pública teria que usar RAPL — não testado**
- Não conseguiram treinar modelo próprio no Kepler (documentação insuficiente)

## Relevância para a dissertação

1. **Precedente da arquitetura de duas máquinas** com Prometheus fora do servidor.
2. **Separar estática de dinâmica** é o que permite medir a economia do autoscaler, que só age na dinâmica.
3. **Latência de medição:** o HPA decide a cada 15 s; fonte de 1 min é lenta demais. RAPL atualiza em milissegundos.
4. **`Ê(n)` não pode ser linear:** o consumo satura.
5. **Contribuição técnica:** implementar `PowerCollector` para RAPL — trabalho futuro dos
   próprios autores. Ver `docs/decisoes/001_medicao_energetica_por_software.md`.
6. **Sobre o Scaphandre:** o artigo diz que ele e o Kepler dão resultados parecidos, mas
   **nenhum foi validado** contra medição real.

## O que reaproveitar

1. Os dois testes (containers ociosos; remoção de pods) como **validação da atribuição**
2. O modelo de alocação estático/dinâmico
3. O modo base para medir a potência estática antes de cada sessão
4. O pacote de replicação (Zenodo) como modelo de reprodutibilidade
5. Evitar Kepler > 0.7.2 se for usá-lo como comparação

## Próximas leituras

1. **Centofanti et al.** — *Impact of power consumption in containerized clouds: A comprehensive analysis of open-source power measurement tools*, Computer Networks, v. 245, 2024 — **compara Kepler, Scaphandre e s-tui**
2. **Dinga et al.** — ICSOC 2023 — ferramentas de monitoramento aumentam o consumo em **1,47% a 12,86%**
3. **Santos et al.** — *How does Docker affect energy consumption?*, J. Systems and Software, v. 146, 2018
4. **Kistowski et al.** — ICPE 2015 — relação CPU × consumo em cargas CPU-intensivas
5. **Fieni et al.** — *SmartWatts*, CCGrid 2020

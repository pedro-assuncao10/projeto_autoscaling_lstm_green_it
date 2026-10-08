# Compilado — Autoscaling preditivo em Kubernetes com redes neurais

Estado da arte da base do projeto. Os capítulos de **sustentabilidade** e **Transfer
Learning** são a parte original; esta é a fundação que precisa estar sólida primeiro.

Fonte: os seis artigos em `artigos relacionados/`, lidos na íntegra.

---

## 1. Os seis artigos

| # | Trabalho | Veículo / ano | O que faz |
|---|---|---|---|
| A | **Guruge & Priyadarshana** — *Time series forecasting-based Kubernetes autoscaling using Facebook Prophet and LSTM* | Frontiers in Computer Science, 2025 | Híbrido Prophet + LSTM prevendo requisições HTTP; laço MAPE |
| B | **Beshley et al.** — *AI-Based Proactive Autoscaling Technique for Web Applications in Kubernetes* | IEEE TCSET, 2026 | Operador Kubernetes com CRD; híbrido Holt–Winters + LSTM com seleção automática de modelo |
| C | **Veeck, Barbosa & Dias** — *Reagir ou Antecipar? Uma Comparação entre HPA e ML* | **SBrT 2025** (UFPE) | GRU prevendo CPU para instanciar UPFs em 5G; compara com HPA |
| D | **Augustyn, Wyciślik & Sojka** — *Tuning a Kubernetes HPA for Meeting Performance and Load Demands* | Applied Sciences, 2024 | Calcula o `maxReplicas` ótimo por máxima entropia; **não usa ML** |
| E | **Machiraju, Kumar & Sharma** — *ML-Based Autoscaling for Elastic Cloud Applications* | Math. Comput. Appl., 2026 | **Revisão sistemática** de 60 estudos (2015–2025), com taxonomia e lacunas |
| F | **Aggarwal** — *Auto-Scaling Techniques for Container Workloads in Kubernetes Clusters* | ASRJETS, 2025 | Estudo comparativo descritivo: HPA, VPA, CA, KEDA, Karpenter, preditivo |

> ⚠️ **Sobre o F:** o veículo (ASRJETS) tem baixa seletividade e o artigo é descritivo,
> sem experimento. Use como leitura de contexto, **não como referência de autoridade**.
> O E (revisão sistemática) cumpre esse papel com muito mais força.

---

## 2. A pergunta central: de onde vêm os dados

É aqui que está o padrão mais útil. **Quase ninguém coleta dados de produção própria.**

| Trabalho | Fonte dos dados | Granularidade | Divisão |
|---|---|---|---|
| A | **NASA-HTTP (1995)** e **FIFA World Cup (1998)** — traços públicos | agregado **por minuto** | 70/30, **preservando a ordem temporal** |
| B | Série pública de requisições HTTP por hora, 5 semanas | horária → refinada para minuto | 4 semanas treino / 1 semana teste |
| C | **Gerados na própria bancada**: vídeo transmitido via Flask, 5 e 10 usuários simulados, 30 min por teste | — | treino e validação com execuções distintas |
| D | Logs de um sistema médico real na Polônia | por intervalo de pico | — |
| E | Levanta a prática do campo: RUBiS, DVD Store, SPECweb, DeathStarBench, TrainTicket, logs da Wikipédia | — | — |

**Os dois traços canônicos do campo:**

- **NASA-HTTP (1995)** — 3.461.612 requisições, 2 meses, padrão regular
- **FIFA World Cup (1998)** — 1.352.804.107 requisições, 30/04 a 26/07/1998, **com anomalias muito mais fortes**

Ambos estão no *Internet Traffic Archive* e são de livre acesso. O trabalho A os
pré-processa agregando os logs **por minuto** para obter a taxa de requisições. Ou seja:
**a variável alvo do campo é requisições por segundo/minuto**, não CPU — exatamente a
escolha que o projeto já tinha feito.

> 💡 **Consequência direta para a dissertação.** O projeto não precisa de dados de
> produção próprios para ter base real. O padrão do campo é: **treinar sobre traços
> públicos reais** e **reproduzi-los na bancada com um gerador de carga**. Isso resolve
> a fragilidade do dataset puramente sintético sem depender de convênio nenhum.

**O caso B é um precedente valioso:** como só tinha dados horários e precisava de
granularidade de minuto, eles **distribuíram as requisições uniformemente dentro de cada
hora e acrescentaram pequenas flutuações**. É exatamente a geração sintética a partir de
um perfil real — e foi aceito em veículo IEEE.

---

## 3. O que é prática padrão (a receita do campo)

### Previsão

| Item | Padrão |
|---|---|
| Alvo | **taxa de requisições** (às vezes CPU) |
| Janela de entrada (*look-back*) | de 10 passos (C) a 168 = uma semana (B) |
| Normalização | MinMax 0–1 ou StandardScaler |
| Divisão | **temporal**, nunca aleatória |
| Busca de hiperparâmetros | Optuna (C) ou busca em grade (A) |
| Comparação obrigatória | ARIMA, Holt–Winters, LSTM, **Bi-LSTM**, GRU e híbridos |
| Métricas | MSE, RMSE, MAE, MAPE, R² e **tempo de predição** |

### Controle

| Item | Padrão |
|---|---|
| Laço | **MAPE-K** (Monitor–Analyze–Plan–Execute) |
| Coleta | Prometheus + metrics-server |
| Atuação | API do Kubernetes, ajustando réplicas |
| Integração | script externo (A, C) ou **Operador com CRD** (B) |
| Baseline | **sempre o HPA nativo**; C acrescenta "sem autoscaler" |

### Avaliação

Métricas relatadas: número de pods ao longo do tempo, latência, **taxa de erro HTTP
5xx** como indicador direto de sobrecarga (B), violações de SLA acumuladas, e
economia de recursos.

Cenários: crescimento abrupto, queda súbita, padrão diurno e rajadas aleatórias.

---

## 4. Bancadas usadas

| Trabalho | Ambiente |
|---|---|
| A | Python + TensorFlow; avaliação **sobretudo offline** sobre os traços |
| B | Cluster real: **1 plano de controle + 3 nós de trabalho**, cada um com 2 CPUs e 2 GB; Ubuntu 23.04, Kubernetes 1.26.3, Prometheus 2.47 |
| C | **Minikube** com 16 CPUs e 32 GB, sobre Xeon Gold 5215; Kubernetes 1.27.4; rede 5G do OpenAirInterface |
| E (campo) | Mistura de simulação (CloudSim, AutoScaleSim) e bancadas pequenas; poucos em nuvem real |

**Nenhum dos seis mede energia.** Nenhum usa RAPL, Scaphandre ou Kepler.

---

## 5. Resultados que interessam

**O modelo simples venceu a rede neural (B).** Na mesma série, Holt–Winters obteve
**RMSE 34,1 e MAPE 12,1%**, contra **RMSE 41,8 e MAPE 14,3%** da LSTM. E o custo:
Holt–Winters treina em **menos de 0,3 s**; a LSTM, em **cerca de 10 s**. Por isso eles
adotaram um **híbrido**: Holt–Winters cobre a partida a frio, e a LSTM assume quando há
histórico suficiente.

> Isso confirma a regra que o pipeline já adota: **baseline primeiro**. E dá uma
> referência publicada para citar quando a banca perguntar por que comparar com
> modelos simples.

**O proativo ganha onde era esperado (B, C).** A vantagem aparece na **subida** da
carga: o reativo sistematicamente atrasa, acumulando erros 5xx. Em C, a eficácia
depende do nível de demanda — com carga baixa, a diferença entre HPA e GRU é pequena.

**Limitar o `maxReplicas` corretamente economiza 15% dos nós (D).** Sem nenhum ML.
É um baseline incômodo e honesto: parte da economia atribuída a métodos sofisticados
pode vir de simplesmente configurar bem o HPA.

---

## 6. As lacunas, segundo a revisão sistemática (E)

A seção 5.6 chama-se literalmente *"What Are the Challenges in Achieving
Energy-Efficient Autoscaling?"*. Dela saem quatro afirmações que sustentam o projeto:

1. **Sustentabilidade é lacuna declarada.** A tabela de comparação entre revisões
   anteriores marca "sustainability absent" em quase todas as linhas. O resumo do
   artigo termina pedindo pesquisa em *"sustainability-aware autoscaling"*.
2. **A diretriz deles é a métrica do projeto:** *"Energy efficiency should be treated as
   a primary optimization objective alongside cost and SLOs... quantify the impact of
   autoscaling decisions on both dynamic and idle power consumption."* — é exatamente a
   separação estática/dinâmica da Fase 3.
3. **Pedem fronteiras de Pareto:** *"SLO–cost–energy trade-offs should be reported as
   families of operating points (for example, Pareto fronts) rather than single values"*
   — é a varredura de pesos da Fase 6.
4. **Descrevem a faixa segura:** *"many operators prioritise SLO satisfaction as a hard
   constraint and then seek to minimise cost and energy within the feasible region"* —
   é a política de `J(n)` com `γ` dominante.

Outras lacunas apontadas: atraso de atuação e de telemetria, escalonamento híbrido,
coordenação multi-serviço, falta de benchmarks padronizados e **baixa reprodutibilidade**.

E **Transfer Learning não aparece** entre as 60 obras revisadas.

---

## 7. Onde o projeto se encaixa

| Dimensão | O campo | O projeto |
|---|---|---|
| Alvo da previsão | requisições/s | **igual** — base sólida |
| Modelo | LSTM, Bi-LSTM, GRU, híbridos | **igual**, com baselines obrigatórios |
| Laço de controle | MAPE-K | **igual** |
| Baseline | HPA nativo | **igual**, mais HPA bem ajustado, agenda e carbono |
| Dados | traços públicos + bancada | **igual** — NASA e FIFA, reproduzidos com k6 |
| **Medir energia** | **ninguém** | **RAPL medido** ← original |
| **Carbono na decisão** | lacuna declarada | **sim** ← original |
| **Custo do próprio ML** | ninguém | **medido** ← original |
| **Transfer Learning** | ausente nas 60 obras | **sim** ← original |

**A frase de posicionamento:** *"a literatura de autoscaling preditivo em Kubernetes
está consolidada em prever demanda com redes recorrentes e agir antes do pico; o que ela
não faz é medir o custo energético dessa decisão nem o custo do modelo que a produz."*

---

## 8. Decisões que este compilado recomenda

1. **Adotar NASA-HTTP e FIFA 1998 como dados reais do projeto**, ao lado dos perfis
   sintéticos. São gratuitos, canônicos e comparáveis com a literatura. O dataset
   sintético deixa de ser a única base.
2. **Reproduzir os traços na bancada com k6**, em vez de só prever offline. Os trabalhos
   A e D param na previsão; B e C fecham o laço. Fechar o laço **com medição de energia**
   é o diferencial.
3. **Incluir Holt–Winters entre os baselines**, não só persistência e média móvel. Há
   precedente publicado de ele vencer a LSTM.
4. **Medir e reportar o tempo de predição**, como fazem A e B. Para um controlador que
   decide a cada 15 s, isso é requisito, e conversa com o custo energético do ML.
5. **Usar a taxa de erro 5xx** como indicador direto de sobrecarga, além do p95.
6. **Citar a seção 5.6 da revisão (E)** no Capítulo III: é a lacuna declarada, por
   escrito, em revisão sistemática de 2026.

---

## 9. Artigos que ainda faltam

Canônicos deste recorte, citados pelos próprios artigos lidos:

| Trabalho | Por que |
|---|---|
| **Dang-Quang & Yoo (2021)** — *Deep Learning-Based Autoscaling Using Bidirectional LSTM for Kubernetes*, Applied Sciences | **O artigo de referência de Bi-LSTM em Kubernetes.** Citado por A e F. Usa NASA e FIFA |
| **Yan et al. (2021)** — *HANSEL: Adaptive horizontal scaling of microservices using Bi-LSTM*, Applied Soft Computing | Bi-LSTM para microsserviços |
| **Imdoukh, Ahmad & Alfailakawi (2020)** — Neural Computing and Applications | LSTM para autoscaling de containers |
| **Toka et al. (2021)** — IEEE TNSM | Vários preditores em Kubernetes de borda |
| **Rossi, Nardelli & Cardellini (2019)** — IEEE CLOUD | Escala horizontal e vertical por RL |
| **Qu, Calheiros & Buyya (2018)** — ACM Computing Surveys | Taxonomia clássica de autoscaling |
| **Straesser et al. (2022)** — ICPE | *Why Is It Not Solved Yet?* — limitações práticas |
| **Cañete et al. (2022)** | Autoscaling proativo **consciente de energia**, com potência ociosa e dinâmica — o mais próximo da proposta |
| **Jeong et al. (2023)** | Autoscaling por RL com foco em sustentabilidade, em AWS |

Os quatro últimos ligam esta base ao capítulo de sustentabilidade.

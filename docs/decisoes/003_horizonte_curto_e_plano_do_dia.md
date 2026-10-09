# Decisão 003 — O limite do horizonte curto e a proposta do plano do dia

**Data:** 09/10/2026
**Status:** proposta — hipótese a ser confirmada com os números da reprodução de Dang-Quang & Yoo (2021)

---

## A pergunta que originou esta decisão

> "10 minutos na frente é muito raso. Pode até melhorar, mas continua quase reativo.
> Se tem 10 números subindo, a rede gasta muitos pods para criar, prevendo que vão
> subir, mas pode ser um ruído."
> — Pedro Assunção, 09/10/2026

## Como a rede de referência funciona

Exemplo concreto, com a configuração de Dang-Quang & Yoo (2021):

```
ENTRADA (o que aconteceu):   100, 120, 150, 180, 200, 230, 250, 270, 290, 300   ← req/min, de t-9 até t
                                                │
                                              REDE
                                                │
SAÍDA (o que vai acontecer): 320, 340, 360, 380, 400, 410, 420, 430, 440, 450   ← req/min, de t+1 até t+10
```

- **Os 10 números da saída são as requisições previstas para cada um dos próximos 10
  minutos.** O primeiro é o minuto seguinte, o último é daqui a 10 minutos. **Não são pods.**
- **Como ela aprende:** a rede não sabe o que é "requisição". Ela só vê números. No
  treino recebe dezenas de milhares de exemplos tirados da história real ("estes 10
  números vieram antes, estes 10 vieram depois"), compara a sua previsão com o que
  aconteceu e ajusta os pesos para errar menos.
- **Os pods saem depois da rede:** `pods = carga prevista ÷ capacidade de um pod`.
  Ex.: 450 req/min ÷ 50 req/min por pod = 9 pods daqui a 10 minutos.

**A entrada define o que a rede consegue aprender.** Com só 10 minutos de passado, ela
não tem como saber "é segunda, 9h, daqui a pouco começa o pico".

## Onde a crítica está certa

**1. Com 10 minutos de entrada, a rede vira quase um "reativo melhorado".**
Ela só vê a tendência recente, então o que mais consegue fazer é **prolongar a curva**:
se subiu, continua subindo. Há evidência na revisão: Beshley et al. (2026) mostram um
modelo estatístico simples (Holt-Winters, RMSE 34,1) **vencendo a LSTM** (RMSE 41,8).
Em horizontes curtos, "repetir o valor atual" é um concorrente muito difícil de bater.

**2. Ela não consegue separar ruído de pico verdadeiro.**
Dez minutos subindo às 3h da manhã provavelmente é ruído. Dez minutos subindo numa
segunda às 8h50 é o começo do pico da manhã. **Só com 10 minutos de entrada, as duas
situações são idênticas para a rede.** Ela não tem a informação que as distingue.

## Onde a crítica se relativiza

**1. Os 10 minutos à frente têm função.** Um pod leva de segundos a um minuto para
ficar pronto; para **pods**, um horizonte curto basta para chegar a tempo. O problema
não é o horizonte ser curto, é a rede **só** pensar no curto prazo.

**2. A rede treinada não reage a qualquer subida.** Se nos dados as pequenas subidas
costumam voltar logo, ela aprende isso e prevê subidas menores. **É uma hipótese, a
ser medida.**

**3. Os artigos já têm freios contra ruído, fora da rede.** O Algoritmo 1 espera 1
minuto entre decisões (CDT) e só remove 60% do excedente (RRS); o HPA espera 5 minutos
para descer. Eles **amortecem** o ruído, mas sem distinguir ruído de pico.

## A lacuna na literatura

| Trabalho | Quanto à frente prevê |
|---|---|
| Dang-Quang & Yoo (2021) | 1 e 5 minutos |
| Guruge & Priyadarshana (2025) | 1 minuto |
| NimbusGuard (2026) | decisões a cada 30 segundos |
| Demais trabalhos encontrados | minutos ou segundos |

Na indústria:

- **AWS Predictive Scaling:** prevê as próximas **48 horas, hora a hora**, com 14 dias de
  histórico, atualizado a cada 6 h. **Só sobe** capacidade; para descer depende do
  reativo. Granularidade horária: não pega picos curtos.
- **Azure Predictive Autoscale:** prevê CPU, exige 7 dias de histórico, também exige
  regras reativas configuradas.

> ❌ **Correção (09/10/2026, mesmo dia).** Uma primeira versão deste documento afirmava
> que "nenhum trabalho junta os dois". **Estava errado.** A busca inicial usou termos
> atuais (LSTM, Kubernetes) e não pegou a literatura clássica, que chama a ideia de
> *hybrid provisioning* ou *multi-timescale provisioning*. O próprio dono do projeto
> desconfiou da afirmação, e uma segunda busca confirmou que a ideia existe desde 2005.

### Trabalhos que já combinam longo prazo + curto prazo

| Trabalho | O que faz | Relação com a proposta |
|---|---|---|
| **Urgaonkar, Shenoy, Chandra, Goyal, Wood** — ACM TAAS, 2008 (versão de conferência em 2005) | provisionamento **preditivo** para mudanças lentas e grandes (escala de horas) + **reativo** para flutuações rápidas | **é a ideia do "plano do dia + correção"**, para aplicações web multicamadas |
| **Gandhi, Chen, Gmach, Arlitt, Marwah** — IGCC 2011, prêmio de melhor artigo ([resumo](../../revisao_bibliografica/resumos/05_gandhi_2011_hybrid_provisioning.md)) | analisa o histórico para extrair a **carga de base** de longo prazo; cobre a base com provisionamento **preditivo** (intervalos longos) e os picos com **reativo** (intervalos curtos). Até **35% menos energia** e 21% menos violações de SLA, evitando ligar e desligar servidores o tempo todo | **o mais próximo de todo o projeto**, inclusive da parte de energia. Leitura obrigatória |
| **Gong, Gu, Wilkes (PRESS)** — CNSM 2010 | detecta padrões repetitivos na demanda e prevê recursos | previsão baseada em padrões |
| **Qian et al. (RobustScaler)** — ICDE 2022, Alibaba | detecta a **periodicidade** da carga, modela a incerteza e dá garantias de QoS | separa padrão de ruído |
| **OptScaler** — VLDB 2024, Ant Group | módulos proativo e reativo **integrados** por otimização (controle preditivo) | crítica: em muitos híbridos os dois módulos funcionam de forma independente |
| **Guruge & Priyadarshana** — Frontiers, 2025 (**já está na revisão**) | **Prophet captura a sazonalidade** (dia/semana) e a **LSTM modela o que sobra** (o resíduo) | é "padrão + correção" **na previsão**, mas o horizonte continua sendo 1 minuto |
| **AWS Predictive Scaling** | plano de 48 h, hora a hora, + regras reativas para descer | versão industrial |

### O que sobra como contribuição possível (a verificar)

A ideia de combinar escalas de tempo **não é nova**. O que pode ser novo é a combinação de:

1. **Aplicação em Kubernetes**, compondo ferramentas atuais (HPA, KEDA), quando os
   trabalhos clássicos usavam máquinas físicas ou virtuais
2. **Energia medida** (RAPL) e convertida em **carbono**, quando Gandhi et al. (2011)
   usaram modelos de potência
3. **Redes neurais com previsão em vários horizontes**, e não modelos estatísticos
4. **Avaliação lado a lado** com a referência de curto prazo (Dang-Quang & Yoo, 2021) e
   com o híbrido clássico

> ⚠️ Antes de afirmar qualquer lacuna na dissertação: ler Gandhi et al. (2011) e
> Urgaonkar et al. (2008) na íntegra, e fazer busca sistemática com os termos
> *hybrid provisioning*, *multi-timescale*, *predictive + reactive*, *day-ahead*,
> *hierarchical forecasting autoscaling*.

## A proposta: plano do dia + correção do minuto

```
PLANO DO DIA (horizonte longo)            CORREÇÃO DO MINUTO (horizonte curto)
"segunda, 9h: costuma precisar      +     "agora está 15% acima do esperado:
 de ~20 pods"                              põe mais 3 pods"
 vem do calendário e do histórico          vem dos últimos minutos
```

- O **plano do dia** sabe o que é normal para cada horário. Uma subida às 3h que foge do
  padrão é tratada com desconfiança; uma subida às 8h50 já era esperada.
- A **correção do minuto** só ajusta em torno do plano: captura o pico que veio maior
  ou mais cedo que o normal.
- **O ruído perde força**, porque a decisão não depende só dos últimos 10 minutos.

Encaixa nos dois níveis de escala (Decisão 002): **pods** precisam de minutos de
antecedência; **ligar e desligar máquinas** precisa de horas.

É a mesma estrutura de Urgaonkar et al. (2008) e Gandhi et al. (2011), trazida para
Kubernetes, redes neurais e energia medida. Deve ser apresentada assim, e não como
ideia inédita.

## Como transformar a dúvida em resultado

A reprodução de Dang-Quang & Yoo (2021) **continua necessária**: é a régua para provar
que a proposta é melhor. E ela já responde à crítica com números:

| Pergunta | Como medir |
|---|---|
| A LSTM de 10 min é "quase reativa"? | comparar com a **persistência** (repetir o valor atual). Diferença pequena = a crítica se confirma |
| Ela gasta pods à toa com ruído? | **θO** (pods sobrando) e **número de mudanças de escala** (oscilação) |

Se os números confirmarem, **este é o argumento central da dissertação**:

> *"O modelo de referência é quase reativo e sensível a ruído; a nossa proposta, que
> conhece o padrão do dia, resolve isso."*

## Próximos passos

1. Rodar a reprodução (10 min de entrada; previsão de 1, 5 e 10 min; Algoritmo 1;
   métricas do SPEC) na NASA e na Copa
2. Medir persistência × LSTM, θO e oscilação
3. Mudar a entrada (mais passado + calendário) e criar o horizonte longo
4. Ler Gandhi et al. (2011) e Urgaonkar et al. (2008) na íntegra
5. Busca sistemática para delimitar a contribuição

## Referências

- DANG-QUANG, N.-M.; YOO, M. *Deep Learning-Based Autoscaling Using Bidirectional LSTM
  for Kubernetes.* Applied Sciences, v. 11, n. 9, 3835, 2021.
- GURUGE; PRIYADARSHANA. *Time series forecasting-based Kubernetes autoscaling using
  Facebook Prophet and LSTM.* Frontiers in Computer Science, 2025. (conferir iniciais)
- BESHLEY et al. *AI-Based Proactive Autoscaling Technique for Web Applications in
  Kubernetes.* IEEE TCSET, 2026.
- NimbusGuard: arXiv:2604.11017, 2026.
- URGAONKAR, B.; SHENOY, P.; CHANDRA, A.; GOYAL, P.; WOOD, T. *Agile Dynamic Provisioning
  of Multi-Tier Internet Applications.* ACM TAAS, v. 3, n. 1, 2008. DOI 10.1145/1342171.1342172.
- GANDHI, A.; CHEN, Y.; GMACH, D.; ARLITT, M.; MARWAH, M. *Minimizing Data Center SLA
  Violations and Power Consumption via Hybrid Resource Provisioning.* IGCC 2011.
  PDF: pdl.cmu.edu/ftp/PowerMgmt/igcc_2011.pdf
- GONG, Z.; GU, X.; WILKES, J. *PRESS: PRedictive Elastic ReSource Scaling for cloud
  systems.* CNSM 2010.
- QIAN, H. et al. *RobustScaler: QoS-Aware Autoscaling for Complex Workloads.* ICDE 2022.
  arXiv:2204.07197.
- *OptScaler: A Collaborative Framework for Robust Autoscaling in the Cloud.* PVLDB, v. 17,
  2024. arXiv:2311.12864.
- AWS. *How predictive scaling works.* docs.aws.amazon.com/autoscaling/ec2/userguide/predictive-scaling-policy-overview.html
- Microsoft. *Azure Monitor predictive autoscale for VM Scale Sets.*
- Resumo da literatura de autoscaling preditivo: `revisao_bibliografica/resumos/04_compilado_autoscaling_preditivo.md`

# Hybrid Resource Provisioning (Gandhi et al., 2011)

**Referência:** GANDHI, A.; CHEN, Y.; GMACH, D.; ARLITT, M.; MARWAH, M. *Minimizing Data
Center SLA Violations and Power Consumption via Hybrid Resource Provisioning.* In:
International Green Computing Conference (IGCC), 2011. IEEE. ISBN 978-1-4577-1221-0.

**Instituições:** Carnegie Mellon University; HP Labs (Palo Alto)
**Tipo:** pesquisa primária (propõe método, simula com traços reais e testa em bancada)
**Veículo:** IGCC 2011 — **prêmio de melhor artigo**
**PDF:** `artigos relacionados/Gandhi_2011_Hybrid_Resource_Provisioning_IGCC.pdf`
(fonte: pdl.cmu.edu/ftp/PowerMgmt/igcc_2011.pdf). Existe versão estendida:
*Hybrid Resource Provisioning for Minimizing Data Center SLA Violations and Power Consumption*.

---

## Ideia central

Dividir a carga em duas partes e tratar cada uma no seu ritmo:

```
carga real = carga de BASE (o padrão do dia)  +  RUÍDO (o que foge do padrão)
                │                                     │
       PREVISÃO, em horas                     REATIVO, em minutos
       (planeja o dia inteiro)                (cobre só o excesso)
```

- **Base:** extraída do histórico. É previsível, então é provisionada **com antecedência**,
  em intervalos longos (horas)
- **Ruído:** a diferença entre a carga real e a base. É imprevisível, então é coberto
  **de forma reativa**, em intervalos curtos (10 minutos)

## Problema atacado

| Abordagem | Problema |
|---|---|
| Só previsão | cargas reais fogem do padrão (picos repentinos, quedas, feriados) → violações de SLA |
| Só reativo | ligar um servidor leva minutos e gasta quase a potência máxima → atrasa e erra nos picos |
| Provisionar muito | atende o SLA, mas desperdiça energia |
| Mudar a capacidade toda hora | ligar e desligar servidores custa energia, tempo e **desgasta o hardware** |

Observação que motiva o trabalho: nos traços analisados o pico é de **4 a 5 vezes a
média**, e o periodograma (FFT) mostra um **padrão diário forte** (período de 24 h).

## Como fizeram

### Arquitetura (4 peças)

| Peça | O que faz |
|---|---|
| **Previsor da base** (*base workload forecaster*) | 1x por dia: acha o período dominante com FFT (24 h), prevê o dia seguinte e o **discretiza** em poucos intervalos |
| **Controlador preditivo** | converte a base prevista em número de servidores com um modelo de fila; **não muda até a próxima previsão** |
| **Controlador reativo** | só age quando a carga real **passa** da base; estima o excesso dos próximos 10 min como igual ao dos últimos 10 min |
| **Coordenador** | distribui as requisições entre os servidores da base e os do excesso |

### Passo 1 — Achar o padrão (FFT)

Periodograma sobre o histórico → o pico em 24 h mostra o ciclo diário.

### Passo 2 — Prever o dia seguinte (propositalmente simples)

> *"Para prever, basta tirar a média da demanda diária histórica. Técnicas avançadas de
> previsão podem ser usadas, mas estão fora do escopo deste artigo."*

Na avaliação: o **percentil 90 da mesma hora nos últimos 7 dias**.

### Passo 3 — Discretizar a base (a contribuição principal)

Transformar a curva prevista do dia numa **escada com poucos degraus**: intervalos de
tamanho variável, cada um com um único valor (a média do trecho).

Objetivo: minimizar ao mesmo tempo

```
erro de representação (quanto a escada se afasta da curva)  +  c · (número de degraus)
```

- Resolvido por **programação dinâmica**, com solução ótima
- **Menos degraus = menos mudanças de capacidade** = menos liga/desliga de servidores
- Regra prática: `c = Var/4`. Os autores consideram aceitável mudar a capacidade
  **a cada 4–6 horas** (menos de 5 mudanças por dia)
- Com padrão nenhum, a escada vira um degrau só (a média): é robusto

### Passo 4 — Da carga para o número de servidores

Modelo de fila M/G/1/PS, com λ = taxa de requisições, s = tempo médio de atendimento,
t₀ = tempo de resposta alvo (SLA):

```
servidores = ⌈ λ / (1/s − 1/t₀) ⌉
```

### Passo 5 — Reativo para o excesso

```
excesso previsto (próximos 10 min) = excesso observado (últimos 10 min)
```

Só é acionado quando a carga **passa** da base. Se a carga ficar abaixo, nada é removido
até a próxima previsão. Os autores testaram ARMA e janela móvel, mas a regra simples
funcionou bem.

## Montagem experimental

### Traços

| Traço | O que contém | Duração | Intervalo |
|---|---|---|---|
| SAP (aplicação empresarial, HP) | CPU e memória | 5 semanas | 5 min |
| VDR (aplicação crítica, HP) | taxa de chegada + utilização | 10 dias | 5 min |
| Web 2.0 (HP, 85 milhões de usuários) | utilização | 8 dias | — |
| **WorldCup98** | requisições (Internet Traffic Archive) | — | — |

Os autores descrevem a Copa como **menos previsível**: os picos dependem do resultado
dos jogos.

### Políticas comparadas

| Política | Como decide |
|---|---|
| Predictive/24h, /6h, /1h | percentil 90 dos últimos 7 dias, em blocos fixos |
| Predictive/var | blocos variáveis da programação dinâmica |
| Reactive | estima a demanda a cada 10 min |
| Hybrid/fixed | preditivo de hora em hora + reativo |
| **Hybrid/var** (proposta) | preditivo com blocos variáveis + reativo |

### Duas avaliações

1. **Simulação com os traços:** treina com 7 dias e avalia o **8º dia**
   - SLA violado = intervalo de 5 min em que a demanda passou da capacidade
   - Potência **estimada** por modelo linear: `P = P_ocioso + (P_max − P_ocioso) · u`
   - Contagem de mudanças de capacidade no dia
2. **Bancada real:** 10 servidores blade (2× Xeon E5535, 16 GB)
   - 1 gerador de carga (**httperf** reproduzindo os traços), 1 balanceador, **8 servidores Apache**
   - Processamento simulado com **LINPACK** (carga de CPU ajustável)
   - Carga dos traços **reescalada** para caber em 8 servidores
   - Servidores ligados e desligados remotamente; **potência medida** pelo processador de
     gerenciamento da blade (hardware)

## Resultados

### Simulação (traço SAP, o único com números detalhados)

| Comparação | Resultado |
|---|---|
| Hybrid/var × **Reactive** | violações de SLA de **50% → 5,6%** |
| Hybrid/var × Predictive/1h e /6h | violações de 12% → 5,6%, **mesma potência** |
| Hybrid/var × Predictive/var | 7,3% → 5,6% |
| Hybrid/var × Predictive/24h | **27% menos potência**, desempenho parecido |
| Hybrid/var × Hybrid/fixed | violações de 10,1% → 5,6%; mudanças de **43 → 14** |

Para Web, VDR e **Copa**, os autores dizem apenas que os resultados foram "similares",
**sem números**.

### Bancada

| Traço | Resultado |
|---|---|
| Web | **35% menos potência** que Predictive 90%ile/1h; até 41% menos tempo de resposta que Predictive Mean/1h. O reativo não atingiu o SLA por causa do tempo de ligar servidores |
| VDR | Hybrid/var e Predictive 90%/1h atendem o SLA; o híbrido gasta "um pouco menos" |

## Pontos fracos (onde dá para avançar)

| Ponto fraco | Oportunidade para a dissertação |
|---|---|
| Previsão **ingênua** (média/percentil dos últimos 7 dias), assumida pelos autores | **LSTM** para a base, que capta tendência e semana, não só a média |
| Reativo ingênuo: "excesso de agora = excesso dos próximos 10 min" | **LSTM de curto prazo** (Dang-Quang) para o excesso |
| Escala de **servidores inteiros** | **pods** (curto prazo) e **máquinas** (longo prazo) — Decisão 002 |
| Potência **estimada por modelo linear** na simulação | energia **medida** por RAPL; modelo não linear (Fan et al.) |
| Copa avaliada **sem números publicados** | avaliar e publicar os números na Copa |
| Avaliação de **um único dia**, sem repetições nem estatística | várias repetições, intervalo de confiança, testes |
| Sem carbono | conversão para **carbono** |
| 2011: máquinas físicas/VMs, httperf | **Kubernetes**, KEDA/HPA, k6 |

## Relevância para a dissertação

**É o trabalho mais próximo do projeto inteiro.** Junta previsão de longo prazo,
reativo de curto prazo, energia e custo de mudar a capacidade. **E usa a Copa de 98**,
a mesma base que já preparamos (`docs/pre_processamento/02_copa_1998.md`).

A contribuição da dissertação deve ser apresentada como **atualização deste trabalho**
(ver `docs/decisoes/003_horizonte_curto_e_plano_do_dia.md`):

> *"O provisionamento híbrido reduziu energia e violações de SLA com previsão simples e
> servidores físicos (Gandhi et al., 2011). Este trabalho o leva para Kubernetes, com
> redes neurais nos dois horizontes e energia medida."*

## Como fazer aqui

### Mapeamento das peças

| Peça do artigo | Equivalente no projeto |
|---|---|
| Previsor da base (média de 7 dias) | **baseline**: perfil histórico (percentil 90 da mesma hora, últimos 7 dias) → **proposta**: LSTM com calendário |
| Discretização por programação dinâmica | reaproveitar **direto** para o nível de **máquinas** (poucas mudanças por dia), e como histerese para pods |
| Controlador preditivo | KEDA com gatilho Prometheus publicando os pods da base (ou gatilho *cron*) |
| Controlador reativo do excesso | o gatilho de **CPU** do HPA/KEDA |
| Coordenador | dispensável: no Kubernetes o *Service* já balanceia entre todos os pods |
| Modelo de fila M/G/1/PS | capacidade do pod **medida com k6** |
| httperf + LINPACK | k6 + endpoint `/work?n=N` (carga de CPU controlada) |
| Potência pela blade | RAPL |

> 💡 **Coincidência útil:** com dois gatilhos, o KEDA/HPA usa o **maior** valor
> (`docs/algoritmos.md`, seção 1.4, etapa 5). Gatilho preditivo = base, gatilho de CPU =
> reativo: o HPA já combina os dois **nativamente**, sem código extra. Quando a carga
> passa da base, a CPU sobe e o reativo acrescenta pods, que é o comportamento do artigo.

### Experimento para reproduzir primeiro (offline, só com a Copa)

1. Treinar com 7 dias, avaliar o 8º (como no artigo); depois repetir em vários dias
2. Implementar as políticas: **Predictive/1h** (percentil 90), **Predictive/var** (programação
   dinâmica), **Reactive** (10 min), **Hybrid/var**
3. Métricas do artigo: % de intervalos com SLA violado, número de mudanças, e
   pods-minuto como estimativa de energia
4. Acrescentar Dang-Quang (LSTM de curto prazo) e a proposta (LSTM base + LSTM excesso)
5. **Publicar os números da Copa**, que o artigo não mostra

## O que reaproveitar

1. **A decomposição base + ruído** como estrutura da proposta
2. **A discretização por programação dinâmica** para limitar mudanças de capacidade
3. **O percentil 90 dos últimos 7 dias, por hora** como baseline preditivo
4. **As três métricas:** violações de SLA, potência e **número de mudanças**
5. **Treinar com 7 dias, avaliar o 8º** como protocolo inicial
6. **Reescalar a carga** dos traços para a capacidade da bancada (eles fizeram igual)

## Leituras derivadas

- **Urgaonkar et al.** — *Dynamic Provisioning of Multi-tier Internet Applications*, ICAC
  2005 / ACM TAAS 2008 (referência [23]: o híbrido anterior)
- **Gmach et al.** — *Capacity Management and Demand Prediction for Next Generation Data
  Centers*, ICWS 2007 (referência [13]: técnicas de previsão)
- **Gandhi, Harchol-Balter, Adan** — *Server farms with setup costs*, Performance
  Evaluation, 2010 (referência [12]: o custo de ligar servidores)
- **Bennani & Menascé** — *Resource Allocation for Autonomic Data Centers using Analytic
  Performance Models*, ICAC 2005 (referência [4]: outro híbrido)
- Versão estendida do próprio artigo (a buscar)

# Contexto do projeto — para continuar de qualquer máquina

**Atualizado em:** 09/10/2026
**Leia primeiro.** Resume onde o projeto está, o que foi decidido, o algoritmo proposto
e os próximos passos. Os detalhes estão nos documentos linkados.

---

## 1. O que queremos (prioridades do dono do projeto)

1. Autoscaling de **pods** no Kubernetes, **compondo ferramentas que já existem** (não reinventar a roda)
2. Uma **LSTM** que aprende a série de **requisições por segundo/minuto** e prevê quantos
   pods serão necessários: primeiro daqui a 10 minutos, depois horas, e (ambição) dias,
   meses e anos
3. Depois: estimar a **energia** economizada e converter em **carbono**
4. Depois: base própria com requisições + energia, e um algoritmo de decisão mais inteligente

**Objetivo final:** mostrar que o nosso autoscaling e a metodologia são melhores que os
da literatura, e acrescentar a sustentabilidade.

**Regra de trabalho:** documentar cada passo em `docs/` **na hora em que é feito**.

---

## 2. Onde estamos

| Item | Situação |
|---|---|
| Revisão bibliográfica | 5 resumos em `revisao_bibliografica/resumos/` |
| Bases de dados | NASA, Copa 98 e Wikipédia baixadas e processadas **na máquina do lab** (não estão no git) |
| Notebook de treino | `reproducao/notebooks/treino_lstm_10min_colab.ipynb` — LSTM, Bi-LSTM e GRU, previsão de 10 min. Versão Colab; **ainda sem o Algoritmo 1 e sem ajuste para rodar local** |
| Algoritmo proposto | **v0.1 escrito, aguardando validação** — `docs/algoritmo_proposto.md` |
| Resultados | **nenhum ainda** |
| Cluster Kubernetes | não montado |

---

## 3. O algoritmo proposto (v0.1) — resumo

O melhor dos dois mundos:

- **Gandhi et al. (2011)** — planeja **o dia todo** (carga de base)
- **Dang-Quang & Yoo (2021)** — Bi-LSTM prevê **os próximos minutos** e o Algoritmo 1 decide os pods

```
1x por dia     NÍVEL 1 — PLANO DO DIA                 (Gandhi 2011)
(00:00)        últimos 7 dias → percentil 90 de cada hora → escada com
               poucos degraus (programação dinâmica) → pods_base(t)
                                     │  piso
                                     ▼
a cada         NÍVEL 2 — CORREÇÃO DO MINUTO          (Dang-Quang 2021)
minuto         últimos 10 min → Bi-LSTM → carga prevista → pods_lstm
                                     │
                                     ▼
               pods_desejado = max(pods_base, pods_lstm)
               Algoritmo 1: espera 1 min entre decisões (CDT); sobe direto;
               desce só 60% do excesso (RRS); nunca abaixo de pods_base
```

`pods = ⌈carga ÷ C⌉`, com `C` = requisições por minuto que um pod atende.

### ⚠️ 4 pontos pendentes de validação (decidir antes de implementar)

1. **Peça do dia:** Gandhi (percentil 90 de 7 dias + escada) **ou** Guruge (2025, Prophet)?
2. **Previsão que decide os pods:** `t+1` (como o artigo) **ou** o maior valor dos próximos 10 min (mais seguro, gasta mais)?
3. **Capacidade do pod:** 500 req/min (valor de Dang-Quang para a Copa)?
4. **Plano do dia como piso:** a Bi-LSTM nunca desce abaixo do plano?

### Como testar (offline, base da Copa)

- Bi-LSTM treinada nos primeiros 70% do tempo; teste nos últimos ~26 dias, cada dia
  planejado com os 7 anteriores
- **7 concorrentes:** fixo, reativo (tipo HPA), Gandhi só plano, Gandhi híbrido,
  Dang-Quang, **proposta**, oráculo
- **Métricas:** θU, θO, TU, TO, εn (SPEC, Dang-Quang); % de minutos com SLA violado e nº
  de mudanças (Gandhi); pods-minuto (base para energia)

Detalhes: [algoritmo_proposto.md](algoritmo_proposto.md).

---

## 4. Decisões tomadas

| # | Decisão | Documento |
|---|---|---|
| 001 | Medir energia **só por software (RAPL)**, em máquina física do lab | [decisoes/001](decisoes/001_medicao_energetica_por_software.md) |
| 002 | Escalar em **dois níveis**: pods (minutos) e máquinas (horas) | [decisoes/002](decisoes/002_dois_niveis_de_escala.md) |
| 003 | Horizonte de 10 min é "quase reativo"; proposta = **plano do dia + correção do minuto** | [decisoes/003](decisoes/003_horizonte_curto_e_plano_do_dia.md) |

### Outras conclusões importantes da conversa

- **A métrica é requisições, não CPU.** Dang-Quang e Guruge escalam por
  `requisições previstas ÷ capacidade do pod`. O HPA padrão usa CPU.
- **Não é "maçã com banana":** compara-se o **resultado** (lentidão, pods ligados), não a
  métrica de entrada. A ponte: medir com k6 quantas req/s um pod aguenta a **70% de CPU**
  (alvo do HPA). No cluster, 3 concorrentes: HPA por CPU, HPA por requisições, nosso
  preditivo. Se o nosso vencer o "HPA por requisições", o ganho vem da **previsão**.
- **Nenhuma das nossas bases tem CPU.** A CPU será gerada na bancada (k6 reproduzindo
  NASA/Copa no cluster). Base pública com requisições + CPU + instâncias:
  **Huawei Private 2023** (ver [bases_de_dados](bases_de_dados/README.md)).
- **A ideia de plano de longo prazo + correção curta NÃO é nova:** Urgaonkar et al.
  (2008) e **Gandhi et al. (2011)**, este com 35% de economia de energia e **usando a Copa
  de 98**. A contribuição é **atualizar** isso para Kubernetes, redes neurais e energia
  medida. Ver o [resumo do Gandhi](../revisao_bibliografica/resumos/05_gandhi_2011_hybrid_provisioning.md).
- **Kubernetes já combina os dois níveis sem código:** com dois gatilhos no KEDA, o HPA
  usa o **maior** valor (gatilho preditivo = base; gatilho de CPU = excesso).
- **Capacidade do pod:** o artigo **supõe** 500 req/min. Com a NASA (pico de 405 req/min)
  isso daria sempre 1 pod, então a avaliação de pods faz sentido na **Copa** (pico de
  229.426 req/min → ~460 pods).

---

## 5. Problemas já encontrados no código antigo (`reproducao/src/`)

Corrigir ao implementar o algoritmo:

| Onde | Problema |
|---|---|
| `pods.py`, `PoliticaReativa` | o reativo dimensiona para **70%** de uso, mas os "pods necessários" usam 100% → o reativo parece desperdiçar ~43% a mais. Usar o mesmo alvo nos dois |
| `experimento.py`, perfil histórico | treinado com deslocamento de **9 minutos** (`X_treino[:, -1, 0]` começa no índice 9). Correção: `inicio_minuto_semana = JANELA − 1` |
| `pods.py`, CDT | após uma mudança, pula um minuto a mais: com CDT = 1 decide de 2 em 2 minutos. Conferir com o artigo |

---

## 6. Próximos passos, em ordem

1. **Validar os 4 pontos** do algoritmo (seção 3)
2. Ajustar o notebook para rodar **local e no Colab** (Keras 3 sem `import tensorflow`)
3. Implementar: Algoritmo 1 + métricas do SPEC + plano do dia (Gandhi) + os 7 concorrentes
4. Rodar na Copa (e na NASA) e preencher `docs/treino/README.md` com os resultados
5. Ver se a crítica da Decisão 003 se confirma (LSTM × persistência, θO, oscilação)
6. Depois: entrada com calendário e horizontes de horas; cluster com k6; energia (RAPL)

---

## 7. Montar o ambiente em outra máquina

### Código

```bash
git clone https://github.com/pedro-assuncao10/projeto_autoscaling_lstm_green_it.git
cd projeto_autoscaling_lstm_green_it/reproducao
python -m venv .venv
```

### Treino com GPU NVIDIA no Windows

TensorFlow **não** usa GPU no Windows nativo (e não suporta Python 3.14). Usar
**PyTorch + Keras 3**:

```bash
.venv\Scripts\python -m pip install torch --index-url https://download.pytorch.org/whl/cu126
.venv\Scripts\python -m pip install keras numpy pandas matplotlib jupyter ipykernel pypdf
set KERAS_BACKEND=torch
```

Sem GPU: o mesmo, sem o `--index-url` (CPU). No lab (RTX 3050): ~3,5 s por época com 30 mil exemplos.

### Dados (não estão no git)

Os CSVs processados são pequenos: **copie da máquina do lab** (pendrive/Drive) para
`reproducao/dados/`:

| Arquivo | Tamanho |
|---|---|
| `nasa_1min.csv` | 3,1 MB |
| `fifa_1min.csv` | 4,8 MB |
| `wikipedia_en.wikipedia_all-agents_1h.csv` | 4,1 MB |

Ou regenere (de dentro de `reproducao/`):

| Base | Comandos | Tempo |
|---|---|---|
| NASA | `python src/baixar_tracos.py nasa` e `python src/preparar_traco.py nasa dados/nasa_1min.csv` | ~2 min |
| Copa | `python src/baixar_tracos.py fifa 1 2 ... 92` e `python src/preparar_traco.py fifa dados/fifa_1min.csv` | **horas** (~8 GB). Dias que falharem por tempo esgotado: baixar de novo só esses dias |
| Wikipédia | `python src/baixar_wikipedia.py` | ~2 min |

Conferências: NASA = 3.461.612 requisições; Copa = 1.352.804.107 requisições.

---

## 8. Como trabalhar com o Claude neste projeto

(Preferências que o Claude da máquina do lab tem guardadas na memória e que **não vão
junto** para outra máquina.)

- Explicar em **português simples**, sem jargão, em passos curtos
- **Documentar tudo** em `docs/` na hora em que é feito
- **Não reinventar a roda**: compor ferramentas e seguir os artigos de referência
- **Nunca afirmar que "ninguém fez"** sem buscar também os termos clássicos (2005–2015).
  Já erramos uma vez (ver Decisão 003)
- Antes de afirmar números de artigos, **conferir no PDF** (`artigos relacionados/`)

---

## 9. Mapa dos documentos

| Documento | Conteúdo |
|---|---|
| [algoritmo_proposto.md](algoritmo_proposto.md) | o algoritmo v0.1, completo |
| [decisoes/](decisoes/) | decisões 001, 002, 003 |
| [pre_processamento/](pre_processamento/) | o que foi feito com cada base, com histórico |
| [bases_de_dados/](bases_de_dados/README.md) | catálogo de bases públicas (com e sem CPU) |
| [treino/](treino/README.md) | configuração do treino e tabela de execuções |
| [pipeline.md](pipeline.md) | plano experimental completo e original (mais ambicioso que as prioridades atuais) |
| [algoritmos.md](algoritmos.md) | estudo do código do HPA, KEDA, Carbon-Aware KEDA, CarbonScaler, KubeWatt |
| `../revisao_bibliografica/resumos/` | resumos dos artigos (01 a 05) |
| `../artigos relacionados/` | PDFs: Dang-Quang & Yoo (2021), Gandhi et al. (2011) |

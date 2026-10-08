# Reprodução — autoscaling preditivo com LSTM / Bi-LSTM

Reprodução do desenho de **Dang-Quang & Yoo (2021)**, *Deep Learning-Based Autoscaling
Using Bidirectional LSTM for Kubernetes* (Applied Sciences 11(9), 3835).

**A pergunta:** dada a carga atual e o histórico daquele sistema naquele horário,
**quantos pods vão ser necessários no próximo minuto?**

O caminho é em duas etapas, como na literatura:

```
histórico de carga  ──LSTM──►  carga prevista  ──política──►  número de pods
   (10 minutos)                  (t+1 minuto)                  (Algoritmo 1)
```

A rede **não decide a escala**. Ela só prevê a demanda; quem converte em pods é uma
política explícita e auditável.

---

## Como rodar

### Localmente (NumPy puro, sem GPU)

```bash
./executar.sh
```

Cria o ambiente virtual, instala **só o NumPy**, gera a série e roda tudo.
A LSTM é implementada do zero (`src/lstm.py`), então não precisa de TensorFlow
nem de muita memória.

### No Google Colab (Keras com GPU)

Abra `notebooks/reproducao_colab.ipynb` em [colab.research.google.com](https://colab.research.google.com).
TensorFlow, GPU e as bibliotecas já vêm instalados.

> O artigo original também foi treinado no Colab: *"trained on tensor processing unit
> (TPU) from Google Colab"*.
>
> ⚠️ Para um modelo deste tamanho, **a GPU quase não ajuda**: a LSTM é sequencial e a
> série é pequena. A vantagem do Colab aqui é não depender da memória da sua máquina.

---

## Estrutura

```
reproducao/
├── executar.sh                      roda tudo de ponta a ponta
├── requirements.txt                 só numpy
├── dados/
│   ├── exemplo_entrada.csv          AMOSTRA para visualizar o formato
│   └── LEIA-ME.md                   o que cada coluna significa
├── src/
│   ├── gerar_trace.py               série sintética (diária, semanal, rajadas)
│   ├── dados.py                     janelas, divisão temporal, normalização
│   ├── lstm.py                      LSTM e Bi-LSTM do zero em NumPy
│   ├── baselines.py                 persistência, média móvel, perfil por horário
│   ├── pods.py                      Algoritmo 1 (CDT + RRS) e política reativa
│   ├── metricas.py                  RMSE/MAE/MAPE/R² e elasticidade do SPEC
│   └── experimento.py               orquestra tudo
├── notebooks/
│   └── reproducao_colab.ipynb       versão Keras com GPU
└── resultados/                      métricas.json e serie_teste.csv (gerados)
```

---

## As decisões reproduzidas do artigo

| Item | Valor | Onde |
|---|---|---|
| Janela de entrada | **10 passos** (10 min) | `dados.py` |
| Unidades ocultas | **30** | `lstm.py` |
| Perda | MSE, com parada antecipada | `lstm.py` |
| Divisão | **70/30 temporal** | `dados.py` |
| Capacidade do pod | 500 req/min | `pods.py` |
| Pods mínimos | 10 | `pods.py` |
| Resfriamento (CDT) | 1 minuto | `pods.py` |
| Remoção parcial (RRS) | **0,60** | `pods.py` |
| Métricas de elasticidade | θ_U, θ_O, T_U, T_O, ganho | `metricas.py` |

**O que é o RRS:** quando a carga cai, a política **não remove todos os pods sobrando,
só 60% deles**. Mantém uma reserva para reagir mais rápido à próxima rajada. É uma
troca deliberada de energia por tempo de resposta — e no artigo é um número escolhido
à mão, **sem justificativa medida**. É exatamente a lacuna que a dissertação ataca com
o termo de custo do *cold start*.

---

## O que foi acrescentado além do artigo

| Acréscimo | Por quê |
|---|---|
| **Perfil histórico por horário** como baseline | Equivale ao escalonamento por agenda (cron do KEDA). Se a LSTM não vencer este, não há motivo para rede neural |
| **Política reativa explícita** | Imita o HPA com atraso de leitura e janela de descida de 5 min, para a comparação ser justa |
| **Tempo de predição por amostra** | Critério de projeto: o controlador decide a cada 15 s |
| **LSTM do zero** | Roda em máquina modesta e deixa os portões visíveis |

---

## Limitações, para não confundir com a dissertação

- A série é **sintética**. O próximo passo é usar os traços reais **NASA (1995)** e
  **FIFA (1998)**, do Internet Traffic Archive, agregados por minuto — é o que o
  artigo faz
- Os pods são **simulados**, não há cluster. O artigo também faz assim num dos
  experimentos, antes de ir ao cluster real
- **Não há medição de energia.** É justamente onde a dissertação vai além: nenhum
  dos trabalhos lidos mede energia

---

## Referências

- DANG-QUANG, N.-M.; YOO, M. *Deep Learning-Based Autoscaling Using Bidirectional
  Long Short-Term Memory for Kubernetes.* Applied Sciences, v. 11, n. 9, 3835, 2021.
  PDF em `../artigos relacionados/`
- Resumo e análise: `../revisao_bibliografica/resumos/04_compilado_autoscaling_preditivo.md`

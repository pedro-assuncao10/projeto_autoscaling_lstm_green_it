# Treino da LSTM — previsão de 10 minutos e número de pods

Registro de **como o modelo é treinado** e de **cada execução feita**. Os dados de
entrada estão descritos em [../pre_processamento/](../pre_processamento/).

## Onde está

| Arquivo | O que é |
|---|---|
| `reproducao/notebooks/treino_lstm_10min_colab.ipynb` | **o notebook do treino**, para o Google Colab |
| `reproducao/src/dados.py` | `maior_trecho_valido`: escolhe o trecho sem falha de medição |
| `reproducao/src/baixar_tracos.py`, `preparar_traco.py` | geram a base NASA dentro do Colab, se ela não existir |

O notebook baixa o projeto do GitHub ao começar. **O que roda no Colab é o que está
publicado no GitHub**, então qualquer mudança nos scripts precisa ser enviada (*push*)
antes de treinar.

## A pergunta que o modelo responde

> Olhando a carga dos **últimos 10 minutos**, quantas requisições virão em **cada um dos
> próximos 10 minutos**, e quantos pods serão necessários daqui a 10 minutos?

## Configuração padrão

| Item | Valor | Origem |
|---|---|---|
| Histórico (janela de entrada) | 10 minutos | Dang-Quang & Yoo (2021) |
| Horizonte | 10 minutos: a rede devolve t+1 … t+10 de uma vez | decisão do projeto |
| Entrada | só a carga (req/min); calendário opcional (`USAR_CALENDARIO`) | artigos usam só a carga |
| Divisão | 70% treino / 30% teste, na ordem do tempo | Guruge & Priyadarshana (2025) |
| Validação | últimos 10% do treino, também na ordem do tempo | — |
| Exemplos na fronteira treino/teste | descartados | evita "colar" do futuro |
| Normalização | min-max, calculada só no treino | — |
| Redes | LSTM, Bi-LSTM, GRU — 30 neurônios + camada densa | Dang-Quang & Yoo (2021); compilado da literatura |
| Treino | Adam, perda MSE, lote 64, até 100 épocas, para após 10 sem melhora | — |
| Semente | 42 | — |

## Comparação obrigatória (baselines)

| Baseline | Por quê |
|---|---|
| Persistência (repete a carga de agora) | **equivale ao autoscaler reativo (HPA)**, que decide pela carga atual |
| Média móvel dos últimos 10 min | suaviza ruído |
| Mesmo horário de ontem | captura o padrão diário sem rede neural |

**Regra:** se um baseline empatar com a rede, o baseline vence (é mais simples e barato).

## Métricas

- **Previsão**, para cada minuto à frente (1 a 10): RMSE, MAE, WAPE, MAPE, R²
  - O **WAPE** (erro total ÷ carga total) foi incluído porque o MAPE explode quando a
    carga é quase zero, o que acontece nas madrugadas da NASA
- **Pods**, para t+10: % de acerto exato, % do tempo em que faltou pod, % em que sobrou,
  média de pods faltando e sobrando por minuto
- **Custo**: número de parâmetros, épocas, tempo de treino, tempo de previsão por exemplo

## Capacidade de um pod

As bases não informam quantas requisições um pod atende. Regra adotada:

```
capacidade = pico de carga do treino ÷ PODS_NO_PICO     (padrão: 20)
pods(carga) = arredondar para cima(carga ÷ capacidade), mínimo 1
```

Na NASA: pico de 405 req/min → **capacidade ≈ 20 req/min por pod**.

> Os artigos usam valores fixos (ex.: 500 req/min em Dang-Quang & Yoo). Com a NASA
> isso daria sempre 1 pod, porque o pico é 405 req/min: a comparação perderia sentido.
> A regra proporcional ao pico vale para qualquer base.

## Verificação feita antes do primeiro treino (08/10/2026)

O notebook foi executado localmente com a NASA, trocando só o treino por uma previsão
artificial, para conferir o resto da lógica. Conferido automaticamente:

- a resposta de cada exemplo corresponde aos minutos t+1 … t+10 corretos
- a persistência usa o minuto t, e "ontem" usa t+h−1440
- nenhum exemplo de treino tem resposta no período de teste; a validação vem depois do treino

Tamanho com a NASA: 45.533 minutos utilizáveis (31,6 dias) → 28.669 exemplos de treino,
3.185 de validação, 13.651 de teste.

## Hipótese a testar

O horizonte de 10 minutos pode deixar a rede "quase reativa" e sensível a ruído.
Como medir e qual a proposta: [Decisão 003](../decisoes/003_horizonte_curto_e_plano_do_dia.md).

## Execuções

| Data | Base | Configuração | Melhor rede | Resultado | Pasta |
|---|---|---|---|---|---|
| — | — | — | — | — | — |

Ao terminar cada execução no Colab: baixar o `.zip`, extrair em
`reproducao/resultados/` e preencher uma linha aqui.

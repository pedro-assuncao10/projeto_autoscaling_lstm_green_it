# NASA-HTTP (1995)

## Origem

| Item | Valor |
|---|---|
| O que é | Todos os acessos ao servidor WWW do Kennedy Space Center (NASA), Flórida |
| Fonte | Internet Traffic Archive — `https://ita.ee.lbl.gov/traces/` |
| Arquivos | `NASA_access_log_Jul95.gz` (20,7 MB), `NASA_access_log_Aug95.gz` (16,6 MB) |
| Formato original | texto, *Common Log Format*, uma linha por requisição |
| Fuso do original | horário local, **−0400** |
| Baixado em | 08/10/2026, com `python src/baixar_tracos.py nasa` |
| Guardado em | `reproducao/dados/brutos/` (fora do git) |

Exemplo de uma linha original:

```
199.72.81.55 - - [01/Jul/1995:00:00:01 -0400] "GET /history/apollo/ HTTP/1.0" 200 6245
```

Só o trecho entre colchetes (data, hora e fuso) é usado.

## Passos

Comando (de dentro de `reproducao/`):

```bash
python src/preparar_traco.py nasa dados/nasa_1min.csv
```

| # | Passo | Detalhe |
|---|---|---|
| 1 | Ler cada linha e extrair data/hora | linhas que não seguem o formato são descartadas e contadas |
| 2 | Converter para UTC | soma 4 h ao horário local |
| 3 | Contar requisições por minuto | todas as linhas do mesmo minuto viram um número |
| 4 | Preencher a grade de minutos | todo minuto entre o primeiro e o último existe; minuto sem acesso = 0 |
| 5 | Marcar a queda do servidor | minutos do furacão Erin recebem `valido = 0` |
| 6 | Calcular req/s | req/min ÷ 60 |

## Resultado

Arquivo: `reproducao/dados/nasa_1min.csv`

| Medida | Valor |
|---|---|
| Linhas lidas | 3.461.613 |
| Linhas descartadas (malformadas) | **1** |
| Requisições contadas | 3.461.612 — **igual ao total publicado pelo Internet Traffic Archive** |
| Período (UTC) | 01/07/1995 04:00 a 01/09/1995 03:59 |
| Minutos | 89.280 (62 dias) |
| Minutos com zero acessos | 7.884 (inclui a queda do servidor) |
| Minutos sem medição (Erin) | 2.264 |
| Requisições por minuto | mínimo 0 · média 40 · máximo 405 |

## A queda do servidor (furacão Erin)

Segundo o Internet Traffic Archive, não há registros de **01/Aug/1995 14:52:01** a
**03/Aug/1995 04:36:13**, horário local, porque o servidor foi desligado por causa do
furacão. Em UTC: **01/08 18:52 a 03/08 08:36**.

Conferido nos dados: o tráfego vai a zero às 18:52 UTC e volta às 08:36 UTC.

> ⚠️ **Erro corrigido em 08/10/2026.** A primeira versão do script tratava esse horário
> como se já estivesse em UTC, marcando a queda 4 horas antes da real. Efeito: 4 h de
> tráfego verdadeiro eram descartadas e 4 h de zeros falsos ficavam como válidas.
> Corrigido em `src/preparar_traco.py` (constantes `ERIN_INI` e `ERIN_FIM`, agora com fuso −0400).

**Como a queda é tratada no treino:** `src/dados.py` usa só o **maior trecho contínuo
sem falhas**, ou seja, 01/07 a 01/08 (cerca de 31 dias). Os dias depois da queda ficam
fora. Alternativa a avaliar no futuro: usar os dois trechos, sem criar janelas que atravessem a queda.

## Decisões em aberto

- Usar só o trecho antes da queda (atual) ou também o depois
- Os minutos com zero fora da queda (madrugada) são tráfego real e ficam como estão

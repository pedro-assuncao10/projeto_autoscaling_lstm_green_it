"""Experimento completo, de ponta a ponta.

    1. carrega a série e monta as janelas (divisão temporal 70/30)
    2. treina LSTM e Bi-LSTM, e avalia contra os baselines
    3. converte carga prevista em número de pods (Algoritmo 1 do artigo)
    4. compara com uma política reativa (imitação do HPA)
    5. mede elasticidade pelas métricas do SPEC

Uso:  python3 src/experimento.py
"""
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

import baselines
import dados as D
import metricas
from lstm import RegressorLSTM
from pods import PoliticaPods, PoliticaReativa

ARQUIVO = os.environ.get("TRACE", "dados/trace_sintetico.csv")
SAIDA = "resultados"
CAPACIDADE_POD = 500.0      # requisições por minuto que um pod atende
PODS_MIN, PODS_MAX = 10, 60


def avaliar_modelo(nome, y_real, y_prev, tempo_ms):
    m = metricas.previsao(y_real, y_prev)
    m["tempo_predicao_ms"] = tempo_ms
    print(f"  {nome:34s} RMSE={m['RMSE']:9.2f}  MAE={m['MAE']:9.2f}  "
          f"MAPE={m['MAPE_%']:6.2f}%  R²={m['R2']:6.4f}  {tempo_ms:7.2f} ms")
    return m


def main():
    os.makedirs(SAIDA, exist_ok=True)
    print(f"\n[1] Carregando {ARQUIVO}")
    d = D.preparar(ARQUIVO, fracao_treino=0.7)
    norm = d["norm"]
    print(f"    treino: {len(d['X_treino'])} janelas | teste: {len(d['X_teste'])} janelas")
    print(f"    janela de entrada: {D.JANELA} min | horizonte: {D.HORIZONTE} min")

    y_real = d["serie_real_teste"]
    resultados = {}

    # ---------------- baselines ----------------
    print("\n[2] Baselines")
    for modelo in (baselines.Persistencia(), baselines.MediaMovel(5)):
        t0 = time.perf_counter()
        prev = norm.inverter(modelo.prever(d["X_teste"]))
        t = (time.perf_counter() - t0) * 1000 / len(prev)
        resultados[modelo.nome] = avaliar_modelo(modelo.nome, y_real, prev, t)

    # perfil histórico: usa a posição na semana, não a janela
    ph = baselines.PerfilHistorico()
    serie_treino = norm.inverter(d["X_treino"][:, -1, 0])
    ph.treinar(serie_treino)
    inicio_teste = len(serie_treino) + D.JANELA
    idx = np.arange(inicio_teste, inicio_teste + len(y_real))
    t0 = time.perf_counter()
    prev_ph = ph.prever_por_indice(idx)
    t = (time.perf_counter() - t0) * 1000 / len(prev_ph)
    resultados[ph.nome] = avaliar_modelo(ph.nome, y_real, prev_ph, t)

    # ---------------- redes ----------------
    print("\n[3] Redes recorrentes")
    previsoes = {}
    for bidir in (False, True):
        rede = RegressorLSTM(dim_oculta=30, bidirecional=bidir, semente=42)
        print(f"\n  treinando {rede.nome} ...")
        n_val = int(len(d["X_treino"]) * 0.1)          # 10% finais do treino para validação
        rede.treinar(
            d["X_treino"][:-n_val], d["y_treino"][:-n_val],
            d["X_treino"][-n_val:], d["y_treino"][-n_val:],
            epocas=30, lote=64, taxa=0.01, paciencia=5,
        )
        t0 = time.perf_counter()
        prev = norm.inverter(rede.prever(d["X_teste"]))
        t = (time.perf_counter() - t0) * 1000 / len(prev)
        resultados[rede.nome] = avaliar_modelo(rede.nome, y_real, prev, t)
        previsoes[rede.nome] = prev.ravel()

    # ---------------- da carga para os pods ----------------
    print("\n[4] Decisão de pods (Algoritmo 1: CDT=1 min, RRS=0,60)")
    politica = PoliticaPods(CAPACIDADE_POD, PODS_MIN, PODS_MAX, rrs=0.60, cdt_min=1)

    elasticidade = {}
    serie_pods = {}

    # sem autoscaler: fixo no máximo já usado (pior caso de desperdício)
    fixo = [PODS_MAX] * len(y_real)
    req_fixo = [politica.necessarios(c) for c in y_real]
    elasticidade["Sem autoscaler (fixo no máximo)"] = metricas.elasticidade(req_fixo, fixo)
    serie_pods["Sem autoscaler (fixo no máximo)"] = fixo

    # reativo (imitação do HPA)
    reativa = PoliticaReativa(CAPACIDADE_POD, PODS_MIN, PODS_MAX,
                              alvo_uso=0.70, atraso_min=1, janela_descida=5)
    forn, req, mud = reativa.simular(list(y_real))
    elasticidade["Reativo (tipo HPA)"] = metricas.elasticidade(req, forn)
    elasticidade["Reativo (tipo HPA)"]["mudancas_de_escala"] = mud
    serie_pods["Reativo (tipo HPA)"] = forn

    # preditivos
    for nome, prev in previsoes.items():
        forn, req, mud = politica.simular(list(prev), list(y_real))
        e = metricas.elasticidade(req, forn)
        e["mudancas_de_escala"] = mud
        elasticidade[f"Preditivo ({nome})"] = e
        serie_pods[f"Preditivo ({nome})"] = forn

    base = elasticidade["Sem autoscaler (fixo no máximo)"]
    print(f"\n  {'estratégia':34s} {'faltou':>9s} {'sobrou':>9s} {'t.falta':>9s} {'t.sobra':>9s} {'ganho':>7s}")
    for nome, e in elasticidade.items():
        g = metricas.ganho_elastico(base, e)
        e["ganho_elastico"] = g
        print(f"  {nome:34s} {e['theta_U_%']:8.2f}% {e['theta_O_%']:8.2f}% "
              f"{e['T_U_%']:8.1f}% {e['T_O_%']:8.1f}% {g:7.2f}")

    # ---------------- saída ----------------
    with open(os.path.join(SAIDA, "metricas.json"), "w", encoding="utf-8") as f:
        json.dump({"previsao": resultados, "elasticidade": elasticidade}, f,
                  indent=2, ensure_ascii=False)

    import csv
    with open(os.path.join(SAIDA, "serie_teste.csv"), "w", newline="", encoding="utf-8") as f:
        cols = ["timestamp", "carga_real"] + \
               [f"previsao_{n}" for n in previsoes] + \
               [f"pods_{n}" for n in serie_pods]
        w = csv.writer(f)
        w.writerow(cols)
        for i in range(len(y_real)):
            linha = [d["ts_teste"][i], round(float(y_real[i]), 1)]
            linha += [round(float(previsoes[n][i]), 1) for n in previsoes]
            linha += [serie_pods[n][i] for n in serie_pods]
            w.writerow(linha)

    print(f"\n[5] Salvo em {SAIDA}/metricas.json e {SAIDA}/serie_teste.csv\n")


if __name__ == "__main__":
    main()

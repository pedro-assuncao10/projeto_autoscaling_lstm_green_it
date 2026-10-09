"""Baixa a série de acessos da Wikipédia, por hora, desde jul/2015.

Fonte: API oficial da Wikimedia (Pageviews), agregada — sem baixar logs brutos.
    https://wikimedia.org/api/rest_v1/metrics/pageviews/aggregate/...

Granularidade mínima: 1 HORA. Não serve para prever 10 minutos à frente;
serve para padrões longos (diário, semanal, mensal, anual).

Agentes:
    all-agents — humanos + robôs: é a carga real que o servidor atende
    user       — só humanos

Uso:
    python3 src/baixar_wikipedia.py                         # en.wikipedia, all-agents
    python3 src/baixar_wikipedia.py all-projects user
"""
import csv
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

API = "https://wikimedia.org/api/rest_v1/metrics/pageviews/aggregate"
# A Wikimedia exige User-Agent identificável
UA = {"User-Agent": "dissertacao-ufma-autoscaling/1.0 (pesquisa academica)"}
INICIO = 2015                 # a API só tem dados por hora a partir de 01/07/2015


def baixar_ano(projeto, agente, ano, fim_utc):
    ini = f"{ano}010100" if ano > INICIO else f"{INICIO}070100"
    fim = min(f"{ano}123123", fim_utc)
    url = f"{API}/{projeto}/all-access/{agente}/hourly/{ini}/{fim}"
    for tentativa in range(6):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)["items"]
        except Exception as e:
            espera = 15 * 2 ** tentativa          # 429 = limite da API: esperar cada vez mais
            print(f" erro ({e}), nova tentativa em {espera} s...", end="", flush=True)
            time.sleep(espera)
    raise RuntimeError(f"falhou: {url}")


def main():
    projeto = sys.argv[1] if len(sys.argv) > 1 else "en.wikipedia"
    agente = sys.argv[2] if len(sys.argv) > 2 else "all-agents"
    agora = datetime.now(timezone.utc)
    fim_utc = agora.strftime("%Y%m%d00")
    saida = f"dados/wikipedia_{projeto}_{agente}_1h.csv"

    print(f"Wikipédia ({projeto}, {agente}), por hora:")
    linhas = []
    for ano in range(INICIO, agora.year + 1):
        print(f"  {ano} ...", end="", flush=True)
        itens = baixar_ano(projeto, agente, ano, fim_utc)
        for it in itens:
            t = datetime.strptime(it["timestamp"], "%Y%m%d%H").replace(tzinfo=timezone.utc)
            linhas.append({
                "timestamp": t.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "requests_per_hour": it["views"],
                "requests_per_second": round(it["views"] / 3600.0, 3),
            })
        print(f" {len(itens):,} horas")
        time.sleep(5)                         # educação com a API

    os.makedirs("dados", exist_ok=True)
    with open(saida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)

    v = [l["requests_per_hour"] for l in linhas]
    print(f"\n  {saida}")
    print(f"    período : {linhas[0]['timestamp']} a {linhas[-1]['timestamp']}")
    print(f"    horas   : {len(linhas):,} ({len(linhas)/24/365.25:.1f} anos)")
    print(f"    req/s   : mín={min(v)/3600:.0f} | média={sum(v)/len(v)/3600:.0f} | máx={max(v)/3600:.0f}")


if __name__ == "__main__":
    main()

"""Baixa os traços reais usados pela literatura de autoscaling.

  NASA-HTTP (1995) — logs do Kennedy Space Center, texto (Common Log Format)
  FIFA World Cup (1998) — logs binários de 20 bytes por requisição

Fonte: Internet Traffic Archive (ita.ee.lbl.gov)

Uso:
    python3 src/baixar_tracos.py nasa
    python3 src/baixar_tracos.py fifa 70 71 72      # dias escolhidos
"""
import os
import sys
import urllib.request

BASE = "https://ita.ee.lbl.gov/traces"
DESTINO = "dados/brutos"
UA = {"User-Agent": "Mozilla/5.0 (pesquisa academica; dissertacao UFMA)"}

NASA = [
    ("NASA_access_log_Jul95.gz", f"{BASE}/NASA_access_log_Jul95.gz"),
    ("NASA_access_log_Aug95.gz", f"{BASE}/NASA_access_log_Aug95.gz"),
]


def baixar(nome: str, url: str) -> bool:
    destino = os.path.join(DESTINO, nome)
    if os.path.exists(destino) and os.path.getsize(destino) > 0:
        print(f"  já existe: {nome} ({os.path.getsize(destino)/1e6:.1f} MB)")
        return True
    print(f"  baixando {nome} ...", end="", flush=True)
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=120) as r, open(destino, "wb") as f:
            total = 0
            while True:
                bloco = r.read(1 << 20)
                if not bloco:
                    break
                f.write(bloco)
                total += len(bloco)
        print(f" {total/1e6:.1f} MB")
        return True
    except Exception as e:
        print(f" FALHOU ({e})")
        if os.path.exists(destino):
            os.remove(destino)
        return False


def main():
    os.makedirs(DESTINO, exist_ok=True)
    alvo = sys.argv[1] if len(sys.argv) > 1 else "nasa"

    if alvo == "nasa":
        print("NASA-HTTP 1995:")
        for nome, url in NASA:
            baixar(nome, url)

    elif alvo == "fifa":
        dias = [int(d) for d in sys.argv[2:]] or [70]
        print(f"FIFA World Cup 1998, dias {dias}:")
        for dia in dias:
            parte = 1
            while True:                       # cada dia pode ter várias partes
                nome = f"wc_day{dia}_{parte}.gz"
                if not baixar(nome, f"{BASE}/WorldCup/{nome}"):
                    break
                parte += 1
                if parte > 12:
                    break
    else:
        print(__doc__)


if __name__ == "__main__":
    main()

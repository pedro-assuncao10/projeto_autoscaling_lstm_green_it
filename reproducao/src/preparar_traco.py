"""Converte os traços brutos em série de requisições por minuto.

É o mesmo pré-processamento que a literatura faz: agregar todos os registros do
mesmo minuto num único valor acumulado.

  NASA  — texto em Common Log Format, timestamp entre colchetes
  FIFA  — binário, 20 bytes por requisição (big endian):
          timestamp(4) clientID(4) objectID(4) size(4) method(1) status(1) type(1) server(1)

Uso:
    python3 src/preparar_traco.py nasa  dados/nasa_1min.csv
    python3 src/preparar_traco.py fifa  dados/fifa_1min.csv
"""
import csv
import glob
import gzip
import os
import struct
import sys
from datetime import datetime, timedelta, timezone

BRUTOS = "dados/brutos"
MESES = {m: i + 1 for i, m in enumerate(
    "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}

# Furacão Erin: o servidor da NASA ficou fora do ar neste intervalo.
# Os minutos aqui dentro NÃO são "tráfego zero" — são ausência de medição.
ERIN_INI = datetime(1995, 8, 1, 14, 52, 1, tzinfo=timezone.utc)
ERIN_FIM = datetime(1995, 8, 3, 4, 36, 13, tzinfo=timezone.utc)


def minuto(dt: datetime) -> datetime:
    return dt.replace(second=0, microsecond=0)


def ler_nasa():
    """Devolve {minuto_utc: contagem}. Linhas malformadas são ignoradas."""
    contagem, ignoradas, total = {}, 0, 0
    for caminho in sorted(glob.glob(f"{BRUTOS}/NASA_access_log_*.gz")):
        print(f"  lendo {os.path.basename(caminho)} ...", end="", flush=True)
        n = 0
        with gzip.open(caminho, "rt", encoding="latin-1", errors="ignore") as f:
            for linha in f:
                total += 1
                try:
                    bruto = linha[linha.index("[") + 1:linha.index("]")]
                    data, fuso = bruto.split(" ")
                    d, mes, resto = data.split("/", 2)
                    ano, h, mi, s = resto.split(":")
                    sinal = 1 if fuso[0] == "+" else -1
                    desloc = timedelta(hours=int(fuso[1:3]), minutes=int(fuso[3:5])) * sinal
                    dt = datetime(int(ano), MESES[mes], int(d), int(h), int(mi), int(s),
                                  tzinfo=timezone.utc) - desloc
                except Exception:
                    ignoradas += 1
                    continue
                k = minuto(dt)
                contagem[k] = contagem.get(k, 0) + 1
                n += 1
        print(f" {n:,} requisições")
    print(f"  total: {total:,} linhas | ignoradas: {ignoradas:,}")
    return contagem


def ler_fifa():
    """Lê os arquivos binários. Só o timestamp de cada registro interessa."""
    REG = struct.Struct(">IIIIBBBB")          # 20 bytes por requisição
    contagem, total = {}, 0
    arquivos = sorted(glob.glob(f"{BRUTOS}/wc_day*.gz"),
                      key=lambda p: [int(x) for x in
                                     os.path.basename(p)[6:-3].split("_")])
    if not arquivos:
        print("  nenhum arquivo wc_day*.gz em dados/brutos")
        return contagem
    for caminho in arquivos:
        print(f"  lendo {os.path.basename(caminho)} ...", end="", flush=True)
        n = 0
        with gzip.open(caminho, "rb") as f:
            while True:
                bloco = f.read(REG.size * 50000)
                if not bloco:
                    break
                sobra = len(bloco) % REG.size
                if sobra:
                    bloco += f.read(REG.size - sobra)
                for reg in REG.iter_unpack(bloco):
                    k = minuto(datetime.fromtimestamp(reg[0], tz=timezone.utc))
                    contagem[k] = contagem.get(k, 0) + 1
                    n += 1
        total += n
        print(f" {n:,} requisições")
    print(f"  total: {total:,} requisições")
    return contagem


def gravar(contagem, saida, marcar_erin=False):
    """Preenche a grade completa de minutos (minuto sem registro = 0)."""
    if not contagem:
        print("  nada a gravar")
        return
    ini, fim = min(contagem), max(contagem)
    linhas, zeros, fora = [], 0, 0
    t = ini
    while t <= fim:
        c = contagem.get(t, 0)
        if c == 0:
            zeros += 1
        valido = 1
        if marcar_erin and ERIN_INI <= t <= ERIN_FIM:
            valido = 0
            fora += 1
        linhas.append({
            "timestamp": t.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "requests_per_minute": c,
            "requests_per_second": round(c / 60.0, 3),
            "valido": valido,
        })
        t += timedelta(minutes=1)

    os.makedirs(os.path.dirname(saida) or ".", exist_ok=True)
    with open(saida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)

    valores = [l["requests_per_minute"] for l in linhas if l["valido"]]
    print(f"\n  {saida}")
    print(f"    período : {ini:%Y-%m-%d %H:%M} a {fim:%Y-%m-%d %H:%M} UTC")
    print(f"    minutos : {len(linhas):,} ({len(linhas)/1440:.1f} dias)")
    print(f"    sem registro: {zeros:,} minutos" + (f" | fora do ar (Erin): {fora:,}" if fora else ""))
    print(f"    req/min : mín={min(valores)} | média={sum(valores)/len(valores):.0f} | máx={max(valores)}")


def main():
    qual = sys.argv[1] if len(sys.argv) > 1 else "nasa"
    saida = sys.argv[2] if len(sys.argv) > 2 else f"dados/{qual}_1min.csv"
    print(f"Preparando {qual.upper()}:")
    if qual == "nasa":
        gravar(ler_nasa(), saida, marcar_erin=True)
    elif qual == "fifa":
        gravar(ler_fifa(), saida)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()

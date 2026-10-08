"""Gera uma série sintética de carga, no formato do dataset do projeto.

Imita o que os artigos fazem com os traços NASA/FIFA: uma linha por minuto com o
total de requisições naquele minuto. Aqui a série é gerada, não coletada, para o
projeto poder rodar antes da bancada existir.

Componentes do sinal:
  - ciclo diário  (madrugada baixa, pico comercial)
  - ciclo semanal (fim de semana mais fraco)
  - tendência leve de crescimento
  - rajadas aleatórias (o caso difícil)
  - ruído

Uso: python3 src/gerar_trace.py [semanas] [arquivo_saida]
"""
import csv
import math
import random
import sys
from datetime import datetime, timedelta, timezone

SEED = 42
REQ_BASE = 1200.0       # requisições por minuto no vale
REQ_PICO = 9000.0       # requisições por minuto no pico comercial


def perfil_diario(h: float) -> float:
    """Fator de 0 a 1 conforme a hora do dia (h em horas, pode ser fracionário)."""
    # dois picos: manhã (10h) e tarde (15h), vale de madrugada
    manha = math.exp(-((h - 10.0) ** 2) / (2 * 2.2 ** 2))
    tarde = math.exp(-((h - 15.5) ** 2) / (2 * 2.8 ** 2))
    noite = 0.25 * math.exp(-((h - 21.0) ** 2) / (2 * 1.8 ** 2))
    return min(1.0, manha + 0.9 * tarde + noite)


def perfil_semanal(dia_semana: int) -> float:
    """Segunda=0 ... Domingo=6."""
    return [1.00, 1.03, 1.02, 1.00, 0.95, 0.55, 0.45][dia_semana]


def gerar(semanas: int = 4, saida: str = "dados/trace_sintetico.csv") -> None:
    rnd = random.Random(SEED)
    inicio = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)  # uma segunda-feira
    total_min = semanas * 7 * 24 * 60

    # rajadas: sorteia alguns minutos de início e uma duração curta
    rajadas = {}
    for _ in range(semanas * 6):
        ini = rnd.randrange(total_min)
        dur = rnd.randint(3, 12)
        amp = rnd.uniform(1.6, 3.2)
        for k in range(dur):
            if ini + k < total_min:
                # sobe e desce dentro da rajada
                forma = math.sin(math.pi * (k + 0.5) / dur)
                rajadas[ini + k] = max(rajadas.get(ini + k, 1.0), 1.0 + (amp - 1.0) * forma)

    linhas = []
    for i in range(total_min):
        ts = inicio + timedelta(minutes=i)
        h = ts.hour + ts.minute / 60.0
        base = REQ_BASE + (REQ_PICO - REQ_BASE) * perfil_diario(h)
        base *= perfil_semanal(ts.weekday())
        base *= 1.0 + 0.0009 * (i / (24 * 60))          # tendência de crescimento
        base *= rajadas.get(i, 1.0)                      # rajada, se houver
        base *= rnd.gauss(1.0, 0.06)                     # ruído multiplicativo
        rpm = max(0.0, base)
        linhas.append({
            "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "requests_per_minute": round(rpm, 1),
            "requests_per_second": round(rpm / 60.0, 2),
        })

    with open(saida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)
    print(f"gerado: {saida}  ({len(linhas)} minutos = {semanas} semanas)")


if __name__ == "__main__":
    semanas = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    saida = sys.argv[2] if len(sys.argv) > 2 else "dados/trace_sintetico.csv"
    gerar(semanas, saida)

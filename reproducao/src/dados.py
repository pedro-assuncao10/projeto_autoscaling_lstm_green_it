"""Carrega a série, monta as janelas deslizantes e separa treino/teste."""
import csv
import numpy as np

JANELA = 10       # passos de entrada (últimos 10 minutos) — igual ao artigo
HORIZONTE = 1     # prever 1 passo à frente


def carregar(caminho: str):
    ts, y = [], []
    with open(caminho, encoding="utf-8") as f:
        for linha in csv.DictReader(f):
            ts.append(linha["timestamp"])
            y.append(float(linha["requests_per_minute"]))
    return np.array(ts), np.array(y, dtype=np.float64)


def janelas(serie: np.ndarray, janela: int = JANELA, horizonte: int = HORIZONTE):
    """X[i] = serie[i : i+janela]   ->   y[i] = serie[i+janela+horizonte-1]"""
    n = len(serie) - janela - horizonte + 1
    X = np.empty((n, janela, 1))
    y = np.empty((n, 1))
    for i in range(n):
        X[i, :, 0] = serie[i:i + janela]
        y[i, 0] = serie[i + janela + horizonte - 1]
    return X, y


class Normalizador:
    """Min-max ajustado SÓ no treino (evita vazamento do futuro para o passado)."""

    def __init__(self):
        self.minimo = None
        self.maximo = None

    def ajustar(self, v: np.ndarray):
        self.minimo, self.maximo = float(v.min()), float(v.max())
        return self

    def aplicar(self, v):
        return (v - self.minimo) / (self.maximo - self.minimo)

    def inverter(self, v):
        return v * (self.maximo - self.minimo) + self.minimo


def preparar(caminho: str, fracao_treino: float = 0.7):
    """Divisão TEMPORAL: os primeiros 70% para treino, o resto para teste."""
    ts, serie = carregar(caminho)
    corte = int(len(serie) * fracao_treino)

    norm = Normalizador().ajustar(serie[:corte])
    serie_n = norm.aplicar(serie)

    X, y = janelas(serie_n)
    ts_alvo = ts[JANELA + HORIZONTE - 1:]

    corte_j = corte - JANELA - HORIZONTE + 1
    dados = {
        "X_treino": X[:corte_j], "y_treino": y[:corte_j],
        "X_teste": X[corte_j:], "y_teste": y[corte_j:],
        "ts_teste": ts_alvo[corte_j:],
        "serie_real_teste": serie[JANELA + HORIZONTE - 1:][corte_j:],
        "norm": norm,
    }
    return dados

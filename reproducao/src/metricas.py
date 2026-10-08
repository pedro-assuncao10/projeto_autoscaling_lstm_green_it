"""Métricas de previsão e de elasticidade (SPEC), como nos artigos."""
import numpy as np


def previsao(y_real, y_prev):
    y_real = np.asarray(y_real, dtype=float).ravel()
    y_prev = np.asarray(y_prev, dtype=float).ravel()
    erro = y_real - y_prev
    mse = float(np.mean(erro ** 2))
    mae = float(np.mean(np.abs(erro)))
    denom = np.where(np.abs(y_real) < 1e-9, np.nan, y_real)
    mape = float(np.nanmean(np.abs(erro / denom)) * 100)
    ss_res = float(np.sum(erro ** 2))
    ss_tot = float(np.sum((y_real - y_real.mean()) ** 2))
    return {
        "MSE": mse,
        "RMSE": float(np.sqrt(mse)),
        "MAE": mae,
        "MAPE_%": mape,
        "R2": 1 - ss_res / ss_tot if ss_tot > 0 else float("nan"),
    }


def elasticidade(requerido, fornecido):
    """Métricas do SPEC usadas por Dang-Quang & Yoo (2021).

    requerido[t]: pods que seriam necessários naquele minuto
    fornecido[t]: pods que o autoscaler de fato manteve

    theta_U: quanto faltou (%)      theta_O: quanto sobrou (%)
    T_U: tempo faltando (%)         T_O: tempo sobrando (%)
    Quanto menor, melhor; 0 é o ideal.
    """
    r = np.asarray(requerido, dtype=float)
    p = np.asarray(fornecido, dtype=float)
    T = len(r)
    r_seguro = np.where(r <= 0, np.nan, r)
    theta_u = float(np.nanmean(np.maximum(r - p, 0) / r_seguro) * 100)
    theta_o = float(np.nanmean(np.maximum(p - r, 0) / r_seguro) * 100)
    t_u = float(np.mean(r > p) * 100)
    t_o = float(np.mean(p > r) * 100)
    return {"theta_U_%": theta_u, "theta_O_%": theta_o, "T_U_%": t_u, "T_O_%": t_o}


def ganho_elastico(base, proposta):
    """e_n: média geométrica da razão entre o baseline e a proposta nas 4 métricas.
    Maior que 1 = a proposta é melhor."""
    razoes = []
    for k in ("theta_U_%", "theta_O_%", "T_U_%", "T_O_%"):
        b, p = base[k], proposta[k]
        razoes.append((b + 1e-6) / (p + 1e-6))
    return float(np.prod(razoes) ** (1.0 / len(razoes)))

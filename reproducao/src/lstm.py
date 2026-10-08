"""LSTM implementada do zero em NumPy — forward, backward e Adam.

Sem TensorFlow nem PyTorch: roda com pouca memória e deixa os portões visíveis.
Suporta LSTM simples e Bi-LSTM (duas LSTMs, uma em cada direção), como no artigo
de Dang-Quang & Yoo (2021).

Notação por passo de tempo t:
    z   = x_t · Wx + h_{t-1} · Wh + b          (4H colunas: i, f, o, g)
    i   = sigmoide(z_i)      portão de entrada  — quanto do novo entra
    f   = sigmoide(z_f)      portão de esquecimento — quanto do passado fica
    o   = sigmoide(z_o)      portão de saída     — quanto do estado sai
    g   = tanh(z_g)          candidato a novo conteúdo
    c_t = f ⊙ c_{t-1} + i ⊙ g                   estado da célula (a "memória")
    h_t = o ⊙ tanh(c_t)                         saída do passo
"""
import numpy as np


def sigmoide(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -60, 60)))


class CelulaLSTM:
    """Uma camada LSTM processando uma sequência inteira."""

    def __init__(self, dim_entrada, dim_oculta, rng):
        D, H = dim_entrada, dim_oculta
        escala = 1.0 / np.sqrt(H)
        self.Wx = rng.uniform(-escala, escala, (D, 4 * H))
        self.Wh = rng.uniform(-escala, escala, (H, 4 * H))
        self.b = np.zeros(4 * H)
        self.b[H:2 * H] = 1.0          # viés do portão de esquecimento em 1: ajuda a reter memória no início
        self.H = H

    @property
    def parametros(self):
        return [self.Wx, self.Wh, self.b]

    def frente(self, X):
        """X: (N, T, D) -> h_final (N, H). Guarda o cache para o backward."""
        N, T, _ = X.shape
        H = self.H
        h = np.zeros((N, H))
        c = np.zeros((N, H))
        cache = []
        for t in range(T):
            x = X[:, t, :]
            z = x @ self.Wx + h @ self.Wh + self.b
            i = sigmoide(z[:, 0:H])
            f = sigmoide(z[:, H:2 * H])
            o = sigmoide(z[:, 2 * H:3 * H])
            g = np.tanh(z[:, 3 * H:4 * H])
            c_ant = c
            c = f * c_ant + i * g
            tc = np.tanh(c)
            h = o * tc
            cache.append((x, h, c_ant, i, f, o, g, tc))
        self.cache = cache
        return h

    def tras(self, dh_final):
        """Retropropaga no tempo. dh_final: (N, H) -> gradientes dos parâmetros."""
        H = self.H
        dWx = np.zeros_like(self.Wx)
        dWh = np.zeros_like(self.Wh)
        db = np.zeros_like(self.b)
        dh = dh_final
        dc = np.zeros_like(dh_final)

        for t in reversed(range(len(self.cache))):
            x, h, c_ant, i, f, o, g, tc = self.cache[t]
            do = dh * tc
            dc = dc + dh * o * (1 - tc ** 2)
            di = dc * g
            dg = dc * i
            df = dc * c_ant
            dc_ant = dc * f

            dz = np.concatenate([
                di * i * (1 - i),
                df * f * (1 - f),
                do * o * (1 - o),
                dg * (1 - g ** 2),
            ], axis=1)

            dWx += x.T @ dz
            h_ant = self.cache[t - 1][1] if t > 0 else np.zeros_like(h)
            dWh += h_ant.T @ dz
            db += dz.sum(axis=0)

            dh = dz @ self.Wh.T
            dc = dc_ant

        return [dWx, dWh, db]


class RegressorLSTM:
    """LSTM (ou Bi-LSTM) + camada densa, para prever um valor contínuo."""

    def __init__(self, dim_oculta=30, bidirecional=False, semente=42):
        rng = np.random.default_rng(semente)
        self.bidirecional = bidirecional
        self.frente_cel = CelulaLSTM(1, dim_oculta, rng)
        self.tras_cel = CelulaLSTM(1, dim_oculta, rng) if bidirecional else None
        dim_densa = dim_oculta * (2 if bidirecional else 1)
        escala = 1.0 / np.sqrt(dim_densa)
        self.Wy = rng.uniform(-escala, escala, (dim_densa, 1))
        self.by = np.zeros(1)
        self.nome = "Bi-LSTM" if bidirecional else "LSTM"

    def _params(self):
        p = self.frente_cel.parametros + [self.Wy, self.by]
        if self.bidirecional:
            p = self.frente_cel.parametros + self.tras_cel.parametros + [self.Wy, self.by]
        return p

    def prever(self, X):
        hF = self.frente_cel.frente(X)
        if self.bidirecional:
            hB = self.tras_cel.frente(X[:, ::-1, :])   # mesma sequência, lida de trás para frente
            self.h = np.concatenate([hF, hB], axis=1)
        else:
            self.h = hF
        return self.h @ self.Wy + self.by

    def _gradientes(self, X, y):
        N = X.shape[0]
        yhat = self.prever(X)
        erro = yhat - y
        perda = float(np.mean(erro ** 2))

        dy = (2.0 / N) * erro
        dWy = self.h.T @ dy
        dby = dy.sum(axis=0)
        dh = dy @ self.Wy.T

        H = self.frente_cel.H
        if self.bidirecional:
            gF = self.frente_cel.tras(dh[:, :H])
            gB = self.tras_cel.tras(dh[:, H:])
            grads = gF + gB + [dWy, dby]
        else:
            grads = self.frente_cel.tras(dh) + [dWy, dby]
        return perda, grads

    def treinar(self, X, y, X_val=None, y_val=None, epocas=30, lote=64,
                taxa=0.01, paciencia=5, verbose=True):
        """Adam + parada antecipada pela perda de validação."""
        params = self._params()
        m = [np.zeros_like(p) for p in params]
        v = [np.zeros_like(p) for p in params]
        b1, b2, eps = 0.9, 0.999, 1e-8
        passo = 0
        melhor, melhor_pesos, sem_melhora = np.inf, None, 0
        historico = []

        n = X.shape[0]
        rng = np.random.default_rng(0)
        for ep in range(1, epocas + 1):
            ordem = rng.permutation(n)
            perdas = []
            for ini in range(0, n, lote):
                idx = ordem[ini:ini + lote]
                perda, grads = self._gradientes(X[idx], y[idx])
                perdas.append(perda)
                passo += 1
                for k, (p, g) in enumerate(zip(params, grads)):
                    np.clip(g, -5, 5, out=g)                       # evita explosão de gradiente
                    m[k] = b1 * m[k] + (1 - b1) * g
                    v[k] = b2 * v[k] + (1 - b2) * (g ** 2)
                    mh = m[k] / (1 - b1 ** passo)
                    vh = v[k] / (1 - b2 ** passo)
                    p -= taxa * mh / (np.sqrt(vh) + eps)

            perda_treino = float(np.mean(perdas))
            if X_val is not None:
                perda_val = float(np.mean((self.prever(X_val) - y_val) ** 2))
            else:
                perda_val = perda_treino
            historico.append((ep, perda_treino, perda_val))
            if verbose:
                print(f"  época {ep:3d}  treino={perda_treino:.6f}  val={perda_val:.6f}")

            if perda_val < melhor - 1e-7:
                melhor, sem_melhora = perda_val, 0
                melhor_pesos = [p.copy() for p in params]
            else:
                sem_melhora += 1
                if sem_melhora >= paciencia:
                    if verbose:
                        print(f"  parada antecipada na época {ep} (melhor val={melhor:.6f})")
                    break

        if melhor_pesos is not None:                                # restaura o melhor estado
            for p, melhor_p in zip(params, melhor_pesos):
                p[...] = melhor_p
        return historico

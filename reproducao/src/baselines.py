"""Modelos simples de comparação. A regra do projeto: se o baseline empatar, ele vence."""
import numpy as np


class Persistencia:
    """A próxima carga é igual à atual. O piso mínimo de qualquer previsão."""
    nome = "Persistência"

    def treinar(self, *a, **k):
        return self

    def prever(self, X):
        return X[:, -1, :]          # último valor da janela


class MediaMovel:
    """Média dos últimos k passos da janela."""

    def __init__(self, k=5):
        self.k = k
        self.nome = f"Média móvel ({k})"

    def treinar(self, *a, **k):
        return self

    def prever(self, X):
        return X[:, -self.k:, 0].mean(axis=1, keepdims=True)


class PerfilHistorico:
    """Média histórica do mesmo horário e dia da semana.

    É o concorrente decisivo: equivale ao escalonamento por agenda (cron do KEDA).
    Se a LSTM não vencer este, não há motivo para usar rede neural.
    """
    nome = "Perfil histórico (hora × dia da semana)"

    def __init__(self, passos_por_hora=60):
        self.passos_por_hora = passos_por_hora
        self.tabela = {}
        self.media_geral = 0.0

    def treinar(self, serie_treino, inicio_minuto_semana=0):
        """serie_treino: valores por minuto, em ordem. Indexa por minuto da semana."""
        soma, cont = {}, {}
        for i, v in enumerate(serie_treino):
            chave = (inicio_minuto_semana + i) % (7 * 24 * 60)
            chave //= 15                                  # agrega em blocos de 15 min
            soma[chave] = soma.get(chave, 0.0) + v
            cont[chave] = cont.get(chave, 0) + 1
        self.tabela = {k: soma[k] / cont[k] for k in soma}
        self.media_geral = float(np.mean(serie_treino))
        return self

    def prever_por_indice(self, indices_minuto_semana):
        saida = np.empty((len(indices_minuto_semana), 1))
        for i, mi in enumerate(indices_minuto_semana):
            chave = (mi % (7 * 24 * 60)) // 15
            saida[i, 0] = self.tabela.get(chave, self.media_geral)
        return saida

"""Da carga prevista para o número de pods — Algoritmo 1 de Dang-Quang & Yoo (2021).

    pods(t+1) = ceil( carga_prevista(t+1) / capacidade_do_pod )

    se subir   -> aplica direto
    se descer  -> remove apenas uma FRAÇÃO (RRS) do excedente, para reagir
                  mais rápido se vier uma rajada em seguida
    CDT        -> tempo mínimo entre duas decisões (evita oscilação)
"""
import math


class PoliticaPods:
    def __init__(self, capacidade_pod=500.0, pods_min=10, pods_max=60,
                 rrs=0.60, cdt_min=1):
        self.capacidade_pod = capacidade_pod   # requisições que um pod atende por minuto
        self.pods_min = pods_min
        self.pods_max = pods_max
        self.rrs = rrs                         # fração do excedente que é removida
        self.cdt_min = cdt_min                 # minutos de resfriamento entre decisões

    def necessarios(self, carga):
        """Quantos pods a carga exige (sem nenhuma política)."""
        n = math.ceil(carga / self.capacidade_pod)
        return max(self.pods_min, min(self.pods_max, n))

    def simular(self, carga_prevista, carga_real):
        """Aplica a política minuto a minuto.

        Devolve: pods fornecidos, pods requeridos (pela carga REAL) e nº de mudanças.
        """
        fornecidos, requeridos = [], []
        atual = self.pods_min
        desde_ultima = self.cdt_min
        mudancas = 0

        for prev, real in zip(carga_prevista, carga_real):
            requeridos.append(self.necessarios(real))

            if desde_ultima >= self.cdt_min:
                alvo = self.necessarios(prev)
                if alvo > atual:
                    atual = alvo                                  # sobe direto
                    desde_ultima = 0
                    mudancas += 1
                elif alvo < atual:
                    excedente = math.floor((atual - alvo) * self.rrs)
                    if excedente > 0:
                        atual = max(self.pods_min, atual - excedente)
                        desde_ultima = 0
                        mudancas += 1
            else:
                desde_ultima += 1
            fornecidos.append(atual)

        return fornecidos, requeridos, mudancas


class PoliticaReativa:
    """Imitação simplificada do HPA: só reage depois que a carga real passou do alvo,
    com atraso de leitura e janela de estabilização na descida."""

    def __init__(self, capacidade_pod=500.0, pods_min=10, pods_max=60,
                 alvo_uso=0.70, atraso_min=1, janela_descida=5):
        self.capacidade_pod = capacidade_pod
        self.pods_min = pods_min
        self.pods_max = pods_max
        self.alvo_uso = alvo_uso
        self.atraso_min = atraso_min
        self.janela_descida = janela_descida

    def simular(self, carga_real):
        fornecidos, requeridos = [], []
        atual = self.pods_min
        historico_alvo = []
        mudancas = 0

        for t, real in enumerate(carga_real):
            requeridos.append(max(self.pods_min,
                                  min(self.pods_max, math.ceil(real / self.capacidade_pod))))

            # o HPA só enxerga a carga de alguns minutos atrás
            idx = max(0, t - self.atraso_min)
            observada = carga_real[idx]
            uso = observada / (atual * self.capacidade_pod)
            alvo = max(self.pods_min,
                       min(self.pods_max, math.ceil(atual * uso / self.alvo_uso)))
            historico_alvo.append(alvo)

            if alvo > atual:
                atual = alvo                                       # sobe na hora
                mudancas += 1
            elif alvo < atual:
                janela = historico_alvo[-self.janela_descida:]
                if len(janela) >= self.janela_descida and max(janela) < atual:
                    atual = max(janela)                            # só desce após a janela
                    mudancas += 1
            fornecidos.append(atual)

        return fornecidos, requeridos, mudancas

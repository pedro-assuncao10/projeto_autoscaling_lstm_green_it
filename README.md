# Autoscaling sustentável em Kubernetes para Green IT

Proposta de dissertação de mestrado — PPGCC / UFMA.
Autoscaling preditivo consciente de energia, com adaptação de modelos via *Transfer Learning*.

**Mestrando:** Pedro Assunção · São Luís — MA · 2026

---

## Estrutura

| Pasta | Conteúdo |
|---|---|
| `apresentacao/` | Slides da proposta (fonte, versão local e o gerador) |
| `scripts/` | Scripts de bancada (`.sh`) — diagnóstico e preparo das máquinas |
| `dados/` | Séries temporais geradas (carga × Watts). Os `.csv` não vão para o git |
| `modelos/` | Modelos treinados. Os pesos não vão para o git |
| `controlador/` | O autoscaler preditivo em Python |
| `experimentos/` | Configurações de carga (k6) e resultados das execuções |
| `referencias/` | Bibliografia e material de leitura |

## Apresentação

`apresentacao/apresentacao_local.html` — arquivo único e autônomo, com as fontes
embutidas (funciona sem internet). Abra no navegador e apresente.

- **Navegação:** setas, espaço, Home/End
- **Tela cheia:** tecla `F` ou o botão ⛶ — esconde a barra de endereço
- **PDF:** `Ctrl+P` → paisagem → sai um slide por página

## Bancada

```bash
sudo bash scripts/checar_bancada.sh     # o RAPL funciona nesta máquina?
bash scripts/preparar_server.sh         # simula; --aplicar para valer
```

**Arquitetura do experimento:** o notebook gera carga (k6) e observa (Prometheus +
Grafana); o PC do laboratório é o sistema sob teste (k3s + aplicação + Scaphandre).

### Já verificado

| Máquina | Achado |
|---|---|
| Notebook (AMD Ryzen 7 3700U) | RAPL disponível, mas só `package-0` e `core` — sem domínio `dram`. Chip móvel de 15 W, sujeito a *throttling*. 5,7 GB de RAM. Serve para desenvolver, não para medir |
| PC do laboratório | A verificar com `checar_bancada.sh` |

`energy_uj` tem permissão `0400` (mitigação do PLATYPUS, CVE-2020-8694): a leitura
exige root.

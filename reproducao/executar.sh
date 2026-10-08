#!/usr/bin/env bash
# Roda o experimento completo, do zero.
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo ">> criando ambiente virtual e instalando numpy"
  python3 -m venv .venv
  ./.venv/bin/pip install -q --upgrade pip
  ./.venv/bin/pip install -q -r requirements.txt
fi

[ -f dados/trace_sintetico.csv ] || ./.venv/bin/python src/gerar_trace.py 4 dados/trace_sintetico.csv
./.venv/bin/python src/experimento.py

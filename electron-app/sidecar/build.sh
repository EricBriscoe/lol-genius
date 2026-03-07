#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
pip install pyinstaller xgboost shap numpy pandas
pyinstaller --onefile --name shap_predict shap_predict.py
echo "Built sidecar at dist/shap_predict"

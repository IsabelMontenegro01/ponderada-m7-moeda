"""
Treino do modelo que estima o fechamento do BTC do dia seguinte.

Lê o CSV (date, close, volume), treina, compara com um baseline e salva o
modelo em /models (volume compartilhado com o container do backend).

USO DE IA: a estrutura geral desse arquivo foi gerada pela IA (Claude) para eu
ganhar tempo. Depois eu li e fui entendendo cada parte (comentários abaixo).
"""
import json
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error

DATA_PATH = os.getenv("DATA_PATH", "/data/btc_usd.csv")
MODEL_DIR = os.getenv("MODEL_DIR", "/models")
JANELA = 7  # quantos dias para trás o modelo olha


def montar_dataset(close: np.ndarray):
    """Cada linha = 7 fechamentos seguidos / o último deles. Alvo = amanhã / hoje.

    Divido pelo último preço para o modelo aprender a variação (ex: 1.02 = sobe 2%)
    e não o valor em dólar, porque o BTC mudou muito de escala ao longo dos anos.
    """
    X, y, ultimo = [], [], []
    for t in range(JANELA - 1, len(close) - 1):
        janela = close[t - JANELA + 1 : t + 1]
        X.append(janela / janela[-1])
        y.append(close[t + 1] / close[t])
        ultimo.append(close[t])
    return np.array(X), np.array(y), np.array(ultimo)


def main():
    df = pd.read_csv(DATA_PATH, parse_dates=["date"]).sort_values("date")
    close = df["close"].to_numpy(dtype=float)
    print(f"[treino] {len(df)} linhas, de {df['date'].iloc[0].date()} até {df['date'].iloc[-1].date()}")

    X, y, ultimo = montar_dataset(close)

    # separação cronológica: 80% mais antigo treina, 20% mais recente testa (sem embaralhar)
    corte = int(len(X) * 0.8)
    X_tr, X_te = X[:corte], X[corte:]
    y_tr, y_te = y[:corte], y[corte:]
    ultimo_te = ultimo[corte:]
    preco_real_te = y_te * ultimo_te

    candidatos = {
        "ridge": Ridge(alpha=1.0),
        "random_forest": RandomForestRegressor(n_estimators=200, min_samples_leaf=5, random_state=42, n_jobs=-1),
    }

    # baseline: "amanhã vai ser igual a hoje"
    mae_baseline = mean_absolute_error(preco_real_te, ultimo_te)
    print(f"[treino] baseline (amanhã = hoje): MAE = {mae_baseline:.2f} USD")

    resultados = {}
    for nome, modelo in candidatos.items():
        modelo.fit(X_tr, y_tr)
        pred_preco = modelo.predict(X_te) * ultimo_te
        mae = mean_absolute_error(preco_real_te, pred_preco)
        resultados[nome] = mae
        print(f"[treino] {nome}: MAE = {mae:.2f} USD")

    melhor = min(resultados, key=resultados.get)
    print(f"[treino] melhor modelo: {melhor}")

    # depois de escolher, retreino com TUDO para o modelo final ficar com os dados mais recentes
    modelo_final = candidatos[melhor].fit(X, y)

    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(modelo_final, os.path.join(MODEL_DIR, "modelo_btc.joblib"))
    metadata = {
        "modelo": melhor,
        "janela": JANELA,
        "mae_teste_usd": round(resultados[melhor], 2),
        "mae_baseline_usd": round(mae_baseline, 2),
        "linhas_treino": int(len(X)),
        "ultima_data": str(df["date"].iloc[-1].date()),
    }
    with open(os.path.join(MODEL_DIR, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"[treino] modelo salvo em {MODEL_DIR}/modelo_btc.joblib")


if __name__ == "__main__":
    main()

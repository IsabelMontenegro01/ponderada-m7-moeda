"""
Backend de inferência (FastAPI).

- GET  /health  -> diz se o serviço está de pé e se o modelo carregou
- POST /predict -> recebe os últimos 7 fechamentos e devolve a estimativa de amanhã

USO DE IA: pedi para a IA (Claude) gerar a base da API. Eu escolhi usar FastAPI
porque ele já valida o JSON de entrada e cria uma página de teste sozinho em /docs.
"""
import json
import os
from contextlib import asynccontextmanager

import joblib
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

MODEL_DIR = os.getenv("MODEL_DIR", "/models")
estado = {"modelo": None, "metadata": {}}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # carrega o artefato UMA vez quando o container sobe
    caminho = os.path.join(MODEL_DIR, "modelo_btc.joblib")
    if os.path.exists(caminho):
        estado["modelo"] = joblib.load(caminho)
        with open(os.path.join(MODEL_DIR, "metadata.json")) as f:
            estado["metadata"] = json.load(f)
        print(f"[backend] modelo carregado de {caminho}")
    else:
        print(f"[backend] ATENÇÃO: {caminho} não existe, rode o treino antes")
    yield


app = FastAPI(title="Predição BTC (experimental)", lifespan=lifespan)


class EntradaPredicao(BaseModel):
    ultimos_fechamentos: list[float] = Field(
        ..., description="Fechamentos diários em USD, do mais antigo ao mais recente"
    )


@app.get("/health")
def health():
    return {"status": "ok", "modelo_carregado": estado["modelo"] is not None}


@app.post("/predict")
def predict(entrada: EntradaPredicao):
    if estado["modelo"] is None:
        raise HTTPException(status_code=503, detail="Modelo não carregado. Rode o treino primeiro.")

    janela = estado["metadata"]["janela"]
    precos = entrada.ultimos_fechamentos
    if len(precos) != janela:
        raise HTTPException(status_code=422, detail=f"Envie exatamente {janela} fechamentos.")
    if any(p <= 0 for p in precos):
        raise HTTPException(status_code=422, detail="Os preços precisam ser positivos.")

    # mesma transformação do treino: divide tudo pelo último preço
    ultimo = precos[-1]
    x = [[p / ultimo for p in precos]]
    variacao = float(estado["modelo"].predict(x)[0])

    return {
        "ultimo_fechamento": ultimo,
        "previsao_proximo_fechamento": round(ultimo * variacao, 2),
        "variacao_prevista_pct": round((variacao - 1) * 100, 2),
        "modelo": estado["metadata"]["modelo"],
        "aviso": "Experimental. Não é recomendação de investimento.",
    }

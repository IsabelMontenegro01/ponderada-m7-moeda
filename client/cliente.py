"""
Aplicação cliente: lê os últimos 7 fechamentos do CSV e pede a predição ao backend.

Rodar na minha máquina (só usa biblioteca padrão + csv):
    python client/cliente.py

USO DE IA: pedi para a IA gerar esse cliente simples, para eu ter uma "aplicação"
de verdade além do curl. O que eu entendi: ele pega os 7 últimos preços do CSV,
manda num POST em JSON pro /predict e imprime a resposta.
"""
import csv
import json
import os
import urllib.request

URL = os.getenv("BACKEND_URL", "http://localhost:8000")

with open("data/btc_usd.csv") as f:
    precos = [float(linha["close"]) for linha in csv.DictReader(f)][-7:]

print("Enviando:", precos)

req = urllib.request.Request(
    f"{URL}/predict",
    data=json.dumps({"ultimos_fechamentos": precos}).encode(),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req) as resp:
    print("Resposta:", json.dumps(json.loads(resp.read()), indent=2, ensure_ascii=False))

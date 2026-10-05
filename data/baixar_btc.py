"""
Baixa o histórico diário do BTC-USD no Yahoo Finance e salva em data/btc_usd.csv.

Rodar na minha máquina (não dentro do Docker), só uma vez:
    pip install yfinance pandas
    python data/baixar_btc.py

USO DE IA: pedi para a IA (Claude) escrever esse script para ganhar tempo,
porque eu não lembrava como a yfinance devolve as colunas.
O que eu entendi: ele baixa os preços diários, fica só com data, fechamento e
volume, e salva num CSV simples. Assim o treino não depende de internet.
"""
import yfinance as yf

df = yf.download("BTC-USD", start="2020-01-01", interval="1d", auto_adjust=True, progress=False)

# versões novas da yfinance devolvem colunas com 2 níveis, então achatamos
if hasattr(df.columns, "levels"):
    df.columns = df.columns.get_level_values(0)

df = df[["Close", "Volume"]].dropna().reset_index()
df.columns = ["date", "close", "volume"]
df["date"] = df["date"].dt.strftime("%Y-%m-%d")

df.to_csv("data/btc_usd.csv", index=False)
print(f"salvo data/btc_usd.csv com {len(df)} linhas ({df['date'].iloc[0]} até {df['date'].iloc[-1]})")

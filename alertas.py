import ccxt
import pandas as pd
import numpy as np
import time
from datetime import datetime
import requests
import io
import matplotlib.pyplot as plt
import os

# === VARIABLES DE ENTORNO (Railway) ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SYMBOL = "BTC/USDT"
TIMEFRAME = "5m"
RSI_PERIOD = 14

# === CONEXIÓN BINANCE (pública) ===
exchange = ccxt.bingx({"enableRateLimit": True})

def enviar_alerta(texto, image_bytes=None):
    """Envía texto o imagen al canal de Telegram."""
    if image_bytes:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        files = {"photo": ("grafico.png", image_bytes)}
        data = {"chat_id": CHAT_ID, "caption": texto}
        requests.post(url, files=files, data=data)
    else:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": texto}
        requests.post(url, data=data)

def calcular_rsi(df, period=14):
    """Calcula RSI de 14 periodos."""
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    df["rsi"] = 100 - (100 / (1 + rs))
    return df

def detectar_divergencia(df):
    """Detecta divergencias entre RSI y precio."""
    precio = df["close"]
    rsi = df["rsi"]

    # Puntos recientes
    min_precio = precio.iloc[-3:-1].idxmin()
    max_precio = precio.iloc[-3:-1].idxmax()
    min_rsi = rsi.iloc[-3:-1].idxmin()
    max_rsi = rsi.iloc[-3:-1].idxmax()

    mensaje = None

    # Divergencia alcista
    if precio.iloc[-1] < precio[min_precio] and rsi.iloc[-1] > rsi[min_rsi] and rsi.iloc[-1] < 40:
        mensaje = "🟢 *Divergencia Alcista* detectada (RSI < 40) → posible LONG"
    # Divergencia bajista
    elif precio.iloc[-1] > precio[max_precio] and rsi.iloc[-1] < rsi[max_rsi] and rsi.iloc[-1] > 60:
        mensaje = "🔴 *Divergencia Bajista* detectada (RSI > 60) → posible SHORT"

    return mensaje

def generar_grafico(df):
    """Genera gráfico con RSI y precio."""
    plt.figure(figsize=(10, 5))
    plt.subplot(2, 1, 1)
    plt.plot(df["timestamp"], df["close"], label="Precio", color="gray")
    plt.title(f"{SYMBOL} - Divergencia RSI")
    plt.legend()
    plt.grid()

    plt.subplot(2, 1, 2)
    plt.plot(df["timestamp"], df["rsi"], label="RSI 14", color="orange")
    plt.axhline(40, color="green", linestyle="--")
    plt.axhline(60, color="red", linestyle="--")
    plt.legend()
    plt.grid()

    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png")
    buf.seek(0)
    plt.close()
    return buf

def main():
    print("🚀 Bot de divergencias iniciado...")
    ultima_alerta = None
    while True:
        try:
            velas = exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=200)
            df = pd.DataFrame(velas, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df = calcular_rsi(df, RSI_PERIOD)

            alerta = detectar_divergencia(df)
            if alerta and alerta != ultima_alerta:
                hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                precio_actual = df["close"].iloc[-1]
                mensaje = f"{alerta}\n\n📊 {SYMBOL} | {TIMEFRAME}\n💰 Precio: {precio_actual}\n🕒 {hora}"
                imagen = generar_grafico(df)
                enviar_alerta(mensaje, imagen)
                ultima_alerta = alerta
                print(mensaje)
            else:
                print(f"⏳ {datetime.now()} | Sin divergencias detectadas.")

        except Exception as e:
            print("❌ Error:", e)

        time.sleep(300)  # espera 5 minutos

if __name__ == "__main__":
    main()

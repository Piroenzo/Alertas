import ccxt
import time
import pandas as pd
from datetime import datetime
import requests
import matplotlib.pyplot as plt
import io

# ===== CONFIGURACIÓN =====
API_KEY = "TU_API_KEY_DE_BINGX"
SECRET_KEY = "TU_SECRET_KEY"
TELEGRAM_TOKEN = "TU_TOKEN_TELEGRAM"
CHAT_ID = "TU_CHAT_ID"
SYMBOL = "BTC/USDT"
TIMEFRAME = "5m"
EMA_PERIOD = 12

# ===== CONEXIÓN BINGX =====
exchange = ccxt.bingx({
    "apiKey": API_KEY,
    "secret": SECRET_KEY,
    "enableRateLimit": True
})

# ===== FUNCIONES =====

def enviar_alerta_con_imagen(mensaje, image_bytes):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    files = {'photo': ('grafico.png', image_bytes)}
    data = {'chat_id': CHAT_ID, 'caption': mensaje}
    requests.post(url, files=files, data=data)

def obtener_datos():
    velas = exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=EMA_PERIOD + 50)
    df = pd.DataFrame(velas, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df["ema12"] = df["close"].ewm(span=EMA_PERIOD, adjust=False).mean()
    return df

def detectar_cruce(df):
    cierre_anterior = df["close"].iloc[-2]
    ema_anterior = df["ema12"].iloc[-2]
    cierre_actual = df["close"].iloc[-1]
    ema_actual = df["ema12"].iloc[-1]

    if cierre_anterior < ema_anterior and cierre_actual > ema_actual:
        return "LONG"
    elif cierre_anterior > ema_anterior and cierre_actual < ema_actual:
        return "SHORT"
    else:
        return None

def generar_grafico(df, senal):
    plt.figure(figsize=(10, 5))
    plt.plot(df["timestamp"], df["close"], label="Precio", color="gray")
    plt.plot(df["timestamp"], df["ema12"], label="EMA12", color="orange", linewidth=2)

    # Última vela (cruce)
    x = df["timestamp"].iloc[-1]
    y = df["close"].iloc[-1]

    if senal == "LONG":
        plt.scatter(x, y, color="green", s=100, label="Señal LONG")
    elif senal == "SHORT":
        plt.scatter(x, y, color="red", s=100, label="Señal SHORT")

    plt.title(f"{SYMBOL} | {TIMEFRAME} | Cruce EMA12")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    buffer = io.BytesIO()
    plt.savefig(buffer, format="png")
    buffer.seek(0)
    plt.close()
    return buffer

# ===== LOOP PRINCIPAL =====
def main():
    ultima_senal = None
    while True:
        try:
            df = obtener_datos()
            senal = detectar_cruce(df)
            if senal and senal != ultima_senal:
                precio = df["close"].iloc[-1]
                hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                mensaje = (
                    f"📊 {SYMBOL} | {TIMEFRAME}\n"
                    f"📈 Señal: {senal}\n"
                    f"💰 Precio: {precio:.2f}\n"
                    f"🕒 Hora: {hora}"
                )
                imagen = generar_grafico(df, senal)
                enviar_alerta_con_imagen(mensaje, imagen)
                ultima_senal = senal
                print(f"{hora} -> {mensaje}")
        except Exception as e:
            print("Error:", e)
        time.sleep(60)  # Revisa cada minuto

if __name__ == "__main__":
    main()

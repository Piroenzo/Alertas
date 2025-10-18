import os
import time
import requests
import ccxt
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timezone
from dotenv import load_dotenv
from scipy.signal import argrelextrema
import numpy as np

# ================== CONFIG ==================
SYMBOL = 'BTC/USDT'
TIMEFRAME = '5m'
LIMIT = 300
CSV_PATH = 'divergencias.csv'
TRADINGVIEW_LINK = 'https://www.tradingview.com/chart/?symbol=BINANCE:BTCUSDT&interval=5'
SLEEP_SECONDS = 20

# ================== CREDENCIALES ==================
load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

if not TELEGRAM_TOKEN or not CHAT_ID:
    raise RuntimeError("Faltan TELEGRAM_TOKEN o CHAT_ID en .env")

# ================== EXCHANGE ==================
exchange = ccxt.bingx()

# ================== FUNCIONES TELEGRAM ==================
def enviar_telegram_texto(texto):
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    data = {'chat_id': CHAT_ID, 'text': texto, 'parse_mode': 'HTML'}
    requests.post(url, data=data)

def enviar_telegram_foto(texto, path_imagen):
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto'
    files = {'photo': open(path_imagen, 'rb')}
    data = {'chat_id': CHAT_ID, 'caption': texto, 'parse_mode': 'HTML'}
    requests.post(url, data=data, files=files)

# ================== FUNCIONES AUXILIARES ==================
def fmt_ts(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

def calcular_rsi(series: pd.Series, length=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(length).mean()
    loss = (-delta.clip(upper=0)).rolling(length).mean()
    rs = gain / (loss.replace(0, 1e-10))
    return 100 - (100 / (1 + rs))

def obtener_df():
    ohlcv = exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=LIMIT)
    df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
    df['rsi'] = calcular_rsi(df['close'])
    return df.dropna()

def detectar_divergencia_real(df, order=5):
    """Detecta divergencias RSI reales tipo visual (Bull/Bear)."""
    close = df['close'].values
    rsi = df['rsi'].values

    # Encuentra los últimos 2 mínimos y máximos locales
    lows = argrelextrema(close, np.less_equal, order=order)[0]
    highs = argrelextrema(close, np.greater_equal, order=order)[0]

    tipo = None
    idx1 = idx2 = None

    # --- Divergencia alcista (Bull): precio hace mínimo más bajo, RSI sube ---
    if len(lows) >= 2:
        idx1, idx2 = lows[-2], lows[-1]
        if close[idx2] < close[idx1] and rsi[idx2] > rsi[idx1]:
            tipo = "Bullish"

    # --- Divergencia bajista (Bear): precio hace máximo más alto, RSI baja ---
    if len(highs) >= 2:
        h1, h2 = highs[-2], highs[-1]
        if close[h2] > close[h1] and rsi[h2] < rsi[h1]:
            tipo = "Bearish"
            idx1, idx2 = h1, h2

    return tipo, idx1, idx2

def graficar_divergencia_real(df, tipo, idx1, idx2):
    close = df['close']
    rsi = df['rsi']
    color = 'green' if tipo == "Bullish" else 'red'
    label = 'Bull' if tipo == "Bullish" else 'Bear'

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    fig.suptitle(f"Divergencia {label} en {SYMBOL} ({TIMEFRAME})", fontsize=12, fontweight='bold')

    # --- Precio ---
    ax1.plot(close, color='orange', label='Precio')
    ax1.plot([idx1, idx2], [close.iloc[idx1], close.iloc[idx2]], color=color, linestyle='--', linewidth=2)
    ax1.text(idx2, close.iloc[idx2], label, color='white', fontsize=9,
             bbox=dict(facecolor=color, alpha=0.8, boxstyle="round,pad=0.3"))
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='upper left')

    # --- RSI ---
    ax2.plot(rsi, color='blue', label='RSI (14)')
    ax2.plot([idx1, idx2], [rsi.iloc[idx1], rsi.iloc[idx2]], color=color, linewidth=2)
    ax2.axhline(70, color='red', linestyle='--', linewidth=0.8)
    ax2.axhline(30, color='green', linestyle='--', linewidth=0.8)
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='upper left')
    plt.tight_layout()

    path = 'grafico.png'
    plt.savefig(path)
    plt.close(fig)
    return path

def guardar_csv(data):
    df = pd.DataFrame([data])
    header = not os.path.exists(CSV_PATH)
    df.to_csv(CSV_PATH, mode='a', header=header, index=False)

# ================== LOOP PRINCIPAL ==================
def main():
    enviar_telegram_texto(f"🤖 Bot de divergencias RSI reales iniciado — monitoreando <b>{SYMBOL}</b> ({TIMEFRAME})")
    last_signal_time = None

    while True:
        try:
            df = obtener_df()
            tipo, idx1, idx2 = detectar_divergencia_real(df)

            if tipo and (last_signal_time != df.iloc[idx2]['time']):
                hora = fmt_ts(df.iloc[idx2]['time'])
                precio = df.iloc[idx2]['close']
                rsi_val = df.iloc[idx2]['rsi']

                path_img = graficar_divergencia_real(df, tipo, idx1, idx2)
                mensaje = (
                    f"{'📈' if tipo == 'Bullish' else '📉'} Divergencia RSI {tipo} detectada en <b>{SYMBOL}</b>\n"
                    f"🕒 {hora}\n"
                    f"💰 Precio: <b>{precio:.2f}</b>\n"
                    f"🧪 RSI: <b>{rsi_val:.1f}</b>\n"
                    f"🔗 <a href='{TRADINGVIEW_LINK}'>Ver en TradingView</a>"
                )

                enviar_telegram_foto(mensaje, path_img)
                guardar_csv({
                    'timestamp_utc': hora,
                    'symbol': SYMBOL,
                    'timeframe': TIMEFRAME,
                    'tipo': tipo,
                    'precio': round(float(precio), 2),
                    'rsi': round(float(rsi_val), 2)
                })
                print(f"[ALERTA] Divergencia {tipo} enviada.")
                last_signal_time = df.iloc[idx2]['time']

            time.sleep(SLEEP_SECONDS)

        except Exception as e:
            print(f"[ERROR] {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()

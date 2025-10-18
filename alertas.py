import os
import time
import requests
import threading
import ccxt
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timezone
from dotenv import load_dotenv

# ================== CONFIG ==================
SYMBOL = 'BTC/USDT'
TIMEFRAME = '5m'
LIMIT = 200
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
    df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    df['rsi'] = calcular_rsi(df['close'])
    return df.dropna()

def detectar_divergencia_rsi(df, lookback=5):
    close = df['close']
    rsi = df['rsi']

    max_price_prev = close.iloc[-(lookback+1):-1].max()
    min_price_prev = close.iloc[-(lookback+1):-1].min()
    max_rsi_prev = rsi.iloc[-(lookback+1):-1].max()
    min_rsi_prev = rsi.iloc[-(lookback+1):-1].min()
    last_price = close.iloc[-1]
    last_rsi = rsi.iloc[-1]

    div_bajista = (last_price > max_price_prev) and (last_rsi < max_rsi_prev)
    div_alcista = (last_price < min_price_prev) and (last_rsi > min_rsi_prev)
    return div_alcista, div_bajista

def graficar_divergencia(df, tipo):
    plt.figure(figsize=(8, 5))
    plt.title(f'{tipo} en {SYMBOL} ({TIMEFRAME})')
    plt.plot(df['close'], label='Precio', color='orange')
    plt.ylabel('Precio')
    plt.twinx()
    plt.plot(df['rsi'], label='RSI', color='blue', alpha=0.7)
    plt.axhline(70, color='red', linestyle='--', linewidth=0.8)
    plt.axhline(30, color='green', linestyle='--', linewidth=0.8)
    plt.legend(loc='upper left')
    plt.tight_layout()
    path = 'grafico.png'
    plt.savefig(path)
    plt.close()
    return path

def guardar_csv(data):
    df = pd.DataFrame([data])
    header = not os.path.exists(CSV_PATH)
    df.to_csv(CSV_PATH, mode='a', header=header, index=False)

# ================== LOOP PRINCIPAL ==================
def main():
    enviar_telegram_texto(f"🤖 Bot de divergencias iniciado — monitoreando <b>{SYMBOL}</b> ({TIMEFRAME})")
    last_candle = None

    while True:
        try:
            df = obtener_df()
            current_time = int(df.iloc[-1]['time'])

            if last_candle is None:
                last_candle = current_time
            elif current_time != last_candle:
                div_alcista, div_bajista = detectar_divergencia_rsi(df)
                if div_alcista or div_bajista:
                    tipo = "📈 Divergencia RSI Alcista" if div_alcista else "📉 Divergencia RSI Bajista"
                    precio = df.iloc[-1]['close']
                    hora = fmt_ts(current_time)
                    rsi = df.iloc[-1]['rsi']

                    path_img = graficar_divergencia(df, tipo)
                    mensaje = (
                        f"{tipo} detectada en <b>{SYMBOL}</b>\n"
                        f"🕒 {hora}\n"
                        f"💰 Precio: <b>{precio:.2f}</b>\n"
                        f"🧪 RSI: <b>{rsi:.1f}</b>\n"
                        f"🔗 <a href='{TRADINGVIEW_LINK}'>Ver en TradingView</a>"
                    )

                    enviar_telegram_foto(mensaje, path_img)
                    guardar_csv({
                        'timestamp_utc': hora,
                        'symbol': SYMBOL,
                        'timeframe': TIMEFRAME,
                        'tipo': tipo,
                        'precio': round(float(precio), 2),
                        'rsi': round(float(rsi), 2)
                    })
                    print(f"[ALERTA] {tipo} enviada a Telegram")

                last_candle = current_time

            time.sleep(SLEEP_SECONDS)

        except Exception as e:
            print(f"[ERROR] {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()

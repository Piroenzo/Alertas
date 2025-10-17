import time
import os
import requests
import threading
import ccxt
import pandas as pd
from datetime import datetime, timezone
from dotenv import load_dotenv

# ================== CONFIG ==================
SYMBOL = 'BTC/USDT'
TIMEFRAME = '5m'
LIMIT = 500
TOL_PIVOTE = 0.002
CSV_PATH = 'senales.csv'
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
def enviar_telegram(texto: str):
    try:
        url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
        data = {'chat_id': CHAT_ID, 'text': texto, 'parse_mode': 'HTML', 'disable_web_page_preview': True}
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"[WARN] Error enviando Telegram: {e}")

def escuchar_comandos():
    """Hilo que revisa mensajes entrantes para comandos como /status"""
    print("[INFO] Escuchando comandos de Telegram...")
    last_update_id = None
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates'

    while True:
        try:
            params = {'timeout': 10, 'offset': last_update_id}
            response = requests.get(url, params=params, timeout=20)
            data = response.json()

            if 'result' in data and len(data['result']) > 0:
                for update in data['result']:
                    last_update_id = update['update_id'] + 1
                    message = update.get('message', {})
                    text = message.get('text', '')
                    chat_id = str(message.get('chat', {}).get('id'))

                    # Solo responde a tu chat
                    if chat_id == CHAT_ID:
                        if text.lower() == '/status':
                            enviar_telegram(f"✅ El bot está activo y monitoreando <b>{SYMBOL}</b> ({TIMEFRAME})")

            time.sleep(3)

        except Exception as e:
            print(f"[ERROR][Comandos] {e}")
            time.sleep(5)

# ================== FUNCIONES DE ESTRATEGIA ==================
def fmt_ts(ms):
    return datetime.fromtimestamp(ms/1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

def calcular_ema(series: pd.Series, length=12):
    return series.ewm(span=length, adjust=False).mean()

def calcular_rsi(series: pd.Series, length=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(length).mean()
    loss = (-delta.clip(upper=0)).rolling(length).mean()
    rs = gain / (loss.replace(0, 1e-10))
    return 100 - (100 / (1 + rs))

def calcular_pivote(prev_high, prev_low, prev_close):
    return (prev_high + prev_low + prev_close) / 3.0

def vela_traspasa_ema12(prev_close, prev_ema, last_close, last_ema):
    long_break = (prev_close < prev_ema) and (last_close > last_ema)
    short_break = (prev_close > prev_ema) and (last_close < last_ema)
    return long_break, short_break

def detectar_divergencia_rsi(df: pd.DataFrame, lookback_swings=5):
    close = df['close']
    rsi = df['rsi']
    max_price_prev = close.iloc[-(lookback_swings+1):-1].max()
    min_price_prev = close.iloc[-(lookback_swings+1):-1].min()
    max_rsi_prev = rsi.iloc[-(lookback_swings+1):-1].max()
    min_rsi_prev = rsi.iloc[-(lookback_swings+1):-1].min()
    last_price = close.iloc[-1]
    last_rsi = rsi.iloc[-1]
    div_bajista = (last_price > max_price_prev) and (last_rsi < max_rsi_prev)
    div_alcista = (last_price < min_price_prev) and (last_rsi > min_rsi_prev)
    return div_alcista, div_bajista

def cerca_de_pivote(price, pivot, tol=TOL_PIVOTE):
    return abs(price - pivot) / pivot <= tol

def guardar_csv(row: dict, path=CSV_PATH):
    df = pd.DataFrame([row])
    header = not os.path.exists(path)
    df.to_csv(path, mode='a', header=header, index=False)

def obtener_df():
    ohlcv = exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=LIMIT)
    df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
    df['ema12'] = calcular_ema(df['close'], 12)
    df['rsi'] = calcular_rsi(df['close'], 14)
    return df

def evaluar_y_alertar(df: pd.DataFrame):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    pivot = calcular_pivote(prev['high'], prev['low'], prev['close'])
    toca_pivote = cerca_de_pivote(last['close'], pivot)
    long_break, short_break = vela_traspasa_ema12(prev['close'], prev['ema12'], last['close'], last['ema12'])
    div_alcista, div_bajista = detectar_divergencia_rsi(df)
    señal_long = long_break and div_alcista and toca_pivote
    señal_short = short_break and div_bajista and toca_pivote

    if señal_long or señal_short:
        tipo = "LONG" if señal_long else "SHORT"
        msg = (
            f"⚡ <b>Señal {tipo}</b> en <b>{SYMBOL}</b> ({TIMEFRAME})\n"
            f"🕒 {fmt_ts(int(last['time']))}\n"
            f"💰 Precio: <b>{last['close']:.2f}</b>\n"
            f"📈 EMA12: <b>{last['ema12']:.2f}</b>\n"
            f"🎯 Pivote: <b>{pivot:.2f}</b>\n"
            f"🧪 RSI(14): <b>{last['rsi']:.1f}</b>\n"
            f"🔗 <a href=\"{TRADINGVIEW_LINK}\">Ver en TradingView</a>"
        )
        enviar_telegram(msg)

        guardar_csv({
            'timestamp_utc': fmt_ts(int(last['time'])),
            'symbol': SYMBOL,
            'timeframe': TIMEFRAME,
            'tipo': tipo,
            'price': round(float(last['close']), 2),
            'ema12': round(float(last['ema12']), 2),
            'pivot': round(float(pivot), 2),
            'rsi': round(float(last['rsi']), 2)
        })

# ================== LOOP PRINCIPAL ==================
def main():
    print(f"[INFO] Bot iniciado para {SYMBOL} ({TIMEFRAME})")
    enviar_telegram(f"🤖 Bot de señales iniciado correctamente — Monitoreando {SYMBOL} ({TIMEFRAME})")

    # Hilo para escuchar comandos
    hilo_comandos = threading.Thread(target=escuchar_comandos, daemon=True)
    hilo_comandos.start()

    last_candle_time = None

    while True:
        try:
            df = obtener_df()
            current_last_time = int(df.iloc[-1]['time'])

            if last_candle_time is None:
                last_candle_time = current_last_time
                print(f"[SYNC] Última vela: {fmt_ts(current_last_time)}")
            elif current_last_time != last_candle_time:
                print(f"[NEW] Nueva vela: {fmt_ts(current_last_time)} — evaluando...")
                evaluar_y_alertar(df)
                last_candle_time = current_last_time

            time.sleep(SLEEP_SECONDS)
        except Exception as e:
            print(f"[ERROR] {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()

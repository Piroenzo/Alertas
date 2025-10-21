from flask import Flask, request
import requests
from datetime import datetime

app = Flask(__name__)

# === CONFIGURACIÓN TELEGRAM ===
TELEGRAM_TOKEN = "TU_TOKEN_TELEGRAM"
CHAT_ID = "TU_CHAT_ID"

@app.route('/')
def home():
    return "✅ Bot de alertas TradingView funcionando."

@app.route('/alerta', methods=['POST'])
def alerta():
    try:
        data = request.get_json(force=True)
        symbol = data.get("symbol", "DESCONOCIDO")
        interval = data.get("interval", "5m")
        tipo = data.get("type", "N/A")
        precio = data.get("price", "N/A")
        hora = data.get("time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        mensaje = (
            f"📊 {symbol} | {interval}\n"
            f"📈 Señal: {tipo}\n"
            f"💰 Precio: {precio}\n"
            f"🕒 Hora: {hora}"
        )

        telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(telegram_url, data={"chat_id": CHAT_ID, "text": mensaje})
        print("✅ Alerta enviada a Telegram:", mensaje)
        return {"status": "ok"}, 200

    except Exception as e:
        print("❌ Error:", e)
        return {"status": "error", "message": str(e)}, 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

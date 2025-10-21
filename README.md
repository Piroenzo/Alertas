# 📊 Bot de Divergencias RSI (5m)

Detecta divergencias entre RSI 14 y el precio de BTC/USDT (5 min).
Envía alertas por Telegram:

- RSI < 40 → posible LONG
- RSI > 60 → posible SHORT

## 🚀 Despliegue en Railway

1. Subir a GitHub
2. Crear nuevo proyecto en [Railway.app](https://railway.app) → Deploy from GitHub
3. Agregar variables de entorno:
   - `TELEGRAM_TOKEN`
   - `CHAT_ID`
4. Railway correrá automáticamente el bot 24/7.

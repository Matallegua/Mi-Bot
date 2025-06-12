from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import requests

# Función que obtiene el precio de Bitcoin desde CoinGecko
def obtener_precio_btc():
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
    respuesta = requests.get(url)
    datos = respuesta.json()
    precio = datos["bitcoin"]["usd"]
    return precio

# Comando /precio_btc
async def precio_btc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    precio = obtener_precio_btc()
    await update.message.reply_text(f"El precio actual de Bitcoin es: ${precio} USD")

# Configuración del bot
app = ApplicationBuilder().token("7959655718:AAF4CUM1fVy45bNzqqNWarJdnDacpEGBtXk").build()

# Añadir comando
app.add_handler(CommandHandler("precio_btc", precio_btc))

# Ejecutar el bot
app.run_polling()
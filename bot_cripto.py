import logging
import json
import sqlite3
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes
)
from apscheduler.schedulers.background import BackgroundScheduler

# Configura el logging
logging.basicConfig(level=logging.INFO)

# Configura el token y admin
TOKEN = "7959655718:AAF4CUM1fVy45bNzqqNWarJdnDacpEGBtXk"
ID_ADMIN =  8121853765  # Reemplaza con tu user ID numérico

# ---------------------------- FUNCIONES DE APOYO ----------------------------

def obtener_precio(moneda):
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={moneda}&vs_currencies=usd"
    respuesta = requests.get(url)
    if respuesta.ok:
        datos = respuesta.json()
        return datos.get(moneda, {}).get("usd")
    return None

def es_admin(update):
    return update.effective_user.id == ID_ADMIN

def obtener_usuario_premium(user_id):
    try:
        with open("usuarios.json", "r") as f:
            datos = json.load(f)
        return datos.get(str(user_id))
    except (FileNotFoundError, json.JSONDecodeError):
        return None

# ---------------------------- COMANDOS USUARIO ----------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "¡Hola! Soy tu bot de criptomonedas.\n"
        "Usa /precio <moneda>\n"
        "Usa /alerta <cripto> <arriba/abajo> <precio>\n"
        "Usa /mis_alertas\n"
        "Usa /soporte si eres premium\n"
        "Usa /suscribirme para planes\n"
        "Usa /miid para saber tu ID"
    )

async def precio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /precio <moneda>")
        return

    moneda = context.args[0].lower()
    precio_actual = obtener_precio(moneda)
    if precio_actual:
        await update.message.reply_text(f"💰 {moneda.upper()}: ${precio_actual}")
    else:
        await update.message.reply_text("⚠️ Moneda no encontrada.")

async def alerta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    nivel = obtener_usuario_premium(user_id)
    if not nivel:
        await update.message.reply_text("⚠️ No tienes un plan activo. Usa /suscribirme para más funciones.")
        return

    if len(context.args) != 3:
        await update.message.reply_text("Uso: /alerta <cripto> <arriba/abajo> <precio>")
        return

    cripto, condicion, precio_str = context.args
    try:
        precio = float(precio_str)
    except ValueError:
        await update.message.reply_text("⚠️ Precio inválido.")
        return

    if condicion not in ["arriba", "abajo"]:
        await update.message.reply_text("⚠️ Condición inválida. Usa 'arriba' o 'abajo'.")
        return

    conn = sqlite3.connect("alertas.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS alertas (
        user_id INTEGER, cripto TEXT, condicion TEXT, precio REAL)''')
    cursor.execute("INSERT INTO alertas VALUES (?, ?, ?, ?)", (user_id, cripto.lower(), condicion, precio))
    conn.commit()
    conn.close()

    await update.message.reply_text("✅ Alerta guardada.")

async def mis_alertas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect("alertas.db")
    cursor = conn.cursor()
    cursor.execute("SELECT cripto, condicion, precio FROM alertas WHERE user_id=?", (user_id,))
    filas = cursor.fetchall()
    conn.close()

    if not filas:
        await update.message.reply_text("📭 No tienes alertas guardadas.")
    else:
        mensaje = "📌 Tus alertas:\n"
        for cripto, condicion, precio in filas:
            mensaje += f"• {cripto.upper()} {condicion} ${precio}\n"
        await update.message.reply_text(mensaje)

async def soporte(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nivel = obtener_usuario_premium(update.effective_user.id)
    if nivel:
        await update.message.reply_text("🛠️ Soporte Premium: Envíanos un mensaje con tu duda.")
    else:
        await update.message.reply_text("⚠️ Esta función es solo para usuarios premium.")

async def suscribirme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💳 Planes disponibles:\n"
        "1️⃣ Básico: Acceso a alertas personalizadas.\n"
        "2️⃣ VIP: Soporte, más criptos, alertas instantáneas.\n"
        "Contáctanos para activar tu plan."
    )

async def mi_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🆔 Tu ID es: {update.effective_user.id}")

# ---------------------------- COMANDO ADMIN ----------------------------

async def set_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not es_admin(update):
        await update.message.reply_text("🚫 No tienes permiso.")
        return

    if len(context.args) != 2:
        await update.message.reply_text("Uso: /setpremium <user_id> <nivel>\nNivel: 1=básico, 2=VIP")
        return

    try:
        user_id = int(context.args[0])
        nivel = int(context.args[1])

        if nivel not in [1, 2]:
            await update.message.reply_text("❌ Nivel inválido. Usa 1 (básico) o 2 (VIP).")
            return

        # Guardar en base de datos
        conn = sqlite3.connect("alertas.db")
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (
            user_id INTEGER PRIMARY KEY, es_premium INTEGER, fecha_registro TEXT)''')
        cursor.execute("INSERT OR REPLACE INTO usuarios (user_id, es_premium, fecha_registro) VALUES (?, 1, date('now'))", (user_id,))
        conn.commit()
        conn.close()

        # Guardar en JSON
        nivel_texto = "basico" if nivel == 1 else "vip"
        try:
            with open("usuarios.json", "r") as f:
                usuarios = json.load(f)
        except FileNotFoundError:
            usuarios = {}

        usuarios[str(user_id)] = nivel_texto

        with open("usuarios.json", "w") as f:
            json.dump(usuarios, f, indent=4)

        await update.message.reply_text(f"✅ Usuario {user_id} ahora es '{nivel_texto.upper()}'.")
    except Exception as e:
        logging.error(f"Error en set_premium: {e}")
        await update.message.reply_text("⚠️ Error al establecer el plan.")

# ---------------------------- FUNCIONES DE CHEQUEO ----------------------------

def verificar_alertas():
    try:
        conn = sqlite3.connect("alertas.db")
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, cripto, condicion, precio FROM alertas")
        alertas = cursor.fetchall()
        conn.close()

        for user_id, cripto, condicion, precio in alertas:
            actual = obtener_precio(cripto)
            if actual is None:
                continue

            if (condicion == "arriba" and actual > precio) or (condicion == "abajo" and actual < precio):
                app.bot.send_message(chat_id=user_id, text=f"📢 {cripto.upper()} está {condicion} ${precio} (actual: ${actual})")
    except Exception as e:
        logging.error(f"Error al verificar alertas: {e}")

# ---------------------------- INICIO DEL BOT ----------------------------

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("precio", precio))
app.add_handler(CommandHandler("alerta", alerta))
app.add_handler(CommandHandler("mis_alertas", mis_alertas))
app.add_handler(CommandHandler("soporte", soporte))
app.add_handler(CommandHandler("suscribirme", suscribirme))
app.add_handler(CommandHandler("miid", mi_id))
app.add_handler(CommandHandler("setpremium", set_premium))

# Programar verificación cada 60 segundos
scheduler = BackgroundScheduler()
scheduler.add_job(lambda: verificar_alertas(), "interval", seconds=60)
scheduler.start()

print("Bot iniciado y escuchando comandos...")
app.run_polling()
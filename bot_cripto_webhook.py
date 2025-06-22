import logging
import sqlite3
import requests
import os
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Configuración Logging
logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN") or "7959655718:AAF4CUM1fVy45bNzqqNWarJdnDacpEGBtXk"
ID_ADMIN = int(os.getenv("BOT_ADMIN_ID") or "8121853765")

# Conexión a BD
conn = sqlite3.connect("usuarios.db", check_same_thread=False)
c = conn.cursor()

# Crear tablas si no existen
c.execute("""
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY,
    nivel TEXT DEFAULT 'free',
    vence TEXT,
    idioma TEXT DEFAULT 'es',
    referido_por INTEGER
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS alertas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    cripto TEXT,
    precio REAL,
    direccion TEXT,
    enviada INTEGER DEFAULT 0
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS logs (
    user_id INTEGER,
    comando TEXT,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS faq (
    pregunta TEXT,
    respuesta TEXT
)
""")

# Nueva tabla para pagos manuales
c.execute("""
CREATE TABLE IF NOT EXISTS pagos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    monto REAL,
    referencia TEXT,
    confirmado INTEGER DEFAULT 0,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()

# Mensajes multilenguaje
MENSAJES = {
    "es": {
        "inicio": "👋 ¡Hola! Usa /precio <moneda>, /alerta <cripto> <arriba|abajo> <precio>, /mis_alertas, /soporte, /suscribirme, /miid, /historial, /faq",
        "bienvenida": "🎉 ¡Bienvenido! Cuenta registrada.",
        "precio_actual": "💱 Precio de {cripto}: ${precio}",
        "alerta_creada": "✅ Alerta creada para {cripto} cuando esté {direccion} de {precio}",
        "alerta_borrada": "✅ Alerta eliminada para {cripto}",
        "sin_alertas": "🔕 No tienes alertas activas.",
        "no_autorizado": "❌ No autorizado.",
        "idioma_invalido": "❌ Idioma inválido.",
        "idioma_actualizado": "✅ Idioma actualizado.",
        "soporte": "📟 Contacta soporte: @SoporteUsuario",
        "error": "❌ Ocurrió un error, intenta más tarde.",
        "id_usuario": "Tu ID es: {user_id}",
        "historial_vacio": "📬 No tienes historial de alertas.",
        "faq_sin_preguntas": "No hay preguntas frecuentes.",
        "faq_intro": "❓ Preguntas Frecuentes:\n",
        "referral_bienvenida": "🎉 Fuiste referido por {ref_id}. ¡Gracias!",
        "referido_registrado": "✅ Tienes {count} referido(s).",
        "plan_info": "💳 Planes:\n1 mes premium - 5 USD (no implementado)\nUsa /suscribirme para info.",
        "pago_registrado": "✅ Pago registrado. Envía la referencia y monto con /confirmarpago <monto> <referencia>.",
        "pago_recibido": "✅ Tu pago de {monto}€ con referencia '{referencia}' ha sido registrado y será verificado.",
        "pago_confirmado": "✅ Pago confirmado. Ahora eres PREMIUM.",
        "pago_no_encontrado": "❌ No se encontró el pago con esa referencia.",
        "pago_ya_confirmado": "❌ Este pago ya fue confirmado.",
        "uso_confirmarpago": "Uso: /confirmarpago <monto> <referencia>",
        "uso_confirmar_pago": "Uso: /confirmar_pago <referencia>",
        "solo_premium": "❌ Esta función es solo para usuarios PREMIUM. Usa /suscribirme para más info."
    },
    "en": {
        "inicio": "👋 Hello! Use /precio <coin>, /alerta <crypto> <above|below> <price>, /mis_alertas, /soporte, /suscribirme, /miid, /historial, /faq",
        "bienvenida": "🎉 Welcome! Account registered.",
        "precio_actual": "💱 Price of {cripto}: ${precio}",
        "alerta_creada": "✅ Alert set for {cripto} when {direccion} {precio}",
        "alerta_borrada": "✅ Alert deleted for {cripto}",
        "sin_alertas": "🔕 No active alerts.",
        "no_autorizado": "❌ Unauthorized.",
        "idioma_invalido": "❌ Invalid language.",
        "idioma_actualizado": "✅ Language updated.",
        "soporte": "📟 Contact support: @SupportUser",
        "error": "❌ An error occurred, try later.",
        "id_usuario": "Your ID is: {user_id}",
        "historial_vacio": "📬 No alert history.",
        "faq_sin_preguntas": "No FAQs.",
        "faq_intro": "❓ FAQs:\n",
        "referral_bienvenida": "🎉 Referred by {ref_id}. Thanks!",
        "referido_registrado": "✅ You have {count} referral(s).",
        "plan_info": "💳 Plans:\n1 month premium - 5 USD (not implemented)\nUse /suscribirme for info.",
        "pago_registrado": "✅ Payment registered. Send reference and amount with /confirmarpago <amount> <reference>.",
        "pago_recibido": "✅ Your payment of {monto}€ with reference '{referencia}' has been registered and will be verified.",
        "pago_confirmado": "✅ Payment confirmed. You are now PREMIUM.",
        "pago_no_encontrado": "❌ Payment with that reference not found.",
        "pago_ya_confirmado": "❌ This payment was already confirmed.",
        "uso_confirmarpago": "Usage: /confirmarpago <amount> <reference>",
        "uso_confirmar_pago": "Usage: /confirmar_pago <reference>",
        "solo_premium": "❌ This feature is for PREMIUM users only. Use /suscribirme for info."
    }
}

# --- Funciones utilitarias ---

def obtener_idioma(user_id):
    c.execute("SELECT idioma FROM usuarios WHERE id = ?", (user_id,))
    result = c.fetchone()
    return result[0] if result else 'es'

def registrar_usuario(user_id, referido_por=None):
    c.execute("SELECT * FROM usuarios WHERE id = ?", (user_id,))
    if c.fetchone() is None:
        c.execute("INSERT INTO usuarios (id, referido_por) VALUES (?, ?)", (user_id, referido_por))
        conn.commit()
        return True
    return False

async def enviar_mensaje(update: Update, texto: str):
    try:
        await update.message.reply_text(texto)
    except Exception as e:
        logging.error(f"Error enviando mensaje: {e}")

def obtener_precio_cripto(cripto):
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={cripto}&vs_currencies=usd"
    try:
        respuesta = requests.get(url)
        data = respuesta.json()
        if cripto in data and 'usd' in data[cripto]:
            return data[cripto]['usd']
        else:
            return None
    except:
        return None

# --- Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    referido_por = None
    if args and args[0].isdigit():
        referido_por = int(args[0])
    nuevo = registrar_usuario(user_id, referido_por)
    idioma = obtener_idioma(user_id)
    if nuevo:
        await enviar_mensaje(update, MENSAJES[idioma]['bienvenida'])
        if referido_por:
            await enviar_mensaje(update, MENSAJES[idioma]['referral_bienvenida'].format(ref_id=referido_por))
    await enviar_mensaje(update, MENSAJES[idioma]['inicio'])

async def precio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    idioma = obtener_idioma(user_id)
    if len(context.args) == 0:
        await enviar_mensaje(update, "Uso: /precio <nombre_cripto>")
        return
    cripto = context.args[0].lower()
    precio = obtener_precio_cripto(cripto)
    if precio is None:
        await enviar_mensaje(update, "Cripto no encontrada o error en la consulta.")
    else:
        await enviar_mensaje(update, MENSAJES[idioma]['precio_actual'].format(cripto=cripto, precio=precio))

async def alerta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    idioma = obtener_idioma(user_id)
    if len(context.args) < 3:
        await enviar_mensaje(update, "Uso: /alerta <cripto> <arriba|abajo> <precio>")
        return
    cripto = context.args[0].lower()
    direccion = context.args[1].lower()
    if direccion not in ['arriba', 'abajo', 'above', 'below']:
        await enviar_mensaje(update, "Dirección inválida, usa 'arriba' o 'abajo'")
        return
    try:
        precio = float(context.args[2])
    except:
        await enviar_mensaje(update, "Precio inválido.")
        return
    c.execute("INSERT INTO alertas (user_id, cripto, precio, direccion) VALUES (?, ?, ?, ?)",
              (user_id, cripto, precio, direccion))
    conn.commit()
    await enviar_mensaje(update, MENSAJES[idioma]['alerta_creada'].format(cripto=cripto, direccion=direccion, precio=precio))
async def mis_alertas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    idioma = obtener_idioma(user_id)
    c.execute("SELECT cripto, precio, direccion FROM alertas WHERE user_id = ? AND enviada = 0", (user_id,))
    filas = c.fetchall()
    if not filas:
        await enviar_mensaje(update, MENSAJES[idioma]['sin_alertas'])
        return
    texto = "Tus alertas activas:\n"
    for cripto, precio, direccion in filas:
        texto += f"- {cripto} {direccion} {precio}\n"
    await enviar_mensaje(update, texto)


async def borrar_alerta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    idioma = obtener_idioma(user_id)
    if len(context.args) == 0:
        await enviar_mensaje(update, "Uso: /borrar_alerta <cripto>")
        return
    cripto = context.args[0].lower()
    c.execute("DELETE FROM alertas WHERE user_id = ? AND cripto = ?", (user_id, cripto))
    conn.commit()
    await enviar_mensaje(update, MENSAJES[idioma]['alerta_borrada'].format(cripto=cripto))


async def soporte(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    idioma = obtener_idioma(user_id)
    await enviar_mensaje(update, MENSAJES[idioma]['soporte'])


async def suscribirme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    idioma = obtener_idioma(user_id)
    await enviar_mensaje(update, MENSAJES[idioma]['plan_info'])


async def miid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    idioma = obtener_idioma(user_id)
    await enviar_mensaje(update, MENSAJES[idioma]['id_usuario'].format(user_id=user_id))


async def historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    idioma = obtener_idioma(user_id)
    c.execute("SELECT comando, fecha FROM logs WHERE user_id = ?", (user_id,))
    filas = c.fetchall()
    if not filas:
        await enviar_mensaje(update, MENSAJES[idioma]['historial_vacio'])
        return
    texto = "Historial de comandos:\n"
    for comando, fecha in filas:
        texto += f"{fecha}: {comando}\n"
    await enviar_mensaje(update, texto)


async def faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c.execute("SELECT pregunta, respuesta FROM faq")
    filas = c.fetchall()
    if not filas:
        await update.message.reply_text(MENSAJES['es']['faq_sin_preguntas'])
        return
    texto = MENSAJES['es']['faq_intro']
    for pregunta, respuesta in filas:
        texto += f"\nQ: {pregunta}\nA: {respuesta}\n"
    await update.message.reply_text(texto)


async def setfaq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ID_ADMIN:
        await update.message.reply_text(MENSAJES['es']['no_autorizado'])
        return
    try:
        data = update.message.text.split(' ', 1)[1]
        pregunta, respuesta = data.split('|', 1)
        c.execute("INSERT INTO faq (pregunta, respuesta) VALUES (?, ?)", (pregunta.strip(), respuesta.strip()))
        conn.commit()
        await update.message.reply_text("FAQ agregada correctamente.")
    except:
        await update.message.reply_text("Usa el formato: /setfaq pregunta|respuesta")


async def verfaq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ID_ADMIN:
        await update.message.reply_text(MENSAJES['es']['no_autorizado'])
        return
    c.execute("SELECT * FROM faq")
    filas = c.fetchall()
    if not filas:
        await update.message.reply_text("No hay FAQs registradas.")
    else:
        texto = "\n\n".join([f"Q: {q}\nA: {a}" for q, a in filas])
        await update.message.reply_text(texto)


async def referidos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    c.execute("SELECT COUNT(*) FROM usuarios WHERE referido_por = ?", (user_id,))
    count = c.fetchone()[0]
    idioma = obtener_idioma(user_id)
    mensaje = MENSAJES[idioma]['referido_registrado'].format(count=count)
    await update.message.reply_text(mensaje)


# Registrar logs de comandos
async def log_comando(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    comando = update.message.text
    c.execute("INSERT INTO logs (user_id, comando) VALUES (?, ?)", (user_id, comando))
    conn.commit()


# Scheduler para alertas
async def verificar_alertas(application):
    c.execute("SELECT id, user_id, cripto, precio, direccion FROM alertas WHERE enviada = 0")
    alertas = c.fetchall()
    for id_alerta, user_id, cripto, precio, direccion in alertas:
        precio_actual = obtener_precio_cripto(cripto)
        if precio_actual is None:
            continue
        if (direccion in ['arriba', 'above'] and precio_actual >= precio) or \
           (direccion in ['abajo', 'below'] and precio_actual <= precio):
            try:
                await application.bot.send_message(chat_id=user_id,
                                                   text=f"🚨 Alerta: {cripto} está {direccion} {precio}. Precio actual: {precio_actual}")
                c.execute("UPDATE alertas SET enviada = 1 WHERE id = ?", (id_alerta,))
                conn.commit()
            except Exception as e:
                logging.error(f"Error enviando alerta: {e}")


async def main():
    application = ApplicationBuilder().token(TOKEN).build()


    # Agregar handlers comandos
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("precio", precio))
    application.add_handler(CommandHandler("alerta", alerta))
    application.add_handler(CommandHandler("mis_alertas", mis_alertas))
    application.add_handler(CommandHandler("borrar_alerta", borrar_alerta))
    application.add_handler(CommandHandler("soporte", soporte))
    application.add_handler(CommandHandler("suscribirme", suscribirme))
    application.add_handler(CommandHandler("miid", miid))
    application.add_handler(CommandHandler("historial", historial))
    application.add_handler(CommandHandler("faq", faq))
    application.add_handler(CommandHandler("setfaq", setfaq))
    application.add_handler(CommandHandler("verfaq", verfaq))
    application.add_handler(CommandHandler("referidos", referidos))


    # Log comandos (este debe ir en grupo aparte para que no interfiera con otros handlers)
    application.add_handler(MessageHandler(filters.COMMAND, log_comando), group=1)


    # Scheduler para alertas cada 60 segundos
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: asyncio.create_task(verificar_alertas(application)), 'interval', seconds=60)
    scheduler.start()


    # Ejecutar el bot (esperar a que termine)
    await application.run_polling()


if __name__ == "__main__":
    import asyncio
    import nest_asyncio


    nest_asyncio.apply()  # Esto evita errores si ya hay un loop corriendo
    asyncio.run(main())   # Ejecuta tu función principal

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¡Hola! Soy SmartDanielBot, tu nuevo asistente.")

app = ApplicationBuilder().token("7959655718:AAF4CUM1fVy45bNzqqNWarJdnDacpEGBtXk").build()
app.add_handler(CommandHandler("start", start))

app.run_polling()
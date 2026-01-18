from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
TOPIC_ID = int(os.getenv("TOPIC_ID"))  # ID tematu (np. WTS)

async def handle_pm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # TYLKO prywatne wiadomości
    if not update.message or update.message.chat.type != "private":
        return

    # SUROWY TEKST – zero zmian
    text = update.message.text

    await context.bot.send_message(
        chat_id=GROUP_ID,
        message_thread_id=TOPIC_ID,
        text=text
        # UWAGA: brak parse_mode!
    )

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_pm))
    print("CLEAN 1:1 BOT ONLINE")
    app.run_polling()

if __name__ == "__main__":
    main()

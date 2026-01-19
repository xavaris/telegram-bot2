from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
TOPIC_ID = int(os.getenv("TOPIC_ID"))

def get_username(user):
    if user.username:
        return f"@{user.username}"
    return user.first_name or "Użytkownik"

async def handle_pm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.message.chat.type != "private":
        return

    user = update.message.from_user
    username = get_username(user)

    # 🔥 KOPIA 1:1 WIADOMOŚCI
    await context.bot.copy_message(
        chat_id=GROUP_ID,
        message_thread_id=TOPIC_ID,
        from_chat_id=update.message.chat_id,
        message_id=update.message.message_id
    )

    # ✍️ PODPIS AUTORA
    await context.bot.send_message(
        chat_id=GROUP_ID,
        message_thread_id=TOPIC_ID,
        text=f"— {username}"
    )

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL, handle_pm))
    print("COPY 1:1 + SIGNATURE BOT ONLINE")
    app.run_polling()

if __name__ == "__main__":
    main()

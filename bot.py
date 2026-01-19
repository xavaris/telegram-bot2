from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

SOURCE_GROUP_ID = int(os.getenv("SOURCE_GROUP_ID"))   # grupa A
TARGET_GROUP_ID = int(os.getenv("TARGET_GROUP_ID"))   # grupa B
TOPIC_ID = int(os.getenv("TOPIC_ID"))                 # temat w grupie B


def get_username(user):
    if user.username:
        return f"@{user.username}"
    return user.first_name or "Użytkownik"


async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message

    # ❌ brak wiadomości
    if not msg:
        return

    # ❌ tylko grupa źródłowa
    if msg.chat_id != SOURCE_GROUP_ID:
        return

    # ❌ ignoruj systemowe (join/leave/pinned/etc.)
    if msg.from_user is None:
        return

    # ❌ ignoruj wiadomości botów (w tym własne)
    if msg.from_user.is_bot:
        return

    user = msg.from_user
    username = get_username(user)

    try:
        # 1️⃣ PEŁNY FORWARD 1:1
        forwarded = await context.bot.forward_message(
            chat_id=TARGET_GROUP_ID,
            message_thread_id=TOPIC_ID,
            from_chat_id=msg.chat_id,
            message_id=msg.message_id
        )
    except Exception:
        # ❌ tej wiadomości Telegram nie pozwala forwardować
        return

    # 2️⃣ PODPIS AUTORA
    await context.bot.send_message(
        chat_id=TARGET_GROUP_ID,
        message_thread_id=TOPIC_ID,
        text=f"— {username}"
    )


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # OBSŁUGUJ WSZYSTKO, ALE FILTRUJ W FUNKCJI
    app.add_handler(MessageHandler(filters.ALL, handle_group_message))

    print("GROUP A → GROUP B (TOPIC) + SIGNATURE BOT ONLINE")
    app.run_polling()


if __name__ == "__main__":
    main()

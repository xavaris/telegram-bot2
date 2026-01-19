from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    filters,
)
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

SOURCE_GROUP_ID = int(os.getenv("SOURCE_GROUP_ID"))   # grupa A
TARGET_GROUP_ID = int(os.getenv("TARGET_GROUP_ID"))   # grupa B
TOPIC_ID = int(os.getenv("TOPIC_ID"))                  # temat w grupie B

DELETE_AFTER = 12 * 60 * 60  # 12h w sekundach


def get_username(user):
    if user.username:
        return f"@{user.username}"
    return user.first_name or "Użytkownik"


async def delete_message_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]
    message_id = context.job.data["message_id"]

    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass  # wiadomość mogła być już usunięta


async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    # reaguj tylko na grupę A
    if msg.chat_id != SOURCE_GROUP_ID:
        return

    user = msg.from_user
    username = get_username(user)

    # 1️⃣ FORWARD 1:1 DO GRUPY B (TEMAT)
    forwarded = await context.bot.forward_message(
        chat_id=TARGET_GROUP_ID,
        message_thread_id=TOPIC_ID,
        from_chat_id=msg.chat_id,
        message_id=msg.message_id
    )

    # 2️⃣ PODPIS AUTORA
    signature = await context.bot.send_message(
        chat_id=TARGET_GROUP_ID,
        message_thread_id=TOPIC_ID,
        text=f"— {username}"
    )

    # 3️⃣ ZAPLANUJ USUWANIE PO 12H

    # usuń oryginał w grupie A
    context.job_queue.run_once(
        delete_message_job,
        DELETE_AFTER,
        data={"chat_id": SOURCE_GROUP_ID, "message_id": msg.message_id}
    )

    # usuń forward w grupie B
    context.job_queue.run_once(
        delete_message_job,
        DELETE_AFTER,
        data={"chat_id": TARGET_GROUP_ID, "message_id": forwarded.message_id}
    )

    # usuń podpis w grupie B
    context.job_queue.run_once(
        delete_message_job,
        DELETE_AFTER,
        data={"chat_id": TARGET_GROUP_ID, "message_id": signature.message_id}
    )


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.ALL, handle_group_message))

    print("GROUP A → GROUP B + SIGNATURE + AUTO DELETE 12H BOT ONLINE")
    app.run_polling()


if __name__ == "__main__":
    main()

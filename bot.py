from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    filters,
)
import os
import time

BOT_TOKEN = os.getenv("BOT_TOKEN")

SOURCE_GROUP_ID = int(os.getenv("SOURCE_GROUP_ID"))   # grupa A
TARGET_GROUP_ID = int(os.getenv("TARGET_GROUP_ID"))   # grupa B
TOPIC_ID = int(os.getenv("TOPIC_ID"))                 # temat w grupie B

DELETE_AFTER = 12 * 60 * 60   # 12h
COOLDOWN = 12 * 60 * 60       # 12h
MAX_WARNS = 5

last_post_time = {}  # user_id -> timestamp
warns = {}           # user_id -> warn count


# ---------- HELPERS ----------

def get_username(user):
    if user.username:
        return f"@{user.username}"
    return user.first_name or "Użytkownik"


async def is_admin(context, chat_id, user_id):
    member = await context.bot.get_chat_member(chat_id, user_id)
    return member.status in ("administrator", "creator")


async def delete_message_job(context: ContextTypes.DEFAULT_TYPE):
    d = context.job.data
    try:
        await context.bot.delete_message(d["chat_id"], d["message_id"])
    except Exception:
        pass


# ---------- WARNS ----------

async def apply_warn(context, user, reason):
    uid = user.id
    username = get_username(user)

    warns[uid] = warns.get(uid, 0) + 1
    count = warns[uid]

    warn_text = f"⚠️ {username} otrzymuje WARN ({count}/{MAX_WARNS})\nPowód: {reason}"

    await context.bot.send_message(SOURCE_GROUP_ID, warn_text)
    await context.bot.send_message(TARGET_GROUP_ID, warn_text)

    if count >= MAX_WARNS:
        ban_text = f"⛔ {username} otrzymał {MAX_WARNS}/{MAX_WARNS} WARNÓW → BAN"

        for chat_id in (SOURCE_GROUP_ID, TARGET_GROUP_ID):
            try:
                await context.bot.ban_chat_member(chat_id, uid)
                await context.bot.send_message(chat_id, ban_text)
            except Exception:
                pass


# ---------- ADMIN COMMANDS ----------

async def handle_admin_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.reply_to_message:
        return

    if msg.text not in ("/warn", "/unwarn", "/warns"):
        return

    chat_id = msg.chat_id
    admin_id = msg.from_user.id

    if not await is_admin(context, chat_id, admin_id):
        return

    target = msg.reply_to_message.from_user
    if not target or target.is_bot:
        return

    if await is_admin(context, chat_id, target.id):
        return  # adminów nie warnujemy

    uid = target.id
    username = get_username(target)

    if msg.text == "/warn":
        await apply_warn(context, target, "Manualny WARN (admin)")

    elif msg.text == "/unwarn":
        warns[uid] = max(0, warns.get(uid, 0) - 1)
        await context.bot.send_message(
            chat_id,
            f"✅ {username} zdjęto WARN ({warns[uid]}/{MAX_WARNS})"
        )

    elif msg.text == "/warns":
        count = warns.get(uid, 0)
        await context.bot.send_message(
            chat_id,
            f"📊 {username} ma {count}/{MAX_WARNS} WARNÓW"
        )


# ---------- MAIN LOGIC ----------

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    # tylko grupa A
    if msg.chat_id != SOURCE_GROUP_ID:
        return

    # systemowe / boty
    if msg.from_user is None or msg.from_user.is_bot:
        return

    user = msg.from_user
    uid = user.id
    username = get_username(user)
    text = msg.text or msg.caption or ""

    # ADMIN BYPASS
    if not await is_admin(context, SOURCE_GROUP_ID, uid):

        # brak #wts
        if "#wts" not in text.lower():
            await apply_warn(context, user, "Brak #wts")
            return

        # cooldown
        now = time.time()
        last = last_post_time.get(uid, 0)

        if now - last < COOLDOWN:
            await apply_warn(context, user, "Złamanie cooldownu 12h")
            return

        last_post_time[uid] = now

    # FORWARD 1:1
    try:
        forwarded = await context.bot.forward_message(
            chat_id=TARGET_GROUP_ID,
            message_thread_id=TOPIC_ID,
            from_chat_id=msg.chat_id,
            message_id=msg.message_id
        )
    except Exception:
        return

    # PODPIS
    signature = await context.bot.send_message(
        chat_id=TARGET_GROUP_ID,
        message_thread_id=TOPIC_ID,
        text=f"— {username}"
    )

    # AUTO DELETE 12H
    for chat, mid in [
        (SOURCE_GROUP_ID, msg.message_id),
        (TARGET_GROUP_ID, forwarded.message_id),
        (TARGET_GROUP_ID, signature.message_id),
    ]:
        context.job_queue.run_once(
            delete_message_job,
            DELETE_AFTER,
            data={"chat_id": chat, "message_id": mid}
        )


# ---------- START ----------

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/(warn|unwarn|warns)$"), handle_admin_commands))
    app.add_handler(MessageHandler(filters.ALL, handle_group_message))

    print("BOT ONLINE | WTS | WARN | BAN | COOLDOWN | AUTO DELETE")
    app.run_polling()


if __name__ == "__main__":
    main()

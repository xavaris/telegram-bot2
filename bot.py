from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    filters,
)
import os
import time
import json

# ================== KONFIG ==================

BOT_TOKEN = os.getenv("BOT_TOKEN")

SOURCE_GROUP_ID = int(os.getenv("SOURCE_GROUP_ID"))
TARGET_GROUP_ID = int(os.getenv("TARGET_GROUP_ID"))
TOPIC_ID = int(os.getenv("TOPIC_ID"))

DELETE_AFTER = 12 * 60 * 60     # 12h
COOLDOWN = 12 * 60 * 60         # 12h
MAX_WARNS = 5
INFO_DELETE_AFTER = 60          # info na SOURCE (sekundy)

WARN_FILE = "warns.json"

# ================== PAMIĘĆ ==================

last_post_time = {}   # cooldowny (RAM)
warns = {}            # warny (JSON)

# ================== PERSISTENCJA WARNÓW ==================

def load_warns():
    global warns
    if os.path.exists(WARN_FILE):
        try:
            with open(WARN_FILE, "r", encoding="utf-8") as f:
                warns = json.load(f)
                warns = {int(k): int(v) for k, v in warns.items()}
        except Exception:
            warns = {}
    else:
        warns = {}

def save_warns():
    with open(WARN_FILE, "w", encoding="utf-8") as f:
        json.dump(warns, f)

# ================== HELPERY ==================

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

# ================== KOMENDY USERÓW ==================

async def handle_mywarns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.from_user:
        return

    uid = msg.from_user.id
    username = get_username(msg.from_user)
    count = warns.get(uid, 0)

    await context.bot.send_message(
        chat_id=msg.chat_id,
        reply_to_message_id=msg.message_id,
        text=f"📊 {username}, masz {count}/{MAX_WARNS} WARNÓW"
    )

async def handle_mycooldown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.from_user:
        return

    uid = msg.from_user.id
    username = get_username(msg.from_user)

    if await is_admin(context, SOURCE_GROUP_ID, uid):
        await context.bot.send_message(
            chat_id=msg.chat_id,
            reply_to_message_id=msg.message_id,
            text=f"✅ {username}, administratorzy nie mają cooldownu"
        )
        return

    last = last_post_time.get(uid)
    if not last:
        await context.bot.send_message(
            chat_id=msg.chat_id,
            reply_to_message_id=msg.message_id,
            text=f"✅ {username}, możesz wysłać ogłoszenie teraz"
        )
        return

    remaining = int(COOLDOWN - (time.time() - last))
    if remaining <= 0:
        await context.bot.send_message(
            chat_id=msg.chat_id,
            reply_to_message_id=msg.message_id,
            text=f"✅ {username}, możesz wysłać ogłoszenie teraz"
        )
        return

    h = remaining // 3600
    m = (remaining % 3600) // 60

    await context.bot.send_message(
        chat_id=msg.chat_id,
        reply_to_message_id=msg.message_id,
        text=f"⏳ {username}, możesz wysłać kolejne ogłoszenie za {h}h {m}m"
    )

# ================== WARNS ==================

async def apply_warn(context, user, reason):
    uid = user.id
    username = get_username(user)

    warns[uid] = warns.get(uid, 0) + 1
    save_warns()

    count = warns[uid]
    text = f"⚠️ {username} otrzymuje WARN ({count}/{MAX_WARNS})\nPowód: {reason}"

    await context.bot.send_message(SOURCE_GROUP_ID, text)
    await context.bot.send_message(TARGET_GROUP_ID, text)

    if count >= MAX_WARNS:
        ban_text = f"⛔ {username} otrzymał {MAX_WARNS}/{MAX_WARNS} WARNÓW → BAN"
        for chat in (SOURCE_GROUP_ID, TARGET_GROUP_ID):
            try:
                await context.bot.ban_chat_member(chat, uid)
                await context.bot.send_message(chat, ban_text)
            except Exception:
                pass

# ================== PANEL ADMINA ==================

async def handle_admin_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.reply_to_message:
        return

    if msg.text not in ("/warn", "/unwarn", "/warncount"):
        return

    chat_id = msg.chat_id
    admin_id = msg.from_user.id

    if not await is_admin(context, chat_id, admin_id):
        return

    target = msg.reply_to_message.from_user
    if not target or target.is_bot:
        return

    if await is_admin(context, chat_id, target.id):
        return

    uid = target.id
    username = get_username(target)

    if msg.text == "/warn":
        await apply_warn(context, target, "Manualny WARN (admin)")

    elif msg.text == "/unwarn":
        warns[uid] = max(0, warns.get(uid, 0) - 1)
        save_warns()
        await context.bot.send_message(
            chat_id,
            f"✅ {username} zdjęto WARN ({warns[uid]}/{MAX_WARNS})"
        )

    elif msg.text == "/warncount":
        await context.bot.send_message(
            chat_id,
            f"📊 {username} ma {warns.get(uid, 0)}/{MAX_WARNS} WARNÓW"
        )

# ================== GŁÓWNA LOGIKA ==================

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    # ❌ NIE forwarduj komend
    if msg.text and msg.text.startswith("/"):
        return

    # tylko SOURCE
    if msg.chat_id != SOURCE_GROUP_ID:
        return

    # systemowe / boty
    if msg.from_user is None or msg.from_user.is_bot:
        return

    user = msg.from_user
    uid = user.id
    username = get_username(user)
    text = msg.text or msg.caption or ""

    if not await is_admin(context, SOURCE_GROUP_ID, uid):

        if "#wts" not in text.lower():
            await apply_warn(context, user, "Brak #wts")
            return

        now = time.time()
        last = last_post_time.get(uid, 0)
        if now - last < COOLDOWN:
            await apply_warn(context, user, "Złamanie cooldownu 12h")
            return

        last_post_time[uid] = now

    # FORWARD
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

    # USUŃ OGŁOSZENIE Z SOURCE NATYCHMIAST
    try:
        await context.bot.delete_message(
            chat_id=SOURCE_GROUP_ID,
            message_id=msg.message_id
        )
    except Exception:
        pass

    # INFO NA SOURCE
    try:
        info = await context.bot.send_message(
            chat_id=SOURCE_GROUP_ID,
            text=f"{username} twoje ogłoszenie zostało opublikowane."
        )
        context.job_queue.run_once(
            delete_message_job,
            INFO_DELETE_AFTER,
            data={"chat_id": SOURCE_GROUP_ID, "message_id": info.message_id}
        )
    except Exception:
        pass

    # AUTO DELETE NA TARGET PO 12H
    for chat, mid in [
        (TARGET_GROUP_ID, forwarded.message_id),
        (TARGET_GROUP_ID, signature.message_id),
    ]:
        context.job_queue.run_once(
            delete_message_job,
            DELETE_AFTER,
            data={"chat_id": chat, "message_id": mid}
        )

# ================== START ==================

def main():
    load_warns()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.Regex(r"^/mywarns$"), handle_mywarns))
    app.add_handler(MessageHandler(filters.Regex(r"^/mycooldown$"), handle_mycooldown))
    app.add_handler(MessageHandler(filters.Regex(r"^/(warn|unwarn|warncount)$"), handle_admin_commands))
    app.add_handler(MessageHandler(filters.ALL, handle_group_message))

    print("BOT ONLINE | FINAL VERSION")
    app.run_polling()

if __name__ == "__main__":
    main()

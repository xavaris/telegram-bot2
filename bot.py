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

SOURCE_DELETE_AFTER = 120            # 2 min
TARGET_DELETE_AFTER = 12 * 60 * 60   # 12h
COOLDOWN = 12 * 60 * 60              # 12h
MAX_WARNS = 5

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

    reply = await context.bot.send_message(
        chat_id=msg.chat_id,
        reply_to_message_id=msg.message_id,
        text=f"📊 {username}, masz {count}/{MAX_WARNS} WARNÓW"
    )

    # usuń odpowiedź i KOMENDĘ usera po 120s
    for mid in (reply.message_id, msg.message_id):
        context.job_queue.run_once(
            delete_message_job,
            SOURCE_DELETE_AFTER,
            data={"chat_id": msg.chat_id, "message_id": mid}
        )

async def handle_mycooldown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.from_user:
        return

    uid = msg.from_user.id
    username = get_username(msg.from_user)

    if await is_admin(context, SOURCE_GROUP_ID, uid):
        reply = await context.bot.send_message(
            chat_id=msg.chat_id,
            reply_to_message_id=msg.message_id,
            text=f"✅ {username}, administratorzy nie mają cooldownu"
        )
    else:
        last = last_post_time.get(uid)
        if not last:
            reply = await context.bot.send_message(
                chat_id=msg.chat_id,
                reply_to_message_id=msg.message_id,
                text=f"✅ {username}, możesz wysłać ogłoszenie teraz"
            )
        else:
            remaining = int(COOLDOWN - (time.time() - last))
            if remaining <= 0:
                reply = await context.bot.send_message(
                    chat_id=msg.chat_id,
                    reply_to_message_id=msg.message_id,
                    text=f"✅ {username}, możesz wysłać ogłoszenie teraz"
                )
            else:
                h = remaining // 3600
                m = (remaining % 3600) // 60
                reply = await context.bot.send_message(
                    chat_id=msg.chat_id,
                    reply_to_message_id=msg.message_id,
                    text=f"⏳ {username}, możesz wysłać kolejne ogłoszenie za {h}h {m}m"
                )

    # usuń odpowiedź i KOMENDĘ usera po 120s
    for mid in (reply.message_id, msg.message_id):
        context.job_queue.run_once(
            delete_message_job,
            SOURCE_DELETE_AFTER,
            data={"chat_id": msg.chat_id, "message_id": mid}
        )

# ================== WARNS ==================

async def apply_warn(context, user, reason):
    uid = user.id
    username = get_username(user)

    warns[uid] = warns.get(uid, 0) + 1
    save_warns()

    text = f"⚠️ {username} otrzymuje WARN ({warns[uid]}/{MAX_WARNS})\nPowód: {reason}"

    for chat in (SOURCE_GROUP_ID, TARGET_GROUP_ID):
        try:
            warn_msg = await context.bot.send_message(chat, text)
            delay = SOURCE_DELETE_AFTER if chat == SOURCE_GROUP_ID else TARGET_DELETE_AFTER
            context.job_queue.run_once(
                delete_message_job,
                delay,
                data={"chat_id": chat, "message_id": warn_msg.message_id}
            )
        except Exception:
            pass

    if warns[uid] >= MAX_WARNS:
        for chat in (SOURCE_GROUP_ID, TARGET_GROUP_ID):
            try:
                await context.bot.ban_chat_member(chat, uid)
            except Exception:
                pass

# ================== PANEL ADMINA ==================

async def handle_admin_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.reply_to_message:
        return

    if msg.text not in ("/warn", "/unwarn", "/warncount"):
        return

    if not await is_admin(context, msg.chat_id, msg.from_user.id):
        return

    target = msg.reply_to_message.from_user
    if not target or target.is_bot:
        return

    uid = target.id
    username = get_username(target)

    if msg.text == "/warn":
        await apply_warn(context, target, "Manualny WARN (admin)")

    elif msg.text == "/unwarn":
        warns[uid] = max(0, warns.get(uid, 0) - 1)
        save_warns()
        reply = await context.bot.send_message(
            msg.chat_id,
            f"✅ {username} zdjęto WARN ({warns[uid]}/{MAX_WARNS})"
        )
        context.job_queue.run_once(
            delete_message_job,
            SOURCE_DELETE_AFTER,
            data={"chat_id": msg.chat_id, "message_id": reply.message_id}
        )

    elif msg.text == "/warncount":
        reply = await context.bot.send_message(
            msg.chat_id,
            f"📊 {username} ma {warns.get(uid, 0)}/{MAX_WARNS} WARNÓW"
        )
        context.job_queue.run_once(
            delete_message_job,
            SOURCE_DELETE_AFTER,
            data={"chat_id": msg.chat_id, "message_id": reply.message_id}
        )

# ================== GŁÓWNA LOGIKA ==================

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    # ❌ PINY – NIGDY
    if msg.pinned_message is not None:
        return

    # ❌ nie forwarduj komend
    if msg.text and msg.text.startswith("/"):
        return

    # tylko SOURCE
    if msg.chat_id != SOURCE_GROUP_ID:
        return

    if msg.from_user is None or msg.from_user.is_bot:
        return

    user = msg.from_user
    uid = user.id
    username = get_username(user)
    text = msg.text or msg.caption or ""

    # ===== BŁĘDY → WARN + USUNIĘCIE PO 120s =====
    if not await is_admin(context, SOURCE_GROUP_ID, uid):
        if "#wts" not in text.lower():
            context.job_queue.run_once(
                delete_message_job,
                SOURCE_DELETE_AFTER,
                data={"chat_id": SOURCE_GROUP_ID, "message_id": msg.message_id}
            )
            await apply_warn(context, user, "Brak #wts")
            return

        now = time.time()
        if now - last_post_time.get(uid, 0) < COOLDOWN:
            context.job_queue.run_once(
                delete_message_job,
                SOURCE_DELETE_AFTER,
                data={"chat_id": SOURCE_GROUP_ID, "message_id": msg.message_id}
            )
            await apply_warn(context, user, "Złamanie cooldownu 12h")
            return

        last_post_time[uid] = now

    # ===== POPRAWNE OGŁOSZENIE =====
    try:
        forwarded = await context.bot.forward_message(
            chat_id=TARGET_GROUP_ID,
            message_thread_id=TOPIC_ID,
            from_chat_id=SOURCE_GROUP_ID,
            message_id=msg.message_id
        )
    except Exception:
        return

    signature = await context.bot.send_message(
        TARGET_GROUP_ID,
        text=f"— {username}",
        message_thread_id=TOPIC_ID
    )

    # SOURCE – USUŃ NATYCHMIAST
    try:
        await context.bot.delete_message(SOURCE_GROUP_ID, msg.message_id)
    except Exception:
        pass

    info = await context.bot.send_message(
        SOURCE_GROUP_ID,
        text=f"{username} twoje ogłoszenie zostało opublikowane."
    )
    context.job_queue.run_once(
        delete_message_job,
        SOURCE_DELETE_AFTER,
        data={"chat_id": SOURCE_GROUP_ID, "message_id": info.message_id}
    )

    # TARGET – USUŃ PO 12h
    for mid in (forwarded.message_id, signature.message_id):
        context.job_queue.run_once(
            delete_message_job,
            TARGET_DELETE_AFTER,
            data={"chat_id": TARGET_GROUP_ID, "message_id": mid}
        )

# ================== START ==================

def main():
    load_warns()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.Regex(r"^/mywarns$"), handle_mywarns))
    app.add_handler(MessageHandler(filters.Regex(r"^/mycooldown$"), handle_mycooldown))
    app.add_handler(MessageHandler(filters.Regex(r"^/(warn|unwarn|warncount)$"), handle_admin_commands))
    app.add_handler(MessageHandler(filters.ALL, handle_group_message))

    print("BOT ONLINE | FINAL FIXED VERSION")
    app.run_polling()

if __name__ == "__main__":
    main()

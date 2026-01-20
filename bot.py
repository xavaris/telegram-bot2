from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
import os, time, json

# ================== KONFIG ==================

BOT_TOKEN = os.getenv("BOT_TOKEN")

SOURCE_GROUP_ID = int(os.getenv("SOURCE_GROUP_ID"))
TARGET_GROUP_ID = int(os.getenv("TARGET_GROUP_ID"))
TOPIC_ID = int(os.getenv("TOPIC_ID"))

SOURCE_DELETE_AFTER = 120
TARGET_DELETE_AFTER = 12 * 60 * 60
COOLDOWN = 12 * 60 * 60
MAX_WARNS = 5

WARN_FILE = "warns.json"

# ================== PAMIĘĆ ==================

last_post_time = {}
warns = {}

# ================== WARNY (PERSISTENCJA) ==================

def load_warns():
    global warns
    if os.path.exists(WARN_FILE):
        with open(WARN_FILE, "r", encoding="utf-8") as f:
            warns = {int(k): int(v) for k, v in json.load(f).items()}
    else:
        warns = {}

def save_warns():
    with open(WARN_FILE, "w", encoding="utf-8") as f:
        json.dump(warns, f)

# ================== HELPERY ==================

def get_username(user):
    return f"@{user.username}" if user.username else (user.first_name or "Użytkownik")

async def is_admin(context, chat_id, user_id):
    member = await context.bot.get_chat_member(chat_id, user_id)
    return member.status in ("administrator", "creator")

async def delete_message_job(context: ContextTypes.DEFAULT_TYPE):
    d = context.job.data
    try:
        await context.bot.delete_message(d["chat_id"], d["message_id"])
    except Exception:
        pass

# ================== KOMENDY USER ==================

async def handle_mywarns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.from_user:
        return

    count = warns.get(msg.from_user.id, 0)
    reply = await context.bot.send_message(
        msg.chat_id,
        f"📊 {get_username(msg.from_user)} masz {count}/{MAX_WARNS} WARNÓW",
        reply_to_message_id=msg.message_id
    )

    for mid in (msg.message_id, reply.message_id):
        context.job_queue.run_once(
            delete_message_job, SOURCE_DELETE_AFTER,
            data={"chat_id": msg.chat_id, "message_id": mid}
        )

async def handle_mycooldown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.from_user:
        return

    uid = msg.from_user.id
    username = get_username(msg.from_user)

    if await is_admin(context, SOURCE_GROUP_ID, uid):
        text = f"✅ {username} administratorzy nie mają cooldownu"
    else:
        last = last_post_time.get(uid)
        if not last:
            text = f"✅ {username} możesz wysłać ogłoszenie teraz"
        else:
            rem = int(COOLDOWN - (time.time() - last))
            if rem <= 0:
                text = f"✅ {username} możesz wysłać ogłoszenie teraz"
            else:
                text = f"⏳ {username} za {rem//3600}h {(rem%3600)//60}m"

    reply = await context.bot.send_message(
        msg.chat_id, text, reply_to_message_id=msg.message_id
    )

    for mid in (msg.message_id, reply.message_id):
        context.job_queue.run_once(
            delete_message_job, SOURCE_DELETE_AFTER,
            data={"chat_id": msg.chat_id, "message_id": mid}
        )

# ================== WARN ==================

async def apply_warn(context, user, reason):
    uid = user.id
    warns[uid] = warns.get(uid, 0) + 1
    save_warns()

    text = f"⚠️ {get_username(user)} WARN ({warns[uid]}/{MAX_WARNS})\n{reason}"

    for chat in (SOURCE_GROUP_ID, TARGET_GROUP_ID):
        try:
            m = await context.bot.send_message(chat, text)
            delay = SOURCE_DELETE_AFTER if chat == SOURCE_GROUP_ID else TARGET_DELETE_AFTER
            context.job_queue.run_once(
                delete_message_job, delay,
                data={"chat_id": chat, "message_id": m.message_id}
            )
        except Exception:
            pass

# ================== GŁÓWNA LOGIKA ==================

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    # 🚫 systemowe / piny / forwardy
    if (
        msg.pinned_message is not None or
        msg.forward_from or
        msg.forward_from_chat or
        msg.is_automatic_forward
    ):
        return

    # 🚫 komendy
    if msg.text and msg.text.startswith("/"):
        return

    # tylko SOURCE
    if msg.chat_id != SOURCE_GROUP_ID:
        return

    if not msg.from_user or msg.from_user.is_bot:
        return

    text = msg.text or msg.caption or ""
    header = text.strip().lower()
    user = msg.from_user
    uid = user.id

    # 🚫 FILTR NAGŁÓWKA (REGULAMINY / INFO)
    if (
        header.startswith("🤖") or
        header.startswith("jak działa bot") or
        header.startswith("zasady") or
        header.startswith("komendy")
    ):
        return

    # ❌ BŁĘDY
    if not await is_admin(context, SOURCE_GROUP_ID, uid):
        if "#wts" not in text.lower():
            context.job_queue.run_once(
                delete_message_job, SOURCE_DELETE_AFTER,
                data={"chat_id": SOURCE_GROUP_ID, "message_id": msg.message_id}
            )
            await apply_warn(context, user, "Brak #wts")
            return

        if time.time() - last_post_time.get(uid, 0) < COOLDOWN:
            context.job_queue.run_once(
                delete_message_job, SOURCE_DELETE_AFTER,
                data={"chat_id": SOURCE_GROUP_ID, "message_id": msg.message_id}
            )
            await apply_warn(context, user, "Cooldown 12h")
            return

        last_post_time[uid] = time.time()

    # ✅ FORWARD OGŁOSZENIA
    forwarded = await context.bot.forward_message(
        chat_id=TARGET_GROUP_ID,
        message_thread_id=TOPIC_ID,
        from_chat_id=SOURCE_GROUP_ID,
        message_id=msg.message_id
    )

    sign = await context.bot.send_message(
        TARGET_GROUP_ID,
        f"— {get_username(user)}",
        message_thread_id=TOPIC_ID
    )

    # SOURCE → delete natychmiast
    await context.bot.delete_message(SOURCE_GROUP_ID, msg.message_id)

    info = await context.bot.send_message(
        SOURCE_GROUP_ID,
        f"{get_username(user)} twoje ogłoszenie zostało opublikowane."
    )
    context.job_queue.run_once(
        delete_message_job, SOURCE_DELETE_AFTER,
        data={"chat_id": SOURCE_GROUP_ID, "message_id": info.message_id}
    )

    # TARGET → delete po 12h
    for m in (forwarded, sign):
        context.job_queue.run_once(
            delete_message_job, TARGET_DELETE_AFTER,
            data={"chat_id": TARGET_GROUP_ID, "message_id": m.message_id}
        )

# ================== START ==================

def main():
    load_warns()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.Regex(r"^/mywarns$"), handle_mywarns))
    app.add_handler(MessageHandler(filters.Regex(r"^/mycooldown$"), handle_mycooldown))
    app.add_handler(MessageHandler(filters.ALL, handle_group_message))

    print("BOT ONLINE | #WTS + HEADER FILTER | FINAL")
    app.run_polling()

if __name__ == "__main__":
    main()

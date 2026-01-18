from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
from PIL import Image, ImageDraw, ImageFont
import os, re, unicodedata

# ========= CONFIG =========
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
TOPIC_ID = int(os.getenv("TOPIC_ID"))

FONT_PATH = "fonts/DejaVuSans.ttf"

WIDTH = 1080
BG = (10, 10, 10)
WHITE = (240, 240, 240)
USER_COLOR = (0, 190, 255)

# 🔥 EMOJI OVERDOSE (60+)
EMOJI_TOP = "💎🔥✨💥⚡🌟⭐️💫🔮👑💰💵💴💶💷💸🧨🚀🛸🧠🧪⚗️🧬🦠🍀🍏🍎🍃🌿🎷🎶🎵🎧🎼"
EMOJI_HL = "💎🔥✨⚡🌟⭐️💫🔮👑💰🧠🧪⚗️🧬🍀🍏🍃🌿🎷"
EMOJI_HR = "🎷🌿🍃🍏🍀🧬⚗️🧪🧠💰👑🔮💫⭐️🌟⚡✨🔥💎"
EMOJI_BOTTOM = "📦📩📨✉️📬📭📪🚚🚛🚐🛵🏍️🚲🔒🔐🛡️⚔️🗝️🧾🧮📊📈📉💼🧳"

LINE_H = 52
# ==========================

def get_username(user):
    return f"@{user.username}" if user.username else (user.first_name or "Użytkownik")

def normalize_unicode(text: str) -> str:
    # KLUCZ: usuwa fancy unicode → ASCII (koniec kwadratów)
    return (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
    )

def clean_text(text: str):
    text = normalize_unicode(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return [l.strip() for l in text.split("\n")]

def text_to_color(text: str):
    r = g = b = 0
    for i, ch in enumerate(text.lower()):
        v = ord(ch)
        if i % 3 == 0: r += v
        elif i % 3 == 1: g += v
        else: b += v
    return (r % 180 + 40, g % 180 + 40, b % 180 + 40)

def is_header(line: str):
    return not re.search(r"\d", line) and len(line) >= 3

def render(username: str, raw_text: str):
    lines = clean_text(raw_text)

    f_user = ImageFont.truetype(FONT_PATH, 46)
    f_head = ImageFont.truetype(FONT_PATH, 42)
    f_txt  = ImageFont.truetype(FONT_PATH, 36)

    img_h = 360 + len(lines) * LINE_H
    img = Image.new("RGB", (WIDTH, img_h), BG)
    d = ImageDraw.Draw(img)

    y = 34

    # 🔝 USERNAME + EMOJI (GÓRA)
    top = f"{EMOJI_TOP}  {username}  {EMOJI_TOP}"
    w = d.textlength(top, font=f_user)
    d.text(((WIDTH - w) / 2, y), top, USER_COLOR, f_user)
    y += 96

    # 📄 CONTENT (NAPRAWIONY)
    for line in lines:
        if not line:
            y += 22
            continue

        if is_header(line):
            color = text_to_color(line)
            hdr = f"{EMOJI_HL}  {line}  {EMOJI_HR}"
            w = d.textlength(hdr, font=f_head)
            d.text(((WIDTH - w) / 2, y), hdr, color, f_head)
            y += 68
        else:
            w = d.textlength(line, font=f_txt)
            d.text(((WIDTH - w) / 2, y), line, WHITE, f_txt)
            y += LINE_H

    y += 28

    # 🔻 USERNAME + EMOJI (DÓŁ)
    bot = f"{EMOJI_BOTTOM}  {username}  {EMOJI_BOTTOM}"
    w = d.textlength(bot, font=f_user)
    d.text(((WIDTH - w) / 2, y), bot, USER_COLOR, f_user)

    path = "/tmp/post.png"
    img.save(path)
    return path

async def handle_pm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.message.chat.type != "private":
        return

    user = update.message.from_user
    username = get_username(user)
    text = update.message.text or ""

    img = render(username, text)

    # ⬇️ CAPTION = @username POD ZDJĘCIEM
    await context.bot.send_photo(
        chat_id=GROUP_ID,
        message_thread_id=TOPIC_ID,
        photo=open(img, "rb"),
        caption=username
    )

    await update.message.reply_text("✅ Wysłano (naprawione + emoji).")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_pm))
    print("FINAL NORMALIZED EMOJI BOT ONLINE")
    app.run_polling()

if __name__ == "__main__":
    main()

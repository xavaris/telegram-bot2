from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
from PIL import Image, ImageDraw, ImageFont
import os
import re

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
TOPIC_ID = int(os.getenv("TOPIC_ID"))

FONT_PATH = "fonts/DejaVuSans.ttf"

IMG_WIDTH = 1080
BG_COLOR = (12, 12, 12)
TEXT_COLOR = (235, 235, 235)
USER_COLOR = (0, 190, 255)

LINE_HEIGHT = 52
MARGIN_TOP = 50
MARGIN_BOTTOM = 60
# ============================================

def get_username(user):
    if user.username:
        return f"@{user.username}"
    return user.first_name or "Użytkownik"

def clean_text(text: str) -> list[str]:
    # usuń problematyczne znaki (kwadraty itp.)
    text = re.sub(r"[□■▪▫◻◼]+", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return [line.strip() for line in text.split("\n")]

def text_to_color(text: str):
    r = g = b = 0
    for i, ch in enumerate(text.lower()):
        val = ord(ch)
        if i % 3 == 0:
            r += val
        elif i % 3 == 1:
            g += val
        else:
            b += val
    return (r % 180 + 40, g % 180 + 40, b % 180 + 40)

def is_header(line: str):
    return (
        not re.search(r"\d", line)
        and len(line) >= 3
    )

def render_image(username: str, raw_text: str):
    lines = clean_text(raw_text)

    font_user = ImageFont.truetype(FONT_PATH, 46)
    font_header = ImageFont.truetype(FONT_PATH, 44)
    font_text = ImageFont.truetype(FONT_PATH, 38)

    img_height = (
        MARGIN_TOP +
        len(lines) * LINE_HEIGHT +
        200
    )

    img = Image.new("RGB", (IMG_WIDTH, img_height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    y = MARGIN_TOP

    # ===== USERNAME TOP =====
    uw = draw.textlength(username, font=font_user)
    draw.text(((IMG_WIDTH - uw) / 2, y), username, USER_COLOR, font_user)
    y += 80

    # ===== CONTENT =====
    for line in lines:
        if not line:
            y += 24
            continue

        if is_header(line):
            color = text_to_color(line)
            w = draw.textlength(line, font=font_header)
            draw.text(((IMG_WIDTH - w) / 2, y), line, color, font_header)
            y += 64
        else:
            w = draw.textlength(line, font=font_text)
            draw.text(((IMG_WIDTH - w) / 2, y), line, TEXT_COLOR, font_text)
            y += LINE_HEIGHT

    y += 30

    # ===== USERNAME BOTTOM =====
    uw = draw.textlength(username, font=font_user)
    draw.text(((IMG_WIDTH - uw) / 2, y), username, USER_COLOR, font_user)

    path = "/tmp/post.png"
    img.save(path)
    return path

async def handle_pm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.message.chat.type != "private":
        return

    user = update.message.from_user
    username = get_username(user)
    text = update.message.text

    image_path = render_image(username, text)

    await context.bot.send_photo(
        chat_id=GROUP_ID,
        message_thread_id=TOPIC_ID,
        photo=open(image_path, "rb")
    )

    await update.message.reply_text("✅ Ogłoszenie poprawione i wysłane.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_pm))
    print("SMART GRAPHIC BOT ONLINE")
    app.run_polling()

if __name__ == "__main__":
    main()

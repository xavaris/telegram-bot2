from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    filters,
)
from PIL import Image, ImageDraw, ImageFont
import os
import textwrap

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
TOPIC_WTS_ID = int(os.getenv("TOPIC_WTS_ID"))

WIDTH = 1080
PADDING = 60

def get_name(user):
    if user.username:
        return f"@{user.username}"
    return user.first_name or "Użytkownik"

def render_premium_image(username, text):
    img = Image.new("RGB", (WIDTH, 800), color=(15, 15, 15))
    draw = ImageDraw.Draw(img)

    # domyślna czcionka (działa na Railway)
    font_title = ImageFont.load_default()
    font_text = ImageFont.load_default()

    y = PADDING

    draw.text((PADDING, y), "💎 WTS", fill=(255, 215, 0), font=font_title)
    y += 50

    draw.text((PADDING, y), f"👤 {username}", fill=(200, 200, 200), font=font_text)
    y += 50

    for line in textwrap.wrap(text, 40):
        draw.text((PADDING, y), line, fill=(255, 255, 255), font=font_text)
        y += 30

    path = "/tmp/out.png"
    img.save(path)
    return path

async def handle_pm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.message.chat.type != "private":
        return

    user = update.message.from_user
    text = update.message.text
    username = get_name(user)

    image_path = render_premium_image(username, text)

    await context.bot.send_photo(
        chat_id=GROUP_ID,
        message_thread_id=TOPIC_WTS_ID,
        photo=open(image_path, "rb")
    )

    await update.message.reply_text("✅ Ogłoszenie wysłane do WTS.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_pm))
    print("PREMIUM WTS BOT DZIAŁA")
    app.run_polling()

if __name__ == "__main__":
    main()

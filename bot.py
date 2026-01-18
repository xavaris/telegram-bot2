from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
from PIL import Image, ImageDraw, ImageFont
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
TOPIC_ID = int(os.getenv("TOPIC_ID"))

FONT_PATH = "fonts/DejaVuSans.ttf"

IMG_WIDTH = 1080
BG_COLOR = (15, 15, 15)
TEXT_COLOR = (255, 255, 255)
USER_COLOR = (0, 200, 255)

def get_username(user):
    if user.username:
        return f"@{user.username}"
    return user.first_name or "Użytkownik"

def render_image(username, text):
    font_user = ImageFont.truetype(FONT_PATH, 46)
    font_text = ImageFont.truetype(FONT_PATH, 40)

    lines = text.split("\n")

    # policz wysokość obrazu dynamicznie
    line_height = 56
    img_height = 300 + len(lines) * line_height

    img = Image.new("RGB", (IMG_WIDTH, img_height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    y = 60

    # 🔝 USERNAME (GÓRA)
    w = draw.textlength(username, font=font_user)
    draw.text(((IMG_WIDTH - w) / 2, y), username, fill=USER_COLOR, font=font_user)
    y += 90

    # 📄 TREŚĆ USERA – WYŚRODKOWANA
    for line in lines:
        line_width = draw.textlength(line, font=font_text)
        draw.text(
            ((IMG_WIDTH - line_width) / 2, y),
            line,
            fill=TEXT_COLOR,
            font=font_text
        )
        y += line_height

    y += 40

    # 🔻 USERNAME (DÓŁ)
    w = draw.textlength(username, font=font_user)
    draw.text(((IMG_WIDTH - w) / 2, y), username, fill=USER_COLOR, font=font_user)

    path = "/tmp/post.png"
    img.save(path)
    return path

async def handle_pm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.message.chat.type != "private":
        return

    user = update.message.from_user
    text = update.message.text
    username = get_username(user)

    image_path = render_image(username, text)

    await context.bot.send_photo(
        chat_id=GROUP_ID,
        message_thread_id=TOPIC_ID,
        photo=open(image_path, "rb")
    )

    await update.message.reply_text("✅ Wysłano.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_pm))
    print("CENTER TEXT BOT ONLINE")
    app.run_polling()

if __name__ == "__main__":
    main()

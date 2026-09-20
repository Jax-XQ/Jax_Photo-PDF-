import os
import tempfile
from pathlib import Path
from threading import Thread

from flask import Flask
from PIL import Image
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================
# إعدادات البوت
# =========================

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

# نخزن صور المستخدمين مؤقتًا
user_images = {}


# =========================
# Flask - حتى يكون عندنا Web Service
# =========================

web = Flask(__name__)


@web.route("/")
def home():
    return "Bot is running!"


def run_web():
    port = int(os.getenv("PORT", "10000"))
    web.run(host="0.0.0.0", port=port)


# =========================
# أوامر Telegram
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    user_images[user_id] = []

    await update.message.reply_text(
        "👋 أهلاً بيك!\n\n"
        "📷 أرسللي صورة أو عدة صور.\n"
        "وبعد ما تخلص اكتب:\n\n"
        "/pdf\n\n"
        "📄 وأنا أحولهن إلى ملف PDF."
    )


async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in user_images:
        user_images[user_id] = []

    photo = update.message.photo[-1]

    file = await context.bot.get_file(photo.file_id)

    temp_dir = Path(tempfile.gettempdir()) / "telegram_pdf_bot"
    temp_dir.mkdir(parents=True, exist_ok=True)

    file_path = temp_dir / f"{user_id}_{len(user_images[user_id])}.jpg"

    await file.download_to_drive(str(file_path))

    user_images[user_id].append(str(file_path))

    count = len(user_images[user_id])

    await update.message.reply_text(
        f"✅ استلمت الصورة رقم {count}\n\n"
        "📷 إذا عندك صور ثانية أرسلها.\n"
        "ولما تخلص اكتب /pdf"
    )


async def create_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    images = user_images.get(user_id, [])

    if not images:
        await update.message.reply_text(
            "❌ ما عندي أي صور.\n"
            "أرسل صورة أولاً."
        )
        return

    await update.message.reply_text(
        "⏳ جاري تحويل الصور إلى PDF..."
    )

    try:
        pil_images = []

        for image_path in images:
            img = Image.open(image_path).convert("RGB")
            pil_images.append(img)

        pdf_path = (
            Path(tempfile.gettempdir())
            / f"telegram_pdf_{user_id}.pdf"
        )

        first = pil_images[0]
        others = pil_images[1:]

        first.save(
            pdf_path,
            "PDF",
            resolution=100.0,
            save_all=True,
            append_images=others,
        )

        with open(pdf_path, "rb") as pdf_file:
            await update.message.reply_document(
                document=pdf_file,
                filename="images.pdf",
                caption="✅ تم تحويل الصور إلى PDF"
            )

        # تنظيف الملفات المؤقتة
        for image_path in images:
            try:
                os.remove(image_path)
            except OSError:
                pass

        try:
            os.remove(pdf_path)
        except OSError:
            pass

        user_images[user_id] = []

    except Exception as error:
        print("PDF ERROR:", error)

        await update.message.reply_text(
            "❌ صار خطأ أثناء إنشاء الـPDF."
        )


# =========================
# تشغيل البوت
# =========================

def main():
    Thread(target=run_web, daemon=True).start()

    application = Application.builder().token(TOKEN).build()

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("pdf", create_pdf)
    )

    application.add_handler(
        MessageHandler(
            filters.PHOTO,
            receive_photo
        )
    )

    print("🤖 Bot started!")

    application.run_polling()


if __name__ == "__main__":
    main()
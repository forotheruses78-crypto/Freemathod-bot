import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")
MINI_APP_URL = "https://t.me/freemathodefbytServicebd_bot/Enroll"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📚 Enroll Now", url=MINI_APP_URL)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "স্বাগতম Freemathod-Facebook-YouTube-service-BD -এ! 🎉\n\n"
        "কপিরাইট ফ্রি ফেসবুক ভিডিও ও ইউটিউব ভিডিও পেতে নিচের বাটনে ক্লিক করুন।",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        " যেকোনো সাহায্যের জন্য এডমিনের সাথে যোগাযোগ করুন।"
    )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.run_polling()

if __name__ == "__main__":
    main()

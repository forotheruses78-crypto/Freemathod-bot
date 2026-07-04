import os
import threading
import asyncio
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")
MINI_APP_URL = "https://t.me/freemathodefbytServicebd_bot/Enroll"

web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is running!"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📚 Enroll Now — কোর্সে ভর্তি হন", url=MINI_APP_URL)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "স্বাগতম Wave BD Course-এ! 🎉\n\n"
        "ফেসবুক মার্কেটিং ও ইউটিউব ভিডিও তৈরির সম্পূর্ণ কোর্সে ভর্তি হতে নিচের বাটনে ক্লিক করুন।",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "কোর্স সংক্রান্ত সাহায্যের জন্য এডমিনের সাথে যোগাযোগ করুন।"
    )

def run_bot():
    asyncio.set_event_loop(asyncio.new_event_loop())
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.run_polling(stop_signals=None)

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)

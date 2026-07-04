import os
import threading
import asyncio
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")
MINI_APP_URL = "https://t.me/freemathodefbytServicebd_bot/Enroll"

# এখানে ফ্রি ভিডিওর file_id বসাবো (এখন খালি রাখছি)
FREE_VIDEO_FILE_ID = "BAACAgUAAxkBAAMaakjp1bpUVzexkRFwbrdulzm4dYIAAhYhAALAx0hWpBP6Frl9A5c8BA"
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is running!"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎁 Free Video", callback_data="free_video")],
        [InlineKeyboardButton("📚 Premium video", url=MINI_APP_URL)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "স্বাগতম Freemathod Facebook & YouTube Service Bd-এ! 🎉\n\n"
        "ফ্রি ভিডিও দেখতে বা প্রিমিয়াম ভিডিও পেতে নিচের বাটনে ক্লিক করুন।",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "free_video":
        if FREE_VIDEO_FILE_ID:
            await context.bot.send_video(
                chat_id=query.message.chat_id,
                video=FREE_VIDEO_FILE_ID,
                caption="🎁ফ্রি ভিডিও!"
            )
        else:
            await query.message.reply_text("ফ্রি ভিডিও শীঘ্রই যুক্ত হবে।")

# সাহায্যকারী: যখন তুমি (অ্যাডমিন) ভিডিও পাঠাবে, বট file_id দেখাবে
async def get_file_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.video:
        file_id = update.message.video.file_id
        await update.message.reply_text(f"✅ File ID:\n\n{file_id}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("সাহায্যের জন্য এডমিনের সাথে যোগাযোগ করুন।")

def run_bot():
    asyncio.set_event_loop(asyncio.new_event_loop())
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.VIDEO, get_file_id))
    from telegram.ext import CallbackQueryHandler
    app.add_handler(CallbackQueryHandler(button_handler))
    app.run_polling(stop_signals=None)

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)

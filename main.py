import os
import json
import threading
import asyncio
import requests
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes
)

# ---------- কনফিগারেশন ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MINI_APP_URL = "https://forotheruses78-crypto.github.io/Freemathod-Facebook-YouTube-service-BD/"
IMGBB_API_KEY = os.environ.get("IMGBB_API_KEY")
ADMIN_USER_ID = int(os.environ.get("ADMIN_USER_ID"))

# ---------- Firebase সেটআপ ----------
cred = credentials.Certificate("/etc/secrets/firebase-key.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# ---------- Conversation States (addfree কমান্ডের ধাপ) ----------
THUMBNAIL, VIDEO, TITLE = range(3)
temp_data = {}  # সাময়িকভাবে ডেটা রাখার জন্য

# ---------- Flask (Render-কে জীবিত দেখানোর জন্য) ----------
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is running!"

# ---------- /start কমান্ড ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎁 Free Video", callback_data="free_video")],
        [InlineKeyboardButton("📚 Premium Video", web_app=WebAppInfo(url=MINI_APP_URL))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "স্বাগতম Freemathod Facebook & YouTube Service Bd-এ! 🎉\n\n"
        "ফ্রি ভিডিও দেখতে বা প্রিমিয়াম ভিডিও পেতে নিচের বাটনে ক্লিক করুন।",
        reply_markup=reply_markup
    )

# ---------- Free Video বাটনের রেসপন্স ----------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "free_video":
        free_video_app_url = "https://forotheruses78-crypto.github.io/Freemathod-Facebook-YouTube-service-BD/gallery.html"
        keyboard = [[InlineKeyboardButton("Free Video", web_app=WebAppInfo(url=free_video_app_url))]]
        await query.message.reply_text(
            "নিচের বাটনে ক্লিক করে ফ্রি ভিডিও গ্যালারি দেখুন:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ---------- /addfree কমান্ড শুরু (শুধু Admin) ----------
async def addfree_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("দুঃখিত, এই কমান্ড শুধু অ্যাডমিনের জন্য।")
        return ConversationHandler.END

    await update.message.reply_text("ঠিক আছে! প্রথমে থাম্বনেইল ছবিটা পাঠান।")
    return THUMBNAIL

# ---------- থাম্বনেইল রিসিভ করা ----------
async def receive_thumbnail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]  # সবচেয়ে বড় সাইজের ছবি
    file = await context.bot.get_file(photo.file_id)
    file_path = "temp_thumb.jpg"
    await file.download_to_drive(file_path)

    # imgbb-তে আপলোড করা
    with open(file_path, "rb") as img_file:
        response = requests.post(
            "https://api.imgbb.com/1/upload",
            params={"key": IMGBB_API_KEY},
            files={"image": img_file}
        )
    result = response.json()

    if result.get("success"):
        thumbnail_url = result["data"]["url"]
        temp_data[update.effective_user.id] = {"thumbnail_url": thumbnail_url}
        await update.message.reply_text("✅ থাম্বনেইল আপলোড হয়েছে! এখন ভিডিওটা পাঠান।")
        return VIDEO
    else:
        await update.message.reply_text("❌ থাম্বনেইল আপলোডে সমস্যা হয়েছে, আবার চেষ্টা করুন।")
        return THUMBNAIL

# ---------- ভিডিও রিসিভ করা ----------
async def receive_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video_file_id = update.message.video.file_id
    user_id = update.effective_user.id
    temp_data[user_id]["file_id"] = video_file_id
    await update.message.reply_text("✅ ভিডিও পাওয়া গেছে! এখন ভিডিওর টাইটেল লিখুন।")
    return TITLE

# ---------- টাইটেল রিসিভ করা এবং Firebase-এ সেভ ----------
async def receive_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    title = update.message.text
    data = temp_data[user_id]

    # ইউনিক video_code বানানো (কতগুলো ভিডিও আছে তার উপর ভিত্তি করে)
    videos_ref = db.collection("free_videos")
    count = len(list(videos_ref.stream()))
    video_code = f"video{count + 1}"

    videos_ref.add({
        "title": title,
        "thumbnail_url": data["thumbnail_url"],
        "file_id": data["file_id"],
        "video_code": video_code
    })

    await update.message.reply_text(f"🎉 ভিডিও সফলভাবে যোগ হয়েছে! (কোড: {video_code})")
    del temp_data[user_id]
    return ConversationHandler.END

# ---------- বাতিল করার কমান্ড ----------
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("প্রক্রিয়া বাতিল করা হয়েছে।")
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("সাহায্যের জন্য এডমিনের সাথে যোগাযোগ করুন।")

# ---------- বট রান করা ----------
def run_bot():
    asyncio.set_event_loop(asyncio.new_event_loop())
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_handler))

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("addfree", addfree_start)],
        states={
            THUMBNAIL: [MessageHandler(filters.PHOTO, receive_thumbnail)],
            VIDEO: [MessageHandler(filters.VIDEO, receive_video)],
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_title)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv_handler)

    app.run_polling(stop_signals=None)

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)

import os
import threading
import asyncio
import requests
from datetime import datetime, timezone, timedelta
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    filters, ContextTypes
)

BOT_TOKEN = os.environ.get("DELIVERY_BOT_TOKEN")
IMGBB_API_KEY = os.environ.get("IMGBB_API_KEY")
ADMIN_USER_IDS = [int(x.strip()) for x in os.environ.get("ADMIN_USER_ID").split(",")]

cred = credentials.Certificate("/etc/secrets/firebase-key.json")
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(cred)
db = firestore.client()

THUMBNAIL, VIDEO, TITLE = range(3)
temp_data = {}

web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Delivery bot is running!"

# ---------- ভিডিও ডেলিভারি (আগের মতোই) ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args

    if not args:
        await update.message.reply_text(
            "স্বাগতম! এই বট থেকে আপনার চাওয়া ভিডিও ডেলিভার করা হবে।"
        )
        return

    video_code = args[0]
    videos_ref = db.collection("free_videos")
    query = videos_ref.where("video_code", "==", video_code).limit(1)
    results = list(query.stream())

    if not results:
        await update.message.reply_text("দুঃখিত, এই ভিডিওটি খুঁজে পাওয়া যায়নি।")
        return

    video_data = results[0].to_dict()
    file_id = video_data.get("file_id")
    title = video_data.get("title", "")

    await context.bot.send_video(
        chat_id=update.effective_chat.id,
        video=file_id,
        caption=f"🎁 {title}"
    )

# ---------- Admin: /addfree কমান্ড (এখন এই বটেই) ----------
async def addfree_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USER_IDS:
        await update.message.reply_text("দুঃখিত, এই কমান্ড শুধু অ্যাডমিনের জন্য।")
        return ConversationHandler.END
    await update.message.reply_text("ঠিক আছে! প্রথমে থাম্বনেইল ছবিটা পাঠান।")
    return THUMBNAIL

async def receive_thumbnail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    file_path = "temp_thumb.jpg"
    await file.download_to_drive(file_path)

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

async def receive_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video_file_id = update.message.video.file_id
    user_id = update.effective_user.id
    temp_data[user_id]["file_id"] = video_file_id
    await update.message.reply_text("✅ ভিডিও পাওয়া গেছে! এখন ভিডিওর টাইটেল লিখুন।")
    return TITLE

async def receive_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    title = update.message.text
    data = temp_data[user_id]

    videos_ref = db.collection("free_videos")
    count = len(list(videos_ref.stream()))
    video_code = f"video{count + 1}"

    bd_time = datetime.now(timezone.utc) + timedelta(hours=6)
    if 6 <= bd_time.hour < 18:
        category = "morning"
    else:
        category = "night"

    videos_ref.add({
        "title": title,
        "thumbnail_url": data["thumbnail_url"],
        "file_id": data["file_id"],
        "video_code": video_code,
        "category": category
    })

    category_label = "দিনের ভিডিও" if category == "morning" else "রাতের ভিডিও"
    await update.message.reply_text(f"🎉 ভিডিও সফলভাবে যোগ হয়েছে! (কোড: {video_code}, বিভাগ: {category_label})")
    del temp_data[user_id]
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("প্রক্রিয়া বাতিল করা হয়েছে।")
    return ConversationHandler.END

def run_bot():
    asyncio.set_event_loop(asyncio.new_event_loop())
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

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
    port = int(os.environ.get("PORT", 10001))
    web_app.run(host="0.0.0.0", port=port)

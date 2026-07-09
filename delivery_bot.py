import os
import threading
import asyncio
import requests
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes
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

P_THUMBNAIL, P_VIDEO, P_TITLE, P_CATEGORY = range(10, 14)
premium_temp_data = {}

CATEGORY_LABELS = {
    "fb_video": "ফেসবুক ভিডিও",
    "yt_shorts": "ইউটিউব শর্টস",
    "yt_long": "ইউটিউব লং ভিডিও",
    "tutorial": "টিউটোরিয়াল"
}

web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Delivery bot is running!"

def get_time_label():
    bd_time = datetime.now(timezone.utc) + timedelta(hours=6)
    if 6 <= bd_time.hour < 18:
        return "day"
    else:
        return "night"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args

    if not args:
        await update.message.reply_text(
            "স্বাগতম! এই বট থেকে আপনার চাওয়া ভিডিও ডেলিভার করা হবে।"
        )
        return

    video_code = args[0]

    if video_code.startswith("pvideo"):
        collection_name = "premium_videos"
    else:
        collection_name = "free_videos"

    videos_ref = db.collection(collection_name)
    query = videos_ref.where("video_code", "==", video_code).limit(1)
    results = list(query.stream())

    if not results:
        await update.message.reply_text("দুঃখিত, এই ভিডিওটি খুঁজে পাওয়া যায়নি।")
        return

    video_data = results[0].to_dict()
    file_id = video_data.get("file_id")
    title = video_data.get("title", "")

    sent_message = await context.bot.send_video(
        chat_id=update.effective_chat.id,
        video=file_id,
        caption=f"🎁 {title}"
    )

    notice_message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="⚠️ সতর্কতা: কিছু সময় পর এই ভিডিওটি চ্যাট থেকে অটোমেটিক ডিলিট হয়ে যাবে।"
    )

    asyncio.create_task(
        delete_after_delay(context, update.effective_chat.id, sent_message.message_id, notice_message.message_id)
    )


async def delete_after_delay(context, chat_id, video_message_id, notice_message_id, delay_seconds=1200):
    await asyncio.sleep(delay_seconds)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=video_message_id)
    except Exception:
        pass
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=notice_message_id)
    except Exception:
        pass
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text="🗑️ Your files have been deleted from chat after some time."
        )
    except Exception:
        pass


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

    time_label = get_time_label()
    category_field = "morning" if time_label == "day" else "night"

    videos_ref.add({
        "title": title,
        "thumbnail_url": data["thumbnail_url"],
        "file_id": data["file_id"],
        "video_code": video_code,
        "category": category_field,
        "created_at": firestore.SERVER_TIMESTAMP
    })

    category_label = "দিনের ভিডিও" if category_field == "morning" else "রাতের ভিডিও"
    await update.message.reply_text(f"🎉 ভিডিও সফলভাবে যোগ হয়েছে! (কোড: {video_code}, বিভাগ: {category_label})")
    del temp_data[user_id]
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("প্রক্রিয়া বাতিল করা হয়েছে।")
    return ConversationHandler.END


async def addpremium_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USER_IDS:
        await update.message.reply_text("দুঃখিত, এই কমান্ড শুধু অ্যাডমিনের জন্য।")
        return ConversationHandler.END
    await update.message.reply_text("ঠিক আছে! প্রথমে থাম্বনেইল ছবিটা পাঠান।")
    return P_THUMBNAIL

async def receive_thumbnail_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    file_path = "temp_thumb_premium.jpg"
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
        premium_temp_data[update.effective_user.id] = {"thumbnail_url": thumbnail_url}
        await update.message.reply_text("✅ থাম্বনেইল আপলোড হয়েছে! এখন ভিডিওটা পাঠান।")
        return P_VIDEO
    else:
        await update.message.reply_text("❌ থাম্বনেইল আপলোডে সমস্যা হয়েছে, আবার চেষ্টা করুন।")
        return P_THUMBNAIL

async def receive_video_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video_file_id = update.message.video.file_id
    user_id = update.effective_user.id
    premium_temp_data[user_id]["file_id"] = video_file_id
    await update.message.reply_text("✅ ভিডিও পাওয়া গেছে! এখন ভিডিওর টাইটেল লিখুন।")
    return P_TITLE

async def receive_title_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    title = update.message.text
    premium_temp_data[user_id]["title"] = title

    keyboard = [
        [InlineKeyboardButton("ফেসবুক ভিডিও", callback_data="cat_fb_video")],
        [InlineKeyboardButton("ইউটিউব শর্টস", callback_data="cat_yt_shorts")],
        [InlineKeyboardButton("ইউটিউব লং ভিডিও", callback_data="cat_yt_long")],
        [InlineKeyboardButton("টিউটোরিয়াল", callback_data="cat_tutorial")],
    ]
    await update.message.reply_text(
        "এই ভিডিওটা কোন ক্যাটাগরিতে যোগ হবে?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return P_CATEGORY

async def receive_category_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    category_map = {
        "cat_fb_video": "fb_video",
        "cat_yt_shorts": "yt_shorts",
        "cat_yt_long": "yt_long",
        "cat_tutorial": "tutorial",
    }
    category = category_map.get(query.data)

    user_id = query.from_user.id
    data = premium_temp_data[user_id]

    videos_ref = db.collection("premium_videos")
    count = len(list(videos_ref.stream()))
    video_code = f"pvideo{count + 1}"

    time_label = get_time_label()

    videos_ref.add({
        "title": data["title"],
        "thumbnail_url": data["thumbnail_url"],
        "file_id": data["file_id"],
        "video_code": video_code,
        "category": category,
        "time_label": time_label,
        "created_at": firestore.SERVER_TIMESTAMP
    })

    await query.edit_message_text(
        f"🎉 প্রিমিয়াম ভিডিও সফলভাবে যোগ হয়েছে!\n"
        f"কোড: {video_code}\n"
        f"ক্যাটাগরি: {CATEGORY_LABELS.get(category)}"
    )
    del premium_temp_data[user_id]
    return ConversationHandler.END


def run_bot():
    asyncio.set_event_loop(asyncio.new_event_loop())
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    free_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("addfree", addfree_start)],
        states={
            THUMBNAIL: [MessageHandler(filters.PHOTO, receive_thumbnail)],
            VIDEO: [MessageHandler(filters.VIDEO, receive_video)],
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_title)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(free_conv_handler)

    premium_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("addpremium", addpremium_start)],
        states={
            P_THUMBNAIL: [MessageHandler(filters.PHOTO, receive_thumbnail_premium)],
            P_VIDEO: [MessageHandler(filters.VIDEO, receive_video_premium)],
            P_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_title_premium)],
            P_CATEGORY: [CallbackQueryHandler(receive_category_premium)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(premium_conv_handler)

    app.run_polling(stop_signals=None)

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    port = int(os.environ.get("PORT", 10001))
    web_app.run(host="0.0.0.0", port=port)

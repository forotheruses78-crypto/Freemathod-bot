import os
import threading
import asyncio
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = os.environ.get("DELIVERY_BOT_TOKEN")

# ---------- Firebase সেটআপ ----------
cred = credentials.Certificate("/etc/secrets/firebase-key.json")

# একবারই Firebase App ইনিশিয়ালাইজ করা (কারণ একই সার্ভারে একবারই করা যায়)
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(cred)

db = firestore.client()

web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Delivery bot is running!"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args

    if not args:
        await update.message.reply_text(
            "স্বাগতম! এই বট থেকে আপনার চাওয়া ভিডিও ডেলিভার করা হবে।"
        )
        return

    video_code = args[0]

    # Firebase থেকে এই video_code দিয়ে ভিডিও খোঁজা
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

def run_bot():
    asyncio.set_event_loop(asyncio.new_event_loop())
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling(stop_signals=None)

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    port = int(os.environ.get("PORT", 10001))
    web_app.run(host="0.0.0.0", port=port)

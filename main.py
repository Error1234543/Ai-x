
import os
import time
import json
import base64
import requests
import telebot
from flask import Flask

# ====== CONFIG ======
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OWNER_ID = int(os.getenv("OWNER_ID", "7447651332"))
PORT = int(os.getenv("PORT", 8000))
# ====================

if not BOT_TOKEN or not GEMINI_API_KEY:
    raise RuntimeError("❌ Missing BOT_TOKEN or GEMINI_API_KEY environment variables!")

bot = telebot.TeleBot(BOT_TOKEN)
AUTH_FILE = "auth.json"

# ====== AUTH SYSTEM ======
if not os.path.exists(AUTH_FILE):
    default = {
        "owners": [OWNER_ID],
        "allowed_users": [OWNER_ID],
        "allowed_groups": []
    }
    with open(AUTH_FILE, "w") as f:
        json.dump(default, f, indent=2)

def load_auth():
    with open(AUTH_FILE, "r") as f:
        return json.load(f)

def save_auth(data):
    with open(AUTH_FILE, "w") as f:
        json.dump(data, f, indent=2)

def is_owner(user_id):
    auth = load_auth()
    return user_id in auth["owners"]

def is_allowed(user_id, chat_id):
    auth = load_auth()
    return (
        user_id in auth["owners"] or
        user_id in auth["allowed_users"] or
        chat_id in auth["allowed_groups"]
    )

# ====== GEMINI REQUEST ======
def ask_gemini(prompt, image_bytes=None):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

        contents = [{"parts": [{"text": prompt}]}]

        if image_bytes:
            b64 = base64.b64encode(image_bytes).decode("utf-8")
            contents[0]["parts"].append({
                "inline_data": {"mime_type": "image/jpeg", "data": b64}
            })

        res = requests.post(url, json={"contents": contents}, timeout=60)
        res.raise_for_status()

        data = res.json()
        text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "⚠️ No response from Gemini.")
        return text

    except requests.exceptions.HTTPError as e:
        if "404" in str(e):
            return "❌ Gemini API model not found — use correct API key & model."
        return f"❌ Gemini HTTP Error: {e}"
    except Exception as e:
        return f"❌ Gemini Error: {e}"

# ====== COMMANDS ======
@bot.message_handler(commands=['start'])
def start(msg):
    if not is_allowed(msg.from_user.id, msg.chat.id):
        return bot.reply_to(msg, "🚫 Not authorized.")
    bot.reply_to(msg, "🤖 Hello! Send me any NEET/JEE question or image to solve using Gemini AI.")

@bot.message_handler(commands=['add'])
def add_user(msg):
    if not is_owner(msg.from_user.id):
        return bot.reply_to(msg, "🚫 Only owner can use this command.")
    try:
        uid = int(msg.text.split()[1])
        data = load_auth()
        if uid not in data["allowed_users"]:
            data["allowed_users"].append(uid)
            save_auth(data)
            bot.reply_to(msg, f"✅ Added user ID {uid} to allowed list.")
        else:
            bot.reply_to(msg, "⚠️ User already allowed.")
    except Exception:
        bot.reply_to(msg, "⚠️ Usage: /add <user_id>")

@bot.message_handler(commands=['remove'])
def remove_user(msg):
    if not is_owner(msg.from_user.id):
        return bot.reply_to(msg, "🚫 Only owner can use this command.")
    try:
        uid = int(msg.text.split()[1])
        data = load_auth()
        if uid in data["allowed_users"]:
            data["allowed_users"].remove(uid)
            save_auth(data)
            bot.reply_to(msg, f"✅ Removed user ID {uid}.")
        else:
            bot.reply_to(msg, "⚠️ User not found.")
    except Exception:
        bot.reply_to(msg, "⚠️ Usage: /remove <user_id>")

# ====== TEXT & IMAGE HANDLERS ======
@bot.message_handler(content_types=['text'])
def text_query(msg):
    if not is_allowed(msg.from_user.id, msg.chat.id):
        return bot.reply_to(msg, "🚫 Not authorized.")
    bot.send_chat_action(msg.chat.id, 'typing')
    ans = ask_gemini(msg.text)
    bot.reply_to(msg, ans[:4000])

@bot.message_handler(content_types=['photo'])
def image_query(msg):
    if not is_allowed(msg.from_user.id, msg.chat.id):
        return bot.reply_to(msg, "🚫 Not authorized.")
    bot.send_chat_action(msg.chat.id, 'typing')
    file_info = bot.get_file(msg.photo[-1].file_id)
    img = bot.download_file(file_info.file_path)
    ans = ask_gemini("Solve this NEET/JEE question step-by-step:", image_bytes=img)
    bot.reply_to(msg, ans[:4000])

# ====== FLASK HEALTH CHECK ======
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ AI Bot (Polling mode) is running fine!", 200

# ====== START POLLING ======
if __name__ == '__main__':
    print("✅ Bot starting in POLLING mode...")
    from threading import Thread
    Thread(target=lambda: bot.infinity_polling(skip_pending=True, timeout=60)).start()
    app.run(host='0.0.0.0', port=PORT)
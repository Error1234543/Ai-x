import os
import time
import json
import base64
import requests
import telebot
from flask import Flask, request

# ====== CONFIG ======
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OWNER_ID = int(os.getenv("OWNER_ID", "7447651332"))
PORT = int(os.getenv("PORT", 8000))
APP_NAME = os.getenv("APP_NAME", "your-app-name")  # koyeb app name
# ====================

if not BOT_TOKEN or not GEMINI_API_KEY:
    raise RuntimeError("Missing BOT_TOKEN or GEMINI_API_KEY environment variables!")

bot = telebot.TeleBot(BOT_TOKEN)
AUTH_FILE = "auth.json"

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

def ask_gemini(prompt, image_bytes=None):
    try:
        contents = [{"parts": [{"text": prompt}]}]
        if image_bytes:
            b64 = base64.b64encode(image_bytes).decode("utf-8")
            contents[0]["parts"].append({
                "inline_data": {"mime_type": "image/jpeg", "data": b64}
            })
        res = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
            json={"contents": contents},
            timeout=60
        )
        res.raise_for_status()
        data = res.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return text
    except Exception as e:
        return f"❌ Gemini Error: {e}"

# ====== Flask Setup ======
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ AI Bot is running!", 200

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
    bot.process_new_updates([update])
    return "ok", 200

# ===== Telegram Handlers =====
@bot.message_handler(commands=['start'])
def start(msg):
    if not is_allowed(msg.from_user.id, msg.chat.id):
        return bot.reply_to(msg, "🚫 Not authorized.")
    bot.reply_to(msg, "🤖 Hello! Send a question or image to solve.")

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

# ===== Run Bot (Webhook) =====
if __name__ == '__main__':
    # Remove old webhook first
    requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")

    # Set new webhook to Koyeb
    WEBHOOK_URL = f"https://{APP_NAME}.koyeb.app/{BOT_TOKEN}"
    set_hook = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={WEBHOOK_URL}")
    print("Webhook set response:", set_hook.text)

    app.run(host='0.0.0.0', port=PORT)
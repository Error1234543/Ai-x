
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
# ====================

if not BOT_TOKEN or not GEMINI_API_KEY:
    raise RuntimeError("Missing BOT_TOKEN or GEMINI_API_KEY environment variables!")

bot = telebot.TeleBot(BOT_TOKEN)
AUTH_FILE = "auth.json"

# ====== AUTH SETUP ======
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

# ====== GEMINI FUNCTION ======
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
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"❌ Gemini Error: {e}"

# ====== BOT HANDLERS ======
@bot.message_handler(commands=['start'])
def start(msg):
    if not is_allowed(msg.from_user.id, msg.chat.id):
        return bot.reply_to(msg, "🚫 Not authorized.")
    bot.reply_to(msg, "🤖 Hello! Send a question or image to solve.")

@bot.message_handler(commands=['addauth'])
def add_auth(msg):
    if not is_owner(msg.from_user.id):
        return bot.reply_to(msg, "🚫 Only owner can use this.")
    try:
        user_id = int(msg.text.split()[1])
        data = load_auth()
        if user_id not in data["allowed_users"]:
            data["allowed_users"].append(user_id)
            save_auth(data)
            bot.reply_to(msg, f"✅ Added user {user_id} to authorized list.")
        else:
            bot.reply_to(msg, "⚠️ User already authorized.")
    except:
        bot.reply_to(msg, "⚠️ Usage: /addauth <user_id>")

@bot.message_handler(commands=['removeauth'])
def remove_auth(msg):
    if not is_owner(msg.from_user.id):
        return bot.reply_to(msg, "🚫 Only owner can use this.")
    try:
        user_id = int(msg.text.split()[1])
        data = load_auth()
        if user_id in data["allowed_users"]:
            data["allowed_users"].remove(user_id)
            save_auth(data)
            bot.reply_to(msg, f"❌ Removed user {user_id}.")
        else:
            bot.reply_to(msg, "⚠️ User not found in list.")
    except:
        bot.reply_to(msg, "⚠️ Usage: /removeauth <user_id>")

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

# ====== FLASK APP + WEBHOOK ======
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ AI Bot is running!", 200

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.data.decode('utf-8'))
    bot.process_new_updates([update])
    return "OK", 200

if __name__ == '__main__':
    bot.remove_webhook()
    webhook_url = f"https://{os.getenv('KOYEB_APP_NAME')}.koyeb.app/{BOT_TOKEN}"
    bot.set_webhook(url=webhook_url)
    print(f"✅ Webhook set: {webhook_url}")
    app.run(host='0.0.0.0', port=PORT)
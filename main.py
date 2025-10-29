import os
import time
import json
import base64
import requests
import telebot
from flask import Flask
from threading import Thread

# ====== CONFIG (use environment variables on Koyeb) ======
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OWNER_ID = int(os.getenv("OWNER_ID", "7447651332"))  # default owner id
# =========================================================

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required.")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY environment variable is required.")

bot = telebot.TeleBot(BOT_TOKEN)

AUTH_FILE = "auth.json"

# --- Ensure auth.json exists ---
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
    return user_id in auth.get("owners", [])

def is_allowed(user_id, chat_id):
    auth = load_auth()
    if user_id in auth.get("allowed_users", []):
        return True
    if chat_id in auth.get("allowed_groups", []):
        return True
    if user_id in auth.get("owners", []):
        return True
    return False

# --- Gemini REST helper (Generative Language API v1beta) ---
def ask_gemini(prompt, image_bytes=None, timeout=60):
    try:
        contents = [{"parts": [{"text": prompt}]}]
        if image_bytes:
            b64 = base64.b64encode(image_bytes).decode("utf-8")
            contents[0]["parts"].append({
                "inline_data": {"mime_type": "image/jpeg", "data": b64}
            })
        payload = {"contents": contents}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        res = requests.post(url, json=payload, timeout=timeout)
        res.raise_for_status()
        data = res.json()
        candidates = data.get("candidates") or []
        if candidates:
            parts = candidates[0].get("content", {}).get("parts") or []
            if parts:
                return parts[0].get("text", "No text in response.")
        return json.dumps(data)[:2000]
    except Exception as e:
        return f"Error contacting Gemini API: {e}"

# --- Owner/Admin commands ---
@bot.message_handler(commands=['adduser'])
def cmd_adduser(msg):
    if not is_owner(msg.from_user.id):
        return bot.reply_to(msg, "❌ Only owner can add users.")
    try:
        uid = int(msg.text.split()[1])
        auth = load_auth()
        if uid in auth.get("allowed_users", []):
            return bot.reply_to(msg, "⚠️ User already allowed.")
        auth["allowed_users"].append(uid)
        save_auth(auth)
        bot.reply_to(msg, f"✅ Added allowed user {uid}")
    except Exception:
        bot.reply_to(msg, "Usage: /adduser <telegram_user_id>")

@bot.message_handler(commands=['removeuser'])
def cmd_removeuser(msg):
    if not is_owner(msg.from_user.id):
        return bot.reply_to(msg, "❌ Only owner can remove users.")
    try:
        uid = int(msg.text.split()[1])
        auth = load_auth()
        if uid not in auth.get("allowed_users", []):
            return bot.reply_to(msg, "⚠️ User not in allowed list.")
        auth["allowed_users"].remove(uid)
        save_auth(auth)
        bot.reply_to(msg, f"🗑️ Removed allowed user {uid}")
    except Exception:
        bot.reply_to(msg, "Usage: /removeuser <telegram_user_id>")

@bot.message_handler(commands=['addgroup'])
def cmd_addgroup(msg):
    if not is_owner(msg.from_user.id):
        return bot.reply_to(msg, "❌ Only owner can add groups.")
    try:
        gid = int(msg.text.split()[1])
        auth = load_auth()
        if gid in auth.get("allowed_groups", []):
            return bot.reply_to(msg, "⚠️ Group already allowed.")
        auth["allowed_groups"].append(gid)
        save_auth(auth)
        bot.reply_to(msg, f"✅ Added allowed group {gid}")
    except Exception:
        bot.reply_to(msg, "Usage: /addgroup <telegram_group_id>")

@bot.message_handler(commands=['removegroup'])
def cmd_removegroup(msg):
    if not is_owner(msg.from_user.id):
        return bot.reply_to(msg, "❌ Only owner can remove groups.")
    try:
        gid = int(msg.text.split()[1])
        auth = load_auth()
        if gid not in auth.get("allowed_groups", []):
            return bot.reply_to(msg, "⚠️ Group not in allowed list.")
        auth["allowed_groups"].remove(gid)
        save_auth(auth)
        bot.reply_to(msg, f"🗑️ Removed allowed group {gid}")
    except Exception:
        bot.reply_to(msg, "Usage: /removegroup <telegram_group_id>")

@bot.message_handler(commands=['authlist'])
def cmd_authlist(msg):
    if not is_owner(msg.from_user.id):
        return bot.reply_to(msg, "❌ Only owner can view the auth list.")
    auth = load_auth()
    text = "👑 Owners: " + ", ".join(map(str, auth.get("owners", []))) + "\n"
    text += "👤 Allowed users: " + ", ".join(map(str, auth.get("allowed_users", []))) + "\n"
    text += "💬 Allowed groups: " + ", ".join(map(str, auth.get("allowed_groups", [])))
    bot.reply_to(msg, text)

# --- Bot basic commands ---
@bot.message_handler(commands=['start'])
def cmd_start(msg):
    if not is_allowed(msg.from_user.id, msg.chat.id):
        return bot.reply_to(msg, "🚫 Access Denied. Ask the owner to add you.")
    bot.reply_to(msg, "🤖 Hello! I am your AI Doubt Solver (Gemini). Send text or image to get help.")

@bot.message_handler(content_types=['text'])
def handle_text(msg):
    if not is_allowed(msg.from_user.id, msg.chat.id):
        return bot.reply_to(msg, "🚫 Not authorized.")
    bot.send_chat_action(msg.chat.id, 'typing')
    answer = ask_gemini(msg.text)
    if len(answer) > 4000:
        answer = answer[:3990] + "\n... (truncated)"
    bot.reply_to(msg, answer)

@bot.message_handler(content_types=['photo'])
def handle_photo(msg):
    if not is_allowed(msg.from_user.id, msg.chat.id):
        return bot.reply_to(msg, "🚫 Not authorized.")
    bot.send_chat_action(msg.chat.id, 'typing')
    file_info = bot.get_file(msg.photo[-1].file_id)
    file_bytes = bot.download_file(file_info.file_path)
    answer = ask_gemini("Solve or explain this NEET/JEE question from the image step-by-step:", image_bytes=file_bytes)
    if len(answer) > 4000:
        answer = answer[:3990] + "\n... (truncated)"
    bot.reply_to(msg, answer)

# --- Simple HTTP server for Koyeb health check ---
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Bot running (health check OK)"

def run_flask():
    app.run(host="0.0.0.0", port=8000)

if __name__ == '__main__':
    try:
        bot.remove_webhook()
        requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook", timeout=5)
        time.sleep(1)
    except Exception:
        pass

    print("✅ Bot starting (polling mode)...")

    # Run flask + polling together
    Thread(target=run_flask).start()
    bot.infinity_polling(skip_pending=True)
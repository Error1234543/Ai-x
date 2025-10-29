import telebot
import requests
import os
import json

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

OWNER_ID = 7447651332  # 👈 yahan apna Telegram ID likha hai

bot = telebot.TeleBot(BOT_TOKEN)

AUTH_FILE = "auth_users.json"

# --- Load or create auth file ---
if not os.path.exists(AUTH_FILE):
    with open(AUTH_FILE, "w") as f:
        json.dump([OWNER_ID], f)

def get_auth_users():
    with open(AUTH_FILE, "r") as f:
        return json.load(f)

def save_auth_users(users):
    with open(AUTH_FILE, "w") as f:
        json.dump(users, f)

# --- Gemini AI function ---
def ask_gemini(prompt, image_url=None):
    try:
        headers = {"Content-Type": "application/json"}
        data = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }

        if image_url:
            data["contents"][0]["parts"].append({
                "inline_data": {"mime_type": "image/jpeg", "data": image_url}
            })

        res = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
            json=data,
            timeout=60
        )
        result = res.json()
        return result["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"⚠️ Error: {e}"

# --- Owner Commands ---
@bot.message_handler(commands=['addauth'])
def add_auth(msg):
    if msg.from_user.id != OWNER_ID:
        return bot.reply_to(msg, "❌ Only owner can add users.")
    try:
        new_id = int(msg.text.split()[1])
        users = get_auth_users()
        if new_id not in users:
            users.append(new_id)
            save_auth_users(users)
            bot.reply_to(msg, f"✅ Added user ID: {new_id}")
        else:
            bot.reply_to(msg, "⚠️ Already authorized.")
    except:
        bot.reply_to(msg, "⚠️ Usage: /addauth <user_id>")

@bot.message_handler(commands=['removeauth'])
def remove_auth(msg):
    if msg.from_user.id != OWNER_ID:
        return bot.reply_to(msg, "❌ Only owner can remove users.")
    try:
        rem_id = int(msg.text.split()[1])
        users = get_auth_users()
        if rem_id in users:
            users.remove(rem_id)
            save_auth_users(users)
            bot.reply_to(msg, f"🗑️ Removed user ID: {rem_id}")
        else:
            bot.reply_to(msg, "⚠️ User not found in auth list.")
    except:
        bot.reply_to(msg, "⚠️ Usage: /removeauth <user_id>")

@bot.message_handler(commands=['authlist'])
def list_auth(msg):
    if msg.from_user.id != OWNER_ID:
        return bot.reply_to(msg, "❌ Only owner can view auth list.")
    users = get_auth_users()
    bot.reply_to(msg, "👥 *Authorized Users:*\n" + "\n".join([f"`{u}`" for u in users]), parse_mode="Markdown")

# --- Access check ---
def is_authorized(user_id):
    return user_id in get_auth_users()

# --- Normal Bot Functions ---
@bot.message_handler(commands=['start'])
def start(msg):
    if not is_authorized(msg.from_user.id):
        return bot.reply_to(msg, "🚫 Access Denied. Ask the owner to add you.")
    bot.reply_to(msg, "👋 Hello! I'm your AI Study Bot.\nSend me any *question or image*, and I’ll solve your doubt using Gemini AI!")

@bot.message_handler(content_types=['text'])
def text_reply(msg):
    if not is_authorized(msg.from_user.id):
        return bot.reply_to(msg, "🚫 Not authorized.")
    bot.send_chat_action(msg.chat.id, 'typing')
    answer = ask_gemini(msg.text)
    bot.reply_to(msg, answer)

@bot.message_handler(content_types=['photo'])
def image_reply(msg):
    if not is_authorized(msg.from_user.id):
        return bot.reply_to(msg, "🚫 Not authorized.")
    bot.send_chat_action(msg.chat.id, 'typing')
    file_info = bot.get_file(msg.photo[-1].file_id)
    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
    answer = ask_gemini("Explain this image", image_url=file_url)
    bot.reply_to(msg, answer)

if __name__ == "__main__":
    try:
        requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")
    except:
        pass
    print("✅ Bot is running...")
    bot.infinity_polling()
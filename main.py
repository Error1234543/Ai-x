import os, json, telebot
from telebot import types
import google.generativeai as genai

# --- CONFIG ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
bot = telebot.TeleBot(BOT_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)

# --- Load auth.json ---
def load_auth():
    with open("auth.json", "r") as f:
        return json.load(f)

def save_auth(data):
    with open("auth.json", "w") as f:
        json.dump(data, f, indent=2)

auth = load_auth()

# --- Helpers ---
def is_owner(user_id):
    return user_id in auth["owners"]

def is_allowed(user_id, chat_id):
    return user_id in auth["allowed_users"] or chat_id in auth["allowed_groups"] or is_owner(user_id)

# --- START ---
@bot.message_handler(commands=['start'])
def start_cmd(msg):
    bot.reply_to(msg, "🤖 Hello! Send me your question or image to get an AI solution using Gemini.")

# --- AUTH COMMANDS (Owner only) ---
@bot.message_handler(commands=['add'])
def add_user(msg):
    if not is_owner(msg.from_user.id):
        return bot.reply_to(msg, "❌ You are not authorized.")
    try:
        user_id = int(msg.text.split()[1])
        auth["allowed_users"].append(user_id)
        save_auth(auth)
        bot.reply_to(msg, f"✅ Added user {user_id}")
    except:
        bot.reply_to(msg, "⚠️ Usage: /add <user_id>")

@bot.message_handler(commands=['remove'])
def remove_user(msg):
    if not is_owner(msg.from_user.id):
        return bot.reply_to(msg, "❌ You are not authorized.")
    try:
        user_id = int(msg.text.split()[1])
        auth["allowed_users"].remove(user_id)
        save_auth(auth)
        bot.reply_to(msg, f"🚫 Removed user {user_id}")
    except:
        bot.reply_to(msg, "⚠️ Usage: /remove <user_id>")

@bot.message_handler(commands=['authlist'])
def show_auth(msg):
    if not is_owner(msg.from_user.id):
        return bot.reply_to(msg, "❌ You are not authorized.")
    text = f"👑 Owners: {auth['owners']}\n👤 Users: {auth['allowed_users']}\n💬 Groups: {auth['allowed_groups']}"
    bot.reply_to(msg, text)

# --- TEXT HANDLER ---
@bot.message_handler(func=lambda msg: True, content_types=['text'])
def handle_text(msg):
    if not is_allowed(msg.from_user.id, msg.chat.id):
        return bot.reply_to(msg, "🚫 Not authorized to use this bot.")
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(msg.text)
    bot.reply_to(msg, response.text)

# --- IMAGE HANDLER ---
@bot.message_handler(content_types=['photo'])
def handle_image(msg):
    if not is_allowed(msg.from_user.id, msg.chat.id):
        return bot.reply_to(msg, "🚫 Not authorized to use this bot.")
    file_info = bot.get_file(msg.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    with open("temp.jpg", "wb") as f:
        f.write(downloaded_file)
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(["Explain this image in detail.", {"mime_type": "image/jpeg", "data": open("temp.jpg", "rb").read()}])
    bot.reply_to(msg, response.text)

# --- RUN ---
bot.infinity_polling()
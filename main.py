import telebot
import google.generativeai as genai
import os

# 🔹 Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")
OWNER_ID = int(os.getenv("OWNER_ID", "7447651332"))  # apna owner ID
GROUP_ID = int(os.getenv("GROUP_ID", "-1002432150473"))  # allowed group ID

bot = telebot.TeleBot(BOT_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# 🔹 Auth users list (owner + allowed)
AUTH_USERS = [OWNER_ID]

# ✅ Start Command
@bot.message_handler(commands=['start'])
def start_cmd(msg):
    bot.reply_to(msg, "👋 Hello! I’m your JEE/NEET AI Doubt Solver Bot.\nUse /ask for text questions or /image after sending a photo.")

# ✅ Auth command (owner only)
@bot.message_handler(commands=['auth'])
def auth_user(msg):
    if msg.from_user.id != OWNER_ID:
        return bot.reply_to(msg, "❌ Only owner can use this command.")
    try:
        parts = msg.text.split()
        if len(parts) < 2:
            return bot.reply_to(msg, "⚙️ Usage: /auth <telegram_id>")
        uid = int(parts[1])
        if uid not in AUTH_USERS:
            AUTH_USERS.append(uid)
            bot.reply_to(msg, f"✅ User {uid} authorized successfully.")
        else:
            bot.reply_to(msg, "⚠️ Already authorized.")
    except:
        bot.reply_to(msg, "⚠️ Invalid ID format.")

# ✅ /ask command
@bot.message_handler(commands=['ask'])
def ask_ai(msg):
    if msg.chat.id != GROUP_ID and msg.from_user.id not in AUTH_USERS:
        return bot.reply_to(msg, "❌ You are not authorized to use this bot.")
    question = msg.text.replace("/ask", "").strip()
    if not question:
        return bot.reply_to(msg, "💬 Please type your question like:\n/ask What is Newton’s second law?")
    bot.reply_to(msg, "🧠 Thinking... please wait a few seconds...")
    try:
        response = model.generate_content(question)
        bot.reply_to(msg, f"📘 **Answer:**\n{response.text}", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(msg, f"⚠️ Error: {e}")

# ✅ Handle images with /image command
@bot.message_handler(commands=['image'])
def image_ai(msg):
    if msg.chat.id != GROUP_ID and msg.from_user.id not in AUTH_USERS:
        return bot.reply_to(msg, "❌ You are not authorized to use this bot.")
    bot.reply_to(msg, "📸 Send an image of your question now.")

@bot.message_handler(content_types=['photo'])
def handle_photo(msg):
    if msg.chat.id != GROUP_ID and msg.from_user.id not in AUTH_USERS:
        return bot.reply_to(msg, "❌ You are not authorized to use this bot.")
    file_info = bot.get_file(msg.photo[-1].file_id)
    file = bot.download_file(file_info.file_path)
    with open("question.jpg", "wb") as f:
        f.write(file)

    bot.reply_to(msg, "🔍 Reading question... please wait...")
    try:
        response = model.generate_content(["Solve the NEET/JEE question from this image:", {"mime_type": "image/jpeg", "data": file}])
        bot.reply_to(msg, f"🧾 **Answer:**\n{response.text}", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(msg, f"⚠️ Error while solving: {e}")

# ✅ Run bot
print("🤖 Bot is running...")
bot.infinity_polling(skip_pending=True)
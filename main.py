import telebot
import google.generativeai as genai
from telebot import types

# ====== 🔐 CONFIGURATION ======
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
OWNER_ID = 7447651332              # your telegram id
GROUP_ID = -1002432150473          # your telegram group id
# ==============================

bot = telebot.TeleBot(BOT_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

AUTH_USERS = [OWNER_ID]  # only owner or authorized users can use bot


# ========= /start ==========
@bot.message_handler(commands=['start'])
def start_message(msg):
    bot.reply_to(msg, "👋 **Welcome to AI NEET/JEE Doubt Solver Bot!**\n\n"
                      "📘 Use `/ask` to ask theory or text question\n"
                      "🖼️ Send an image + type `/image` to solve image question",
                  parse_mode="Markdown")


# ========= /auth ==========
@bot.message_handler(commands=['auth'])
def authorize_user(msg):
    if msg.from_user.id != OWNER_ID:
        return bot.reply_to(msg, "❌ Only owner can authorize new users.")
    try:
        user_id = int(msg.text.split()[1])
        if user_id not in AUTH_USERS:
            AUTH_USERS.append(user_id)
            bot.reply_to(msg, f"✅ User {user_id} authorized successfully.")
        else:
            bot.reply_to(msg, f"⚠️ User {user_id} already authorized.")
    except Exception:
        bot.reply_to(msg, "⚠️ Usage: /auth <telegram_id>")


# ========= /ask ==========
@bot.message_handler(commands=['ask'])
def ask_question(msg):
    if msg.chat.id != GROUP_ID and msg.from_user.id not in AUTH_USERS:
        return bot.reply_to(msg, "❌ You are not authorized to use this bot.")

    question = msg.text.replace("/ask", "").strip()
    if not question:
        return bot.reply_to(msg, "✍️ Please type your question after /ask command.")
    bot.reply_to(msg, "🤖 Thinking... please wait...")

    try:
        response = model.generate_content(question)
        bot.reply_to(msg, f"🧠 **Answer:**\n{response.text}", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(msg, f"⚠️ Error while solving: {e}")


# ========= Image + /image command ==========
@bot.message_handler(commands=['image'])
def solve_last_image(msg):
    if msg.chat.id != GROUP_ID and msg.from_user.id not in AUTH_USERS:
        return bot.reply_to(msg, "❌ You are not authorized to use this bot.")

    bot.reply_to(msg, "📸 Please send the question image now...")


# ========= When image sent ==========
@bot.message_handler(content_types=['photo'])
def handle_photo(msg):
    if msg.chat.id != GROUP_ID and msg.from_user.id not in AUTH_USERS:
        return bot.reply_to(msg, "❌ You are not authorized to use this bot.")

    file_info = bot.get_file(msg.photo[-1].file_id)
    file_data = bot.download_file(file_info.file_path)

    bot.reply_to(msg, "🔍 Reading your image... please wait...")

    try:
        response = model.generate_content([
            "Solve this NEET/JEE question step by step:",
            {"mime_type": "image/jpeg", "data": file_data}
        ])
        bot.reply_to(msg, f"🧾 **Answer:**\n{response.text}", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(msg, f"⚠️ Error while solving: {e}")


# ========= Run bot ==========
if __name__ == "__main__":
    import requests
    # delete webhook (important for koyeb)
    try:
        requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")
    except:
        pass
    print("✅ Bot started successfully!")
    bot.infinity_polling(skip_pending=True)
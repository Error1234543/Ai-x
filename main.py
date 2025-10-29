import telebot
import google.generativeai as genai
import requests

# ====== CONFIG ======
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
OWNER_ID = 7447651332
GROUP_ID = -1002432150473
# ====================

bot = telebot.TeleBot(BOT_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

AUTH_USERS = [OWNER_ID]


@bot.message_handler(commands=['start'])
def start_message(msg):
    bot.reply_to(msg, "👋 *Welcome to AI JEE/NEET Doubt Solver!*\n\n"
                      "💬 `/ask` – Type your text question\n"
                      "🖼 `/image` – Send an image and get solution",
                      parse_mode="Markdown")


@bot.message_handler(commands=['auth'])
def authorize(msg):
    if msg.from_user.id != OWNER_ID:
        return bot.reply_to(msg, "❌ Only owner can authorize.")
    try:
        user_id = int(msg.text.split()[1])
        if user_id not in AUTH_USERS:
            AUTH_USERS.append(user_id)
            bot.reply_to(msg, f"✅ Authorized {user_id}")
        else:
            bot.reply_to(msg, f"⚠️ Already authorized.")
    except:
        bot.reply_to(msg, "Usage: /auth <user_id>")


@bot.message_handler(commands=['ask'])
def ask_question(msg):
    if msg.chat.id != GROUP_ID and msg.from_user.id not in AUTH_USERS:
        return bot.reply_to(msg, "❌ Not authorized.")

    question = msg.text.replace("/ask", "").strip()
    if not question:
        return bot.reply_to(msg, "✍️ Type your question after /ask")

    bot.reply_to(msg, "🤖 Thinking... please wait...")
    try:
        ans = model.generate_content(question)
        bot.reply_to(msg, f"🧠 *Answer:*\n{ans.text}", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(msg, f"⚠️ Error: {e}")


@bot.message_handler(commands=['image'])
def image_command(msg):
    if msg.chat.id != GROUP_ID and msg.from_user.id not in AUTH_USERS:
        return bot.reply_to(msg, "❌ Not authorized.")
    bot.reply_to(msg, "📸 Send the question image now...")


@bot.message_handler(content_types=['photo'])
def solve_image(msg):
    if msg.chat.id != GROUP_ID and msg.from_user.id not in AUTH_USERS:
        return bot.reply_to(msg, "❌ Not authorized.")
    file_info = bot.get_file(msg.photo[-1].file_id)
    file = bot.download_file(file_info.file_path)
    bot.reply_to(msg, "🔍 Reading your image... please wait...")
    try:
        response = model.generate_content([
            "Solve this NEET/JEE question step-by-step:",
            {"mime_type": "image/jpeg", "data": file}
        ])
        bot.reply_to(msg, f"🧾 *Answer:*\n{response.text}", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(msg, f"⚠️ Error: {e}")


if __name__ == "__main__":
    try:
        requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")
    except:
        pass
    print("✅ Bot started successfully!")
    bot.infinity_polling(skip_pending=True)
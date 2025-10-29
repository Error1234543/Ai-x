# bot.py
import os
import io
import logging
import time
from typing import Optional

import telebot  # pyTelegramBotAPI
from telebot import types

# OCR
from PIL import Image
import pytesseract

# Gemini client (Google genai). If not installed, we fall back to a simple HTTP stub that raises helpful error.
try:
    from google import genai
    HAS_GENAI = True
except Exception:
    HAS_GENAI = False

# ---- Configuration from environment variables ----
BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Telegram bot token
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))  # Owner Telegram numeric ID
ALLOWED_USERS = os.environ.get("ALLOWED_USERS", "")  # comma separated numeric ids, e.g. "12345,67890"
ALLOWED_USERS_SET = set(int(x.strip()) for x in ALLOWED_USERS.split(",") if x.strip())
GROUP_ID = int(os.environ.get("GROUP_ID", "0"))  # restrict bot to this group/chat id

# Telebot init
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required.")
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# In-memory store for last image file_id per user (persist only while container runs).
LAST_IMAGE = {}  # user_id -> file_info dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---- Gemini helper ----
def init_genai_client():
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set in env.")
    if not HAS_GENAI:
        raise RuntimeError(
            "Google genai client not installed. Install with 'pip install google-genai' "
            "or use the Docker image provided in README."
        )
    client = genai.Client(api_key=GEMINI_API_KEY)
    return client

def call_gemini_text(prompt: str, model: str = "gemini-2.5-flash") -> str:
    """
    Calls Gemini API (using google genai client) to generate an answer.
    If the official client isn't available, raises a helpful error.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set.")
    if not HAS_GENAI:
        raise RuntimeError(
            "Gemini Python client not installed. See README. (pip install google-genai)"
        )

    client = init_genai_client()
    # Using generate_content (per Google docs). The exact API may change with versions.
    try:
        response = client.generate_content(model=model, content=prompt)
        # response.text or response.output may vary by client version. Try common fields:
        text = getattr(response, "text", None) or getattr(response, "output", None) or str(response)
        return text
    except Exception as e:
        logger.exception("Gemini call failed")
        raise

# ---- Helpers for permission checks ----
def is_allowed(user_id: int) -> bool:
    if user_id == OWNER_ID:
        return True
    if user_id in ALLOWED_USERS_SET:
        return True
    return False

def is_in_allowed_group(chat_id: int) -> bool:
    # If GROUP_ID=0 means not set, allow anywhere.
    if GROUP_ID == 0:
        return True
    return chat_id == GROUP_ID

# ---- Commands ----
@bot.message_handler(commands=["start", "help"])
def handle_start(message):
    bot.reply_to(message, (
        "AI Doubt Bot (JEE/NEET)\n\n"
        "Usage:\n"
        "/ask <question>  — Ask a text question.\n"
        "Send an image (photo) containing a problem, then send /image to OCR+solve it.\n\n"
        "Only owner or authorized users can use this bot. The bot will operate only in configured group (if set)."
    ))

@bot.message_handler(commands=["ask"])
def handle_ask(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if not is_in_allowed_group(chat_id):
        bot.reply_to(message, "This bot is restricted to another group/chat.")
        return
    if not is_allowed(user_id):
        bot.reply_to(message, "You are not authorized to use this bot.")
        return

    # Get prompt text (after command)
    args = message.text.partition(" ")[2].strip()
    if not args:
        bot.reply_to(message, "Use: /ask <your question here>")
        return

    sent = bot.reply_to(message, "Processing your question with Gemini... ⏳")
    try:
        answer = call_gemini_text(args)
        bot.edit_message_text(chat_id=sent.chat.id, message_id=sent.message_id, text=f"Q: {args}\n\nA: {answer}")
    except Exception as e:
        bot.edit_message_text(chat_id=sent.chat.id, message_id=sent.message_id, text=f"Error while calling Gemini: {e}")

@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    """
    When user sends a photo, we save its file_id and respond with instructions.
    """
    user_id = message.from_user.id
    chat_id = message.chat.id

    if not is_in_allowed_group(chat_id):
        bot.reply_to(message, "This bot is restricted to another group/chat.")
        return
    if not is_allowed(user_id):
        bot.reply_to(message, "You are not authorized to use this bot.")
        return

    # take highest resolution photo (last in array)
    file_info = bot.get_file(message.photo[-1].file_id)
    LAST_IMAGE[user_id] = {
        "file_id": message.photo[-1].file_id,
        "file_path": file_info.file_path,
        "timestamp": time.time()
    }
    bot.reply_to(message, "Image received ✅\nNow send /image to OCR + solve that image's question.")

@bot.message_handler(commands=["image"])
def handle_image_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if not is_in_allowed_group(chat_id):
        bot.reply_to(message, "This bot is restricted to another group/chat.")
        return
    if not is_allowed(user_id):
        bot.reply_to(message, "You are not authorized to use this bot.")
        return

    info = LAST_IMAGE.get(user_id)
    if not info:
        bot.reply_to(message, "No image found for you. First send the image (photo), then send /image.")
        return

    sent = bot.reply_to(message, "Downloading image and extracting text (OCR)... ⏳")
    try:
        file_id = info["file_id"]
        file_info = bot.get_file(file_id)
        downloaded = bot.download_file(file_info.file_path)
        image = Image.open(io.BytesIO(downloaded))
        # Basic OCR
        ocr_text = pytesseract.image_to_string(image, lang="eng")  # lang can be adjusted
        if not ocr_text.strip():
            bot.edit_message_text(chat_id=sent.chat.id, message_id=sent.message_id, text="Could not extract text from image. Try a clearer photo or type the question.")
            return

        bot.edit_message_text(chat_id=sent.chat.id, message_id=sent.message_id, text="Text extracted. Sending to Gemini for solution... ⏳")
        # Build prompt to ask model to solve or explain step-by-step
        prompt = (
            "You are an expert JEE/NEET tutor. Solve the following problem step-by-step and give final answer. "
            "If multiple interpretations possible, list them.\n\n"
            f"Problem (from image OCR):\n{ocr_text}\n\nAnswer:"
        )
        answer = call_gemini_text(prompt)
        bot.send_message(chat_id, f"<b>OCR Text:</b>\n<pre>{ocr_text[:700]}</pre>\n\n<b>Solution:</b>\n{answer}")
    except Exception as e:
        logger.exception("Error handling /image")
        bot.edit_message_text(chat_id=sent.chat.id, message_id=sent.message_id, text=f"Error processing image: {e}")

# Admin command to add allowed user (owner-only)
@bot.message_handler(commands=["allow"])
def handle_allow(message):
    user_id = message.from_user.id
    if user_id != OWNER_ID:
        bot.reply_to(message, "Only owner can run this command.")
        return
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /allow <telegram_numeric_id>")
        return
    try:
        new_id = int(parts[1])
        ALLOWED_USERS_SET.add(new_id)
        bot.reply_to(message, f"Added {new_id} to allowed users (in-memory). To persist, add to ALLOWED_USERS env var.")
    except:
        bot.reply_to(message, "Invalid id.")

# Clean-up endpoint / ping
@bot.message_handler(commands=["ping"])
def handle_ping(message):
    bot.reply_to(message, "Pong ✅")

# Start polling (or use webhook as you prefer)
def main():
    logger.info("Bot started. Listening for messages...")
    bot.infinity_polling(timeout=60, long_polling_timeout=60)

if __name__ == "__main__":
    main()

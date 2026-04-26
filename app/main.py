import os
import telebot
from dotenv import load_dotenv
from .handlers.start import start_handler
from .handlers.notes import notes_handler
from .handlers.files import files_handler
from .handlers.groups import groups_handler
from .handlers.activate import activation_handler
from .handlers.admin import admin_handler

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Initialize bot with timeout and request kwargs
bot = telebot.TeleBot(
    TOKEN,
    parse_mode="Markdown",
    threaded=False
)

# Request timeout configuration
telebot.apihelper.SESSION_TIMEOUT = 30
telebot.apihelper.API_REQUEST_TIMEOUT = 30

# Register handlers
start_handler(bot)
activation_handler(bot)
notes_handler(bot)
groups_handler(bot)
files_handler(bot)
admin_handler(bot)

# -------------------------
# GLOBAL CATCH-ALL HANDLER
# -------------------------
@bot.message_handler(func=lambda m: m.chat.type == 'private')
def catch_all_unverified(message):
    """
    Final safety net for any messages that didn't match previous handlers.
    Replies with an 'Unverified input' message.
    """
    bot.reply_to(
        message,
        " ⚠️ *Unverified Input*\n\n"
        "I didn't recognize that message. Please use the menu buttons or commands like /start or /hub to interact with me.\n\n"
        "If you are trying to register, make sure you follow the **Name | Program | ...** format exactly.",
        parse_mode="Markdown"
    )

# Bot polling is handled by webhook.py when deployed
# For local testing, uncomment the line below:
# bot.infinity_polling(timeout=30, long_polling_timeout=30)
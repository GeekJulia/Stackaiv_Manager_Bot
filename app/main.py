import os
import telebot
from telebot import types
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

# Inline keyboard
def main_menu():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("/start", callback_data="start"))
    keyboard.add(types.InlineKeyboardButton("/help", callback_data="help"))
    keyboard.add(types.InlineKeyboardButton("/info", callback_data="info"))
    return keyboard

# Commands
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Hello! I'm your bot 🤖")

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(message, "Send me commands and I will respond!")

@bot.message_handler(commands=['menu'])
def show_menu(message):
    bot.send_message(
        message.chat.id,
        "Choose a command from the menu:",
        reply_markup=main_menu()
    )

# Handle button clicks
@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    if call.data == "start":
        bot.send_message(call.message.chat.id, "You pressed /start!")
    elif call.data == "help":
        bot.send_message(call.message.chat.id, "You pressed /help!")
    elif call.data == "info":
        bot.send_message(call.message.chat.id, "You pressed /info!")
    # Optional: remove keyboard after click
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

# Echo any other text
@bot.message_handler(func=lambda m: True)
def echo_all(message):
    bot.reply_to(message, f"You said: {message.text}")

print("Bot is running...")
bot.infinity_polling()

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.services.programs import create_or_get_program, check_activation

def start_handler(bot):

    @bot.message_handler(commands=['start'])
    def start(message):
        kb = InlineKeyboardMarkup()
        for lvl in ['100 Level', '200 Level', '300 Level', '400 Level', '500 Level']:
            kb.add(InlineKeyboardButton(lvl, callback_data=f"level:{lvl}"))

        bot.send_message(
            message.chat.id,
            "👋 Welcome to StackAIV\nSelect your level:",
            reply_markup=kb
        )
        return kb
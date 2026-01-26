from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
# from app.services.programs import create_or_get_program, check_activation

COLLEGES = {
    "CST": ["Computer Science", "Information Tech"],
    "COE": ["Civil Engineering", "Electrical Engineering"],
    "CLDS": ["Law", "International Law"],
    "CMSS": ["Economics", "Sociology"]
}

# -------------------------
# Start Handler
# -------------------------

def start_handler(bot):

    @bot.message_handler(commands=['start'])
    def start(message):
        kb = InlineKeyboardMarkup()
        levels = ['100 Level', '200 Level', '300 Level', '400 Level', '500 Level']
        for lvl in levels:
            kb.add(InlineKeyboardButton(lvl, callback_data=f"level:{lvl}"))

        bot.send_message(
            message.chat.id,
            "👋 Welcome to Stackaiv\n\nSelect your level:",
            reply_markup=kb
        )

# -------------------------
# Level Selected → Ask for College
# -------------------------

    @bot.callback_query_handler(func=lambda call: call.data.startswith("level:"))
    def handle_level(call):
        level = call.data.split(":")[1]

        kb = InlineKeyboardMarkup()
        for college in COLLEGES.keys():
            kb.add(
                InlineKeyboardButton(
                    college,
                    callback_data=f"college:{college}",
                )
            )

        bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"✅ Level selected: *{level}*\n\nNow select your college:",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    # -------------------------
    # College Selected → Ask for Program
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data.startswith("college:"))
    def handle_college(call):
        college = call.data.split(":")[1]

        kb = InlineKeyboardMarkup()
        programs = COLLEGES.get(college, [])

        for program in programs:
            kb.add(
                InlineKeyboardButton(
                    program,
                    callback_data=f"program:{program}"
                )
            )

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"🏫 College selected: *{college}*\n\nSelect your program:",
            reply_markup=kb,
            parse_mode="Markdown"
        )
    # -------------------------
    # Program Selected → Finish
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data.startswith("program:"))
    def handle_program(call):
        program = call.data.split(":")[1]

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=(
                "🎉 *Registration Complete!*\n\n"
                f"📘 Program: *{program}*\n\n"
                "You can now continue using the bot."
            ),
            parse_mode="Markdown"
        )
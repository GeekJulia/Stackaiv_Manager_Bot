from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from ..database.queries import save_user, save_program

user_sessions = {}

COLLEGES = {
    "CST": [
        "COMPUTER SCIENCE", "BIOCHEMISTRY", "ARCHITECTURE", "BIOLOGY",
        "BUILDING TECHNOLOGY", "BUSINESS ADMINISTRATION", "ESTATE MANAGEMENT",
        "INDUSTRIAL CHEMISTRY", "INDUSTRIAL MATHEMATICS",
        "INDUSTRIAL PHYSICS WITH APPLIED GEOPHYSICS",
        "INDUSTRIAL PHYSICS WITH ELECTRONICS AND IT APPLICATION",
        "INDUSTRIAL PHYSICS WITH RENEWABLE ENERGY",
        "MANAGEMENT INFORMATION SYSTEM", "MICROBIOLOGY"
    ],
    "COE": [
        "CIVIL ENGINEERING", "ELECTRICAL/ELECTRONICS ENGINEERING",
        "CHEMICAL ENGINEERING", "COMPUTER ENGINEERING",
        "INFORMATION AND COMMUNICATION ENGINEERING",
        "MECHANICAL ENGINEERING", "PETROLEUM ENGINEERING"
    ],
    "CLDS": [
        "DEMOGRAPHY AND SOCIAL STATISTICS", "ENGLISH LANGUAGE", "FRENCH",
        "INTERNATIONAL RELATIONS", "POLICY AND STRATEGIC STUDIES",
        "POLITICAL SCIENCE", "PSYCHOLOGY"
    ],
    "CMSS": [
        "ECONOMICS", "SOCIOLOGY", "ACCOUNTING", "BANKING AND FINANCE",
        "INDUSTRIAL RELATIONS",
        "INDUSTRIAL RELATIONS AND HUMAN RESOURCES MANAGEMENT",
        "MARKETING", "MASS COMMUNICATION"
    ]
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
            reply_markup=kb,
            parse_mode="Markdown"
        )

# -------------------------
# Level Selected → Ask for College
# -------------------------

    @bot.callback_query_handler(func=lambda call: call.data.startswith("level:"))
    def handle_level(call):
        level = call.data.split(":")[1]

        user_sessions[call.from_user.id] = {"level": level}

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

        user_sessions[call.from_user.id]["college"] = college

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
        user = call.from_user
        session = user_sessions.get(user.id)

        # Save Telegram user
        save_user(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name
        )

         # Save program
        save_program(
            level=session["level"],
            college=session["college"],
            program_name=program,
            telegram_id=user.id
        )

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
        user_sessions.pop(user.id, None)
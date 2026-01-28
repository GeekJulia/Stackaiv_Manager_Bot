from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from ..database.queries import save_user, save_program, get_user_program_id

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
        user_sessions[message.from_user.id] = {}

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
    # Who Am I Command
    # -------------------------
    @bot.message_handler(commands=['whoami'])
    def whoami(message):
        user_id = message.from_user.id
        try:
            program_id = get_user_program_id(user_id)
            bot.send_message(
                message.chat.id,
                f"ℹ️ <b>Your Info</b>\n\n"
                f"👤 Username: @{message.from_user.username or 'N/A'}\n"
                f"📱 Telegram ID: <code>{user_id}</code>\n"
                f"🎓 Program ID: <code>{program_id}</code>\n\n"
                f"Use this Program ID with /setupgroup",
                parse_mode="HTML"
            )
        except Exception as e:
            bot.send_message(
                message.chat.id,
                "❌ Not registered yet.\n\nRun /start to complete registration.",
                parse_mode="HTML"
            )

# -------------------------
# Level Selected → Ask for College
# -------------------------

    @bot.callback_query_handler(func=lambda call: call.data.startswith("level:"))
    def handle_level(call):
        user_id = call.from_user.id
        level = call.data.split(":")[1]

        # Prevent double selection
        if user_sessions.get(user_id, {}).get("level"):
            bot.answer_callback_query(call.id, "Level already selected.")
            return
        
        user_sessions[call.from_user.id] = {"level": level}

        kb = InlineKeyboardMarkup()
        for college in COLLEGES.keys():
            kb.add(
                InlineKeyboardButton(
                    college,
                    callback_data=f"college:{college}",
                )
            )
        kb.add(InlineKeyboardButton("⬅️ Back", callback_data="back:level"))

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
        user_id = call.from_user.id
        college = call.data.split(":")[1]


        if user_sessions.get(user_id, {}).get("college"):
            bot.answer_callback_query(call.id, "College already selected.")
            return

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
        kb.add(InlineKeyboardButton("⬅️ Back", callback_data="back:college"))

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
        user_id = call.from_user.id
        program = call.data.split(":")[1]
        user = call.from_user

        if user_sessions.get(user_id, {}).get("program"):
            bot.answer_callback_query(call.id, "Program already selected.")
            return

        user_sessions[user_id]["program"] = program
        session = user_sessions.get(user.id)

        # Save Telegram user
        user_id = save_user(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name
        )

         # Save program
        save_program(
            level=session["level"],
            college=session["college"],
            program_name=program,
            user_id=user_id
        )

        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton(
                "Add courses",
                callback_data="cmd:addcourses"
            )
        )

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=(
                "🎉 *Registration Complete!*\n\n"
                f"📘 Program: *{program}*\n\n"
                "Set up your academic space."
            ),
            parse_mode="Markdown",
            reply_markup=kb
        )

        user_sessions.pop(user_id, None)

    # -------------------------
    # Back Navigation/UNCHECKED
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data.startswith("back:"))
    def handle_back(call):
        user_id = call.from_user.id
        step = call.data.split(":")[1]

        # Back to level selection
        if step == "level":
            user_sessions[user_id] = {}

            kb = InlineKeyboardMarkup()
            levels = ['100 Level', '200 Level', '300 Level', '400 Level', '500 Level']
            for lvl in levels:
                kb.add(InlineKeyboardButton(lvl, callback_data=f"level:{lvl}"))

            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="🔄 Select your level:",
                reply_markup=kb
            )

        # Back to college selection
        elif step == "college":
            user_sessions[user_id].pop("college", None)

            kb = InlineKeyboardMarkup()
            for college in COLLEGES.keys():
                kb.add(InlineKeyboardButton(college, callback_data=f"college:{college}"))

            kb.add(InlineKeyboardButton("⬅️ Back", callback_data="back:level"))

            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"🔄 Level: *{user_sessions[user_id]['level']}*\n\nSelect your college:",
                reply_markup=kb,
                parse_mode="Markdown"
            )
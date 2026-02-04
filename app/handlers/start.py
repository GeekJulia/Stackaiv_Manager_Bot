from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from ..database.queries import (
    save_user, 
    save_program, 
    get_user_program_id, 
    get_program_info,
    check_program_exists,
    get_program_creator,
    clear_user_program_data,
    count_active_programs,
    activate_program,
    user_has_program,
    get_user_program_info
)

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
        kb.add(InlineKeyboardButton("🏠 Go to Program Space", callback_data="action:goto_space"))
        kb.add(InlineKeyboardButton("➕ Onboard a New Program", callback_data="action:new_program"))
        
        bot.send_message(
            message.chat.id,
            "👋 Welcome to Stackaiv!\n\nWhat would you like to do?",
            reply_markup=kb,
            parse_mode="Markdown"
        )

    # -------------------------
    # Action: Go to Program Space
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "action:goto_space")
    def goto_program_space(call):
        bot.send_message(
            call.message.chat.id,
            "🔑 Please enter your Program ID:",
            parse_mode="Markdown"
        )
        
        user_sessions[call.from_user.id] = {
            "stage": "awaiting_program_id"
        }

    # -------------------------
    # Receive Program ID
    # -------------------------
    @bot.message_handler(func=lambda m: user_sessions.get(m.from_user.id, {}).get("stage") == "awaiting_program_id")
    def verify_program_id(message):
        user_id = message.from_user.id
        program_id_input = message.text.strip()
        
        try:
            program_id = int(program_id_input)
            
            # Verify program exists in database
            program = get_program_info(program_id)
            
            if program:
                # Valid program ID - show hub
                kb = InlineKeyboardMarkup(row_width=2)
                kb.add(
                    InlineKeyboardButton("📚 All Courses", callback_data="hub:courses"),
                    InlineKeyboardButton("➕ Add Resource", callback_data="hub:add"),
                    InlineKeyboardButton("📥 Get Resource", callback_data="hub:get"),
                    InlineKeyboardButton("ℹ️ Help Info", callback_data="hub:help"),
                )
                kb.add(InlineKeyboardButton("🔄 Re-register", callback_data="hub:reregister"))
                
                bot.send_message(
                    message.chat.id,
                    (
                        f"🎉 *Welcome back!*\n\n"
                        f"👋 You're now in your *{program['program_name']} {program['level']}* "
                        f"digital central resource hub.\n\n"
                        f"What would you like to do?"
                    ),
                    parse_mode="Markdown",
                    reply_markup=kb
                )
                
                # Clear session
                user_sessions.pop(user_id, None)
            else:
                bot.send_message(
                    message.chat.id,
                    "❌ Invalid Program ID. Please try again with /start or check the ID.",
                    parse_mode="Markdown"
                )
                user_sessions.pop(user_id, None)
                
        except ValueError:
            bot.send_message(
                message.chat.id,
                "❌ Invalid Program ID format. Please enter a valid number or use /start to register.",
                parse_mode="Markdown"
            )
            user_sessions.pop(user_id, None)
        except Exception as e:
            print(f"ERROR in verify_program_id: {e}")
            bot.send_message(
                message.chat.id,
                "❌ An error occurred. Please use /start to try again.",
                parse_mode="Markdown"
            )
            user_sessions.pop(user_id, None)

    # -------------------------
    # Re-register Handler
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "hub:reregister")
    def handle_reregister(call):
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("✅ Yes, Clear Everything", callback_data="reregister:confirm"))
        kb.add(InlineKeyboardButton("❌ Cancel", callback_data="reregister:cancel"))
        
        bot.send_message(
            call.message.chat.id,
            (
                "⚠️ *Warning: Re-registration*\n\n"
                "This will **delete all your courses and resource types**.\n"
                "You'll need to start over from scratch.\n\n"
                "Are you sure you want to continue?"
            ),
            parse_mode="Markdown",
            reply_markup=kb
        )

    @bot.callback_query_handler(func=lambda call: call.data == "reregister:confirm")
    def confirm_reregister(call):
        user_id = call.from_user.id
        
        try:
            program_id = get_user_program_id(user_id)
            clear_user_program_data(program_id)
            
            kb = InlineKeyboardMarkup()
            kb.add(
                InlineKeyboardButton(
                    "➕ Add Courses",
                    callback_data="notes:add_courses"
                )
            )
            kb.add(
                InlineKeyboardButton(
                    "🏠 Back to Space",
                    callback_data="action:goto_space"
                )
            )
            
            bot.send_message(
                call.message.chat.id,
                (
                    "✅ *Data cleared successfully!*\n\n"
                    "All courses and resource types have been removed.\n"
                    "You can now add your courses again."
                ),
                parse_mode="Markdown",
                reply_markup=kb
            )
        except Exception as e:
            bot.send_message(
                call.message.chat.id,
                "❌ An error occurred. Please try again or contact support.",
                parse_mode="Markdown"
            )

    @bot.callback_query_handler(func=lambda call: call.data == "reregister:cancel")
    def cancel_reregister(call):
        bot.send_message(
            call.message.chat.id,
            "❌ Re-registration cancelled. Your data remains intact.",
            parse_mode="Markdown"
        )

    # -------------------------
    # Action: Onboard New Program
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "action:new_program")
    def onboard_new_program(call):
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        
        # ✅ Check if user already has a program
        if user_has_program(user_id):
            existing_program = get_user_program_info(user_id)
            
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("🏠 Go to Program Space", callback_data="action:goto_space"))
            kb.add(InlineKeyboardButton("🔄 Re-register", callback_data="hub:reregister"))
            
            bot.send_message(
                chat_id,
                (
                    "⚠️ *You Already Have a Registered Program*\n\n"
                    f"📘 Program: *{existing_program['program_name']}*\n"
                    f"🏫 College: *{existing_program['college']}*\n"
                    f"📊 Level: *{existing_program['level']}*\n"
                    f"🆔 Program ID: `{existing_program['id']}`\n\n"
                    "You can only register one program per account.\n\n"
                    "If you need to access a different program, please use the Program ID "
                    "to go to that program's space, or contact support if you need to change your program."
                ),
                parse_mode="Markdown",
                reply_markup=kb
            )
            return
        
        # Initialize new user session
        user_sessions[user_id] = {}

        kb = InlineKeyboardMarkup()
        levels = ['100 Level', '200 Level', '300 Level', '400 Level', '500 Level']
        for lvl in levels:
            kb.add(InlineKeyboardButton(lvl, callback_data=f"level:{lvl}"))

        bot.send_message(
            chat_id,
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
        program_id = get_user_program_id(user_id)
        
        if program_id:
            program_info = get_program_info(program_id)
            bot.send_message(
                message.chat.id,
                f"ℹ️ <b>Your Info</b>\n\n"
                f"👤 Username: @{message.from_user.username or 'N/A'}\n"
                f"📱 Telegram ID: <code>{user_id}</code>\n\n"
                f"📘 Program: <b>{program_info['program_name']}</b>\n"
                f"🏫 College: {program_info['college']}\n"
                f"📊 Level: {program_info['level']}\n"
                f"🆔 Program ID: <code>{program_id}</code>\n\n"
                f"Use this Program ID with /setupgroup in your group chat",
                parse_mode="HTML"
            )
        else:
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

        # ✅ Check if user already has a program (safety check)
        if user_has_program(user_id):
            existing_program = get_user_program_info(user_id)
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("🏠 Go to Program Space", callback_data="action:goto_space"))
            
            bot.answer_callback_query(
                call.id,
                "You already have a registered program!",
                show_alert=True
            )
            bot.send_message(
                call.message.chat.id,
                (
                    "⚠️ *You Already Have a Registered Program*\n\n"
                    f"📘 Program: *{existing_program['program_name']}*\n"
                    f"🆔 Program ID: `{existing_program['id']}`\n\n"
                    "Please go to your program space instead."
                ),
                parse_mode="Markdown",
                reply_markup=kb
            )
            return

        # ✅ Check if session exists
        if user_id not in user_sessions:
            bot.answer_callback_query(call.id, "❌ Session expired. Use /start", show_alert=True)
            return

        # Prevent double selection
        if user_sessions.get(user_id, {}).get("level"):
            bot.answer_callback_query(call.id, "Level already selected.")
            return
        
        user_sessions[user_id]["level"] = level

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

        # ✅ Check if session exists
        if user_id not in user_sessions:
            bot.answer_callback_query(call.id, "❌ Session expired. Use /start", show_alert=True)
            return

        # ✅ Check if level was selected
        if "level" not in user_sessions.get(user_id, {}):
            bot.answer_callback_query(call.id, "❌ Session corrupted. Use /start", show_alert=True)
            user_sessions.pop(user_id, None)
            return

        if user_sessions.get(user_id, {}).get("college"):
            bot.answer_callback_query(call.id, "College already selected.")
            return

        user_sessions[user_id]["college"] = college

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
    # Program Selected → Check Duplicates
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data.startswith("program:"))
    def handle_program(call):
        user_id = call.from_user.id
        program = call.data.split(":")[1]
        user = call.from_user

        # ✅ Check if session exists
        if user_id not in user_sessions:
            bot.answer_callback_query(
                call.id, 
                "❌ Session expired. Please start over.",
                show_alert=True
            )
            bot.send_message(
                call.message.chat.id,
                "Your session has expired. Please use /start to begin again.",
                parse_mode="Markdown"
            )
            return
        
        # ✅ Check if the session has the required data
        session = user_sessions.get(user_id, {})
        if "level" not in session or "college" not in session:
            bot.answer_callback_query(
                call.id,
                "❌ Session corrupted. Please start over.",
                show_alert=True
            )
            user_sessions.pop(user_id, None)
            bot.send_message(
                call.message.chat.id,
                "Your session was corrupted. Please use /start to begin again.",
                parse_mode="Markdown"
            )
            return

        # if session.get("program"):
        #     bot.answer_callback_query(call.id, "Program already selected.")
        #     return

        user_sessions[user_id]["program"] = program
        session = user_sessions.get(user_id)

        # ✅ Final safety check - ensure user doesn't already have a program
        if user_has_program(user_id):
            existing_program = get_user_program_info(user_id)
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("🏠 Go to Program Space", callback_data="action:goto_space"))
            
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=(
                    "⚠️ *You Already Have a Registered Program*\n\n"
                    f"📘 Program: *{existing_program['program_name']}*\n"
                    f"🏫 College: *{existing_program['college']}*\n"
                    f"📊 Level: *{existing_program['level']}*\n"
                    f"🆔 Program ID: `{existing_program['id']}`\n\n"
                    "You can only register one program per account.\n\n"
                    "Please go to your program space instead."
                ),
                parse_mode="Markdown",
                reply_markup=kb
            )
            user_sessions.pop(user_id, None)
            return

        # Check if program already exists (created by someone else)
        existing_program = check_program_exists(
            level=session["level"],
            college=session["college"],
            program_name=program
        )

        if existing_program:
            # Program exists - check if it's created by this user or someone else
            creator = get_program_creator(existing_program['id'])
            current_user_id = save_user(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name
            )
            
            # If program was created by this user, show their program info
            if existing_program['user_id'] == current_user_id:
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton("🏠 Go to Program Space", callback_data="action:goto_space"))
                kb.add(InlineKeyboardButton("🔄 Re-register", callback_data="hub:reregister"))
                
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=(
                        "ℹ️ *This is Your Program*\n\n"
                        f"📘 Program: *{program}*\n"
                        f"🏫 College: *{session['college']}*\n"
                        f"📊 Level: *{session['level']}*\n"
                        f"🆔 Program ID: `{existing_program['id']}`\n\n"
                        "This program is already registered to your account.\n"
                        "You can go to your program space or re-register if needed."
                    ),
                    parse_mode="Markdown",
                    reply_markup=kb
                )
            else:
                # Program exists but was created by someone else
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton("🏠 Go to Program Space", callback_data="action:goto_space"))
                kb.add(InlineKeyboardButton("🔙 Back to Start", callback_data="action:back_to_start"))
                
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=(
                        "ℹ️ *Program Already Registered*\n\n"
                        f"📘 Program: *{program}*\n"
                        f"🏫 College: *{session['college']}*\n"
                        f"📊 Level: *{session['level']}*\n\n"
                        "This program has already been registered by someone else.\n\n"
                        "💡 *What to do:*\n"
                        "Ask your course representative or classmate for the **Program ID**.\n"
                        "Then use that Program ID to access the program space.\n\n"
                        f"👤 Program created by: @{creator['username'] or 'N/A'}"
                    ),
                    parse_mode="Markdown",
                    reply_markup=kb
                )
            
            user_sessions.pop(user_id, None)
            return

        # Save Telegram user
        saved_user_id = save_user(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name
        )

        # Save program
        program_id = save_program(
            level=session["level"],
            college=session["college"],
            program_name=program,
            user_id=saved_user_id
        )

        # Check if this is one of the first 3 programs - if so, auto-activate for free
        active_count = count_active_programs()
        
        if active_count < 3:
            # Auto-activate this program for free
            activate_program(program_id, is_paid=False)
            
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("➕ Add Courses", callback_data="notes:add_courses"))
            kb.add(InlineKeyboardButton("🏠 Back to Hub", callback_data="action:goto_space"))
            
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=(
                    "🎉 *Registration Complete!*\n\n"
                    f"📘 Program: *{program}*\n\n"
                    "✅ *Your program has been automatically activated!*\n"
                    "(You're one of the first 3 programs - enjoying free activation)\n\n"
                    "You can now add your courses and start sharing resources in your group chat."
                ),
                parse_mode="Markdown",
                reply_markup=kb
            )
        else:
            # Program needs payment for activation
            kb = InlineKeyboardMarkup()
            kb.add(
                InlineKeyboardButton(
                    "💳 Activate Program & Continue",
                    callback_data="action:activate_program"
                )
            )

            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=(
                    "🎉 *Registration Complete!*\n\n"
                    f"📘 Program: *{program}*\n\n"
                    "Your program space has been created.\n\n"
                    "Next, activate your program to enable resource sharing."
                ),
                parse_mode="Markdown",
                reply_markup=kb
            )

        user_sessions.pop(user_id, None)

    # -------------------------
    # Back to Start Handler
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "action:back_to_start")
    def back_to_start(call):
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🏠 Go to Program Space", callback_data="action:goto_space"))
        kb.add(InlineKeyboardButton("➕ Onboard a New Program", callback_data="action:new_program"))
        
        bot.send_message(
            call.message.chat.id,
            "👋 Welcome to Stackaiv!\n\nWhat would you like to do?",
            reply_markup=kb,
            parse_mode="Markdown"
        )

    # -------------------------
    # Back Navigation
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data.startswith("back:"))
    def handle_back(call):
        user_id = call.from_user.id
        step = call.data.split(":")[1]

        # ✅ Check if session exists
        if user_id not in user_sessions:
            bot.answer_callback_query(call.id, "❌ Session expired. Use /start", show_alert=True)
            return

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
            # ✅ Check if level exists before going back
            if "level" not in user_sessions.get(user_id, {}):
                bot.answer_callback_query(call.id, "❌ Session corrupted. Use /start", show_alert=True)
                user_sessions.pop(user_id, None)
                return

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
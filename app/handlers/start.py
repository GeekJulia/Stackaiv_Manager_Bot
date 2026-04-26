import random
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton 
from ..database.queries import (
    save_user, 
    save_program, 
    get_user_program_id, 
    get_program_info,
    check_program_exists,
    get_program_creator,
    clear_user_program_data,
    clear_semester_data,
    activate_program,
    get_user_info_by_telegram_id,
    remove_duplicate_courses,
    save_admin_message,
    link_user_to_program,
    save_courses,
    get_courses_by_level_and_semester,
    get_users_by_program_id,
    promote_program,
    get_past_levels,
    check_archive_access,
    get_active_programs_count
)
from ..utils.sessions import TTLDict, get_active_program_id
from ..utils.db_operations import with_db_timeout, safe_db_operation, DatabaseTimeoutError
from ..utils.messages import send_loading_message, safe_edit_or_send as edit_message_safe, escape_html
from ..services.payments import initialize_transaction, generate_payment_reference

user_sessions = TTLDict()

QUOTES = [#test
    "Programming is not about typing, it's about thinking.",
    "First, solve the problem. Then, write the code.",
    "Code is like humor. When you have to explain it, it's bad.",
    "Any fool can write code that a computer can understand. Good programmers write code that humans can understand."
]

def show_program_hub_panel(bot, chat_id, program, message_id=None, extra_text=""):
    # Ensure session has active_semester
    session = user_sessions.get(chat_id, {})
    if 'active_semester' not in session:
        session['active_semester'] = 'Alpha'
        user_sessions[chat_id] = session
    
    current_semester = session['active_semester']
    other_semester = 'Omega' if current_semester == 'Alpha' else 'Alpha'
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(" All Courses", callback_data="hub:courses"),
        InlineKeyboardButton(" Add Resource", callback_data="hub:add"),
        InlineKeyboardButton(" Get Resource", callback_data="hub:get"),
        InlineKeyboardButton(" Help Info", callback_data="hub:help"),
    )
    
    # Semester Toggle Button
    kb.add(InlineKeyboardButton(f"🔄 Switch to {other_semester.upper()} Semester", callback_data=f"hub:toggle_semester:{other_semester}"))
    
    # New Archive and Promote Buttons
    kb.add(InlineKeyboardButton(" 🗄 Past Level Archives", callback_data="hub:archives"))
    
    # Check if user is the creator to show 'Promote' button
    creator = safe_db_operation(get_program_creator, None, program['id'])
    if creator and creator['telegram_id'] == chat_id:
        kb.add(InlineKeyboardButton(" 📊 Promote Hub Level", callback_data="hub:promote"))
        kb.add(InlineKeyboardButton(" 🔄 Reset Semester Data", callback_data="hub:reregister"))

    kb.add(InlineKeyboardButton(" 📝 Re-register Details", callback_data="hub:update_details"))
    kb.add(InlineKeyboardButton(" 📞 Contact Admin", callback_data="action:contact_admin"))
    
    text = f" *{program['program_name']} {program['level']} Hub*\n"
    if program.get('graduation_year'):
        text += f"_Class of {program['graduation_year']}_\n"
    
    # Show active semester
    text += f"📊 *Semester:* _{current_semester.upper()}_\n"
    
    text += f"\n{extra_text}What would you like to do?"
    
    if message_id:
        edit_message_safe(bot, chat_id, message_id, text, reply_markup=kb, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=kb, parse_mode="Markdown")


def handle_hub_access(bot, chat_id, program, user_id, message_id=None, extra_text=""):
    """
    Common entry point for Hub access.
    Checks if program is active. If not, checks free tier.
    Redirects to activation screen if necessary.
    """
    program_id = program['id']
    is_active = program.get('is_active', False)
    
    if is_active:
        show_program_hub_panel(bot, chat_id, program, message_id=message_id, extra_text=extra_text)
        return

    # Not active — check for free tier
    active_count = safe_db_operation(get_active_programs_count, 0)
    if active_count < 5:
        # Auto-activate for free
        safe_db_operation(activate_program, False, program_id, is_paid=False)
        # Refresh program info to get updated is_active
        program = safe_db_operation(get_program_info, None, program_id)
        congrats = f"🎉 *Early Adopter Bonus:* Your hub has been activated for FREE!\n\n"
        show_program_hub_panel(bot, chat_id, program, message_id=message_id, extra_text=congrats + extra_text)
    else:
        # Show activation prompt
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton(" 💳 Activate Hub (\u20a63,000)", callback_data="action:activate_hub"))
        kb.add(InlineKeyboardButton(" 📞 Contact Admin", callback_data="action:contact_admin"))
        
        # Prepare session for activation callback
        user_sessions[user_id]['pending_program'] = {
            "level": program['level'],
            "college": program['college'],
            "program_name": program['program_name'],
            "grad_year": str(program.get('graduation_year', '')),
            "saved_user_id": user_id # Using user_id as a proxy for internal user record ID if needed
        }
        
        text = (
            f" ⚠️ *Hub Not Yet Active*\n\n"
            f"The hub for *{program['program_name']}* exists but hasn't been activated yet.\n\n"
            "A one-time activation fee is required to unlock resource sharing for your entire cohort.\n\n"
            "Would you like to activate it now?"
        )
        
        if message_id:
            edit_message_safe(bot, chat_id, message_id, text, reply_markup=kb, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, text, reply_markup=kb, parse_mode="Markdown")


def start_handler(bot):

    @bot.message_handler(commands=['start'])
    def start(message):
        if message.chat.type in ['group', 'supergroup']:
            bot.send_message(
                message.chat.id,
                " *Private Command Only*\n\n"
                "The `/start` command should be used in a private chat with me, not in groups.\n\n"
                " Please send me a private message to get started.",
                parse_mode="Markdown"
            )
            return

        telegram_id = message.from_user.id
        # Check if user exists in DB and has filled details
        user_info = safe_db_operation(get_user_info_by_telegram_id, None, telegram_id)
        program_id = safe_db_operation(get_user_program_id, None, telegram_id)

        if user_info and user_info.get('career'):
            # User is registered
            if program_id:
                quote = random.choice(QUOTES)
                program = safe_db_operation(get_program_info, None, program_id)
                if program:
                    user_sessions[telegram_id] = {
                        "program_id": program_id,
                        "stage": "authenticated"
                    }
                    handle_hub_access(
                        bot, message.chat.id, program, telegram_id,
                        extra_text=f"Welcome back, {user_info['first_name']}!\n_{quote}_\n\n"
                    )
                    return

            quote = random.choice(QUOTES)
            welcome_text = (
                f" Welcome back, {user_info['first_name']}!\n\n"
                f"_\"{quote}\"_\n\n"
                f"Select an option below to proceed:"
            )
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton(" Join an Existing Hub (ID)", callback_data="action:goto_space"))
            kb.add(InlineKeyboardButton(" Contact Admin", callback_data="action:contact_admin"))
            
            bot.send_message(
                message.chat.id,
                welcome_text,
                reply_markup=kb,
                parse_mode="Markdown"
            )
        else:
            # Not fully registered
            msg = (
                " Welcome to Stackaiv!\n\n"
                "To get started, please reply with your details in this exact format:\n\n"
                "<b>Name, Program, Level, Grad Year, College, Career</b>\n\n"
                "⚠️ <b>IMPORTANT: YOUR PROGRAM NAME MUST BE IN FULL (e.g., \"COMPUTER SCIENCE\", NOT \"CS\" OR \"CompSci\"). FAILURE TO DO SO MAY RESULT IN PAYING FOR AN UNRECOGNIZED PROGRAM!</b> ⚠️\n\n"
                "<i>Example: <code>Julia, Computer Science, 400, 2026, CST, Developer</code></i>"
            )
            
            user_sessions[telegram_id] = {"stage": "awaiting_registration"}
            bot.send_message(message.chat.id, msg, parse_mode="HTML")

    @bot.message_handler(commands=['hub'])
    def hub_command(message):
        if message.chat.type in ['group', 'supergroup']:
            bot.send_message(
                message.chat.id,
                " *Private Command Only*\n\nPlease send me a private message to access your Hub.",
                parse_mode="Markdown"
            )
            return

        user_id = message.from_user.id
        program_id = safe_db_operation(get_user_program_id, None, user_id)
        
        if program_id:
            program = safe_db_operation(get_program_info, None, program_id)
            if program:
                user_sessions[user_id] = {
                    "program_id": program_id,
                    "stage": "authenticated"
                }
                handle_hub_access(bot, message.chat.id, program, user_id)
                return

        bot.send_message(
            message.chat.id,
            " ⚠️ *No Active Hub Found*\n\nYou haven't registered or joined a program hub yet.\n\n"
            "Please enter /start to get started.",
            parse_mode="Markdown"
        )

    @bot.message_handler(func=lambda m: user_sessions.get(m.from_user.id, {}).get("stage") == "awaiting_registration")
    def process_registration(message):
        telegram_id = message.from_user.id
        text = message.text

        # Basic Check
        if "," not in text:
            # Ignore or reprompt
            return

        parts = [p.strip() for p in text.split(',')]
        if len(parts) != 6:
            bot.send_message(
                message.chat.id, 
                " Invalid format. Please make sure to include all 6 details separated by commas (`,`).\n\n"
                "_Example: `Julia, Computer Science, 400, 2026, CST, Developer`_",
                parse_mode="Markdown"
            )
            return

        name, program_name, level, grad_year, college, career = parts

        # Normalize Level (e.g. "400" -> "400 Level")
        if "Level" not in level:
            # If it's just a number, append ' Level'
            level = f"{level} Level" if level.isdigit() else level

        # Natural Language Confirmation
        level_str = level.replace(" Level", "")
        confirm_text = f"Your name is {name}, You are in {level_str} level of {program_name} graduating in {grad_year}.\n\nIs this correct?"
        
        # Save temp state
        user_sessions[telegram_id]['pending_registration'] = {
             "name": name, "program_name": program_name, "level": level, "grad_year": grad_year, "college": college, "career": career, "username": message.from_user.username
        }
        user_sessions[telegram_id]['stage'] = "confirm_registration"

        kb = InlineKeyboardMarkup()
        kb.add(
             InlineKeyboardButton("Yes, Confirm", callback_data="reg:confirm"),
             InlineKeyboardButton("No, Cancel", callback_data="reg:cancel")
        )

        bot.send_message(message.chat.id, confirm_text, reply_markup=kb)

    @bot.callback_query_handler(func=lambda call: call.data == "reg:cancel")
    def reg_cancel(call):
        bot.edit_message_text(
            chat_id=call.message.chat.id, 
            message_id=call.message.message_id, 
            text="Registration cancelled. Please send your details again:\n\n"
                 "<b>Name, Program, Level, Grad Year, College, Career</b>\n\n"
                 "⚠️ <b>IMPORTANT: YOUR PROGRAM NAME MUST BE IN FULL (e.g., \"COMPUTER SCIENCE\", NOT \"CS\" OR \"CompSci\"). FAILURE TO DO SO MAY RESULT IN PAYING FOR AN UNRECOGNIZED PROGRAM!</b> ⚠️\n\n"
                 "<i>Example: <code>Julia, Computer Science, 400, 2026, CST, Developer</code></i>",
            parse_mode="HTML"
        )
        user_sessions[call.from_user.id]['stage'] = "awaiting_registration"

    @bot.callback_query_handler(func=lambda call: call.data == "reg:confirm")
    def reg_confirm(call):
        telegram_id = call.from_user.id
        session = user_sessions.get(telegram_id, {})
        pending = session.get('pending_registration')
        if not pending:
            bot.answer_callback_query(call.id, "Session expired, please /start again.")
            return

        name = pending["name"]
        program_name = pending["program_name"]
        level = pending["level"]
        grad_year = pending["grad_year"]
        college = pending["college"]
        career = pending["career"]
        username = pending["username"]

        # Proceed directly to edits
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=" *Processing...*",
            parse_mode="Markdown"
        )
        loading_msg_id = call.message.message_id

        try:
            is_update = session.get('is_update', False)
            
            # Check if user already exists
            user_info = safe_db_operation(get_user_info_by_telegram_id, None, telegram_id)
            if user_info and user_info.get('career') and not is_update:
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton(" Contact Admin", callback_data="action:contact_admin"))
                edit_message_safe(
                    bot,
                    call.message.chat.id,
                    loading_msg_id,
                    " ⚠️ *Account Already Present*\n\nYour account is already registered on Stackaiv. If you need to make changes or believe this is an error, please contact our admin team.",
                    reply_markup=kb,
                    parse_mode="Markdown"
                )
                return

            # Save User
            saved_user_id = safe_db_operation(
                save_user,
                None,
                telegram_id=telegram_id,
                username=username,
                first_name=name,
                career=career
            )

            # Check if program exists
            existing_program = safe_db_operation(
                check_program_exists,
                None,
                college=college,
                program_name=program_name,
                graduation_year=grad_year
            )

            if existing_program:
                program_id = existing_program['id']
                is_active = existing_program.get('is_active', False)

                # Always link the user so they appear in notify_users on activation
                safe_db_operation(link_user_to_program, False, telegram_id, program_id)

                if is_active:
                    # Hub is live — route straight in
                    user_sessions[telegram_id] = {
                        "program_id": program_id,
                        "stage": "authenticated"
                    }

                    kb = InlineKeyboardMarkup(row_width=2)
                    kb.add(InlineKeyboardButton(" Proceed to Hub", callback_data="hub:enter_own"))
                    kb.add(InlineKeyboardButton(" Contact Help Center", callback_data="action:contact_admin"))

                    edit_message_safe(
                        bot,
                        call.message.chat.id,
                        loading_msg_id,
                        " Welcome! Your program hub has already been created.",
                        reply_markup=kb,
                        parse_mode="Markdown"
                    )
                else:
                    # Hub exists but hasn't been paid for yet.
                    # Check for free tier (first 5 programs)
                    active_count = safe_db_operation(get_active_programs_count, 0)
                    
                    if active_count < 5:
                        # Activate for free
                        safe_db_operation(activate_program, False, program_id, is_paid=False)
                        user_sessions[telegram_id] = {
                            "program_id": program_id,
                            "stage": "authenticated"
                        }
                        
                        kb = InlineKeyboardMarkup(row_width=2)
                        kb.add(InlineKeyboardButton(" Enter Hub", callback_data="hub:enter_own"))
                        
                        edit_message_safe(
                            bot,
                            call.message.chat.id,
                            loading_msg_id,
                            (
                                " 🎉 *Congratulations!* 🎉\n\n"
                                f"A hub for *{existing_program['program_name']}* exists and has been **activated for FREE** "
                                "as part of our early-adopter program!\n\n"
                                "You and your coursemates now have full access."
                            ),
                            reply_markup=kb,
                            parse_mode="Markdown"
                        )
                    else:
                        # User is now linked — they'll be automatically notified whenever
                        # anyone (including themselves) completes the activation payment.
                        user_sessions[telegram_id] = {
                            "program_id": program_id,
                            "stage": "authenticated"
                        }
                        user_sessions[telegram_id]['pending_program'] = {
                            "level": existing_program['level'],
                            "college": existing_program['college'],
                            "program_name": existing_program['program_name'],
                            "grad_year": str(existing_program['graduation_year']),
                            "saved_user_id": saved_user_id
                        }

                        kb = InlineKeyboardMarkup()
                        kb.add(InlineKeyboardButton(" 💳 Activate Hub (\u20a63,000)", callback_data="action:activate_hub"))

                        edit_message_safe(
                            bot,
                            call.message.chat.id,
                            loading_msg_id,
                            (
                                " ⚠️ *Hub Not Yet Active*\n\n"
                                f"A hub for *{existing_program['program_name']}* exists but hasn't been activated yet.\n\n"
                                "You've been added to the waitlist — you'll receive an automatic notification "
                                "the moment anyone activates this hub.\n\n"
                                "You can also activate it yourself now:"
                            ),
                            reply_markup=kb,
                            parse_mode="Markdown"
                        )
            else:
                # Program doesn't exist. Check for free tier.
                user_sessions[telegram_id]['pending_program'] = {
                    "level": level, "college": college, "program_name": program_name, "grad_year": grad_year, "saved_user_id": saved_user_id
                }

                active_count = safe_db_operation(get_active_programs_count, 0)
                if active_count < 5:
                    kb = InlineKeyboardMarkup()
                    kb.add(InlineKeyboardButton(" 🚀 Activate for FREE", callback_data="action:activate_hub"))
                    
                    edit_message_safe(
                        bot,
                        call.message.chat.id,
                        loading_msg_id,
                        " Welcome! This program does not have a hub yet.\n\n"
                        "🎁 *Early Adopter Bonus:* You are eligible to activate this hub for **FREE**!",
                        reply_markup=kb,
                        parse_mode="Markdown"
                    )
                else:
                    kb = InlineKeyboardMarkup()
                    kb.add(InlineKeyboardButton(" Activate", callback_data="action:activate_hub"))
                    
                    edit_message_safe(
                        bot,
                        call.message.chat.id,
                        loading_msg_id,
                        " Welcome! This program does not have a hub yet. Please proceed to activate it.",
                        reply_markup=kb,
                        parse_mode="Markdown"
                    )

        except DatabaseTimeoutError:
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton(" 📞 Contact Admin", callback_data="action:contact_admin"))
            edit_message_safe(
                bot,
                call.message.chat.id,
                loading_msg_id,
                " *System is busy*\n\nPlease try again in a moment.",
                parse_mode="Markdown",
                reply_markup=kb
            )
        except Exception as e:
            print(f"ERROR processing registration: {e}")
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton(" 📞 Contact Admin", callback_data="action:contact_admin"))
            edit_message_safe(
                bot,
                call.message.chat.id,
                loading_msg_id,
                " An error occurred during registration. Please try again.",
                parse_mode="Markdown",
                reply_markup=kb
            )

    @bot.callback_query_handler(func=lambda call: call.data == "action:activate_hub")
    def activate_new_hub(call):
        telegram_id = call.from_user.id
        session = user_sessions.get(telegram_id, {})
        pending_program = session.get('pending_program')
        
        if not pending_program:
            bot.answer_callback_query(call.id, "Session expired, please /start again.")
            return

        loading_msg_id = send_loading_message(bot, call.message.chat.id, " *Activating hub...*")
        
        level = pending_program['level']
        college = pending_program['college']
        program_name = pending_program['program_name']
        saved_user_id = pending_program['saved_user_id']
        
        try:
            # First, check if program already exists somehow (race condition)
            program_id = safe_db_operation(check_program_exists, None, college, program_name, pending_program['grad_year'])
            if not program_id:
                # Create the program in PENDING mode (is_active=FALSE)
                program_id = safe_db_operation(
                    save_program, 
                    None, 
                    level, 
                    college, 
                    program_name, 
                    saved_user_id, 
                    pending_program['grad_year']
                )
            else:
                program_id = program_id['id']

            # Link the initiating user immediately so they appear in notify_users
            # when the webhook fires, regardless of whether they are the original
            # creator or a second user who chose to pay for someone else's pending hub.
            safe_db_operation(link_user_to_program, False, telegram_id, program_id)

            # Check for free tier
            active_count = safe_db_operation(get_active_programs_count, 0)
            if active_count < 5:
                # Activate for free
                safe_db_operation(activate_program, False, program_id, is_paid=False)
                
                # Update session
                user_sessions[telegram_id]['stage'] = "authenticated"
                user_sessions[telegram_id]['program_id'] = program_id
                
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton(" Enter Hub", callback_data="hub:enter_own"))
                
                edit_message_safe(
                    bot,
                    call.message.chat.id,
                    loading_msg_id,
                    " 🎉 *Hub Activated for FREE!* 🎉\n\n"
                    f"Your **{program_name}** hub has been activated as one of our first 5 hubs!\n\n"
                    "Tap below to get started.",
                    reply_markup=kb,
                    parse_mode="Markdown"
                )
                return

            # Generate Payment Link (₦3,000)
            ref = generate_payment_reference(telegram_id, program_id, 'ACT')
            email = f"user_{telegram_id}@stackaiv.com"
            
            pay_data = safe_db_operation(
                initialize_transaction,
                None,
                email=email,
                amount=3000,
                reference=ref,
                payment_type='hub_activation',
                program_id=program_id,
                telegram_id=telegram_id
            )

            if pay_data and pay_data.get('status'):
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton(" 💳 Pay ₦3,000", url=pay_data['authorization_url']))
                kb.add(InlineKeyboardButton(" Back to Home", callback_data="action:goto_home"))
                
                activation_msg = (
                    " 🚀 <b>Activate Your Program Hub</b>\n\n"
                    "A fee of <b>₦3,000</b> is required to initialize this hub.\n\n"
                    f"⚠️ <b>THIS IS A ONE-TIME PAYMENT FOR EVERYONE IN {program_name.upper()} {level.upper()}!</b> ⚠️\n\n"
                    "<i>Note: If you are not the Course Rep, you may still proceed with the payment, "
                    "but it is highly recommended that the Course Rep officially handles this activation.</i>\n\n"
                    "Click the button below to pay via Paystack:"
                )
                
                edit_message_safe(
                    bot,
                    call.message.chat.id,
                    loading_msg_id,
                    activation_msg,
                    reply_markup=kb,
                    parse_mode="HTML"
                )
            else:
                error = pay_data.get('error', 'Initialization failed') if pay_data else 'Service unreachable'
                kb = InlineKeyboardMarkup().add(InlineKeyboardButton(" 📞 Contact Admin", callback_data="action:contact_admin"))
                edit_message_safe(bot, call.message.chat.id, loading_msg_id, f" ❌ Payment Error: {error}", reply_markup=kb)
        except Exception as e:
            print(f"ERROR activating hub: {e}")
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton(" 📞 Contact Admin", callback_data="action:contact_admin"))
            edit_message_safe(bot, call.message.chat.id, loading_msg_id, " Failed to initialize payment.", reply_markup=kb)

    @bot.message_handler(func=lambda m: user_sessions.get(m.from_user.id, {}).get("stage") == "awaiting_courses")
    def collect_initial_courses(message):
        telegram_id = message.from_user.id
        text = message.text
        program_id = user_sessions.get(telegram_id, {}).get("program_id")
        
        if not program_id:
            bot.send_message(message.chat.id, " Session expired. Please /start again.")
            return

        # Support both comma and pipe for flexibility
        courses = [c.strip().upper() for c in text.replace("|", ",").split(",") if c.strip()]
        
        if not courses:
            bot.send_message(message.chat.id, " Invalid format. Try: MAT 101, CSC 141")
            return
            
        loading_msg_id = send_loading_message(bot, message.chat.id, " *Saving courses...*")
        
        try:
            safe_db_operation(save_courses, None, program_id, courses)
            user_sessions[user_id]["stage"] = "authenticated"
            program = safe_db_operation(get_program_info, None, program_id)
            handle_hub_access(bot, message.chat.id, program, user_id, message_id=loading_msg_id)
        except Exception as e:
            edit_message_safe(bot, message.chat.id, loading_msg_id, " Could not save courses. Try again.", parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data == "hub:enter_own")
    def enter_own_hub(call):
        telegram_id = call.from_user.id
        program_id = safe_db_operation(get_user_program_id, None, telegram_id)
        
        if not program_id:
            bot.answer_callback_query(call.id, "No active program found.", show_alert=True)
            return
            
        loading_msg_id = send_loading_message(bot, call.message.chat.id, " *Loading Hub...*")
        
        try:
            user_sessions[telegram_id] = {
                "program_id": program_id,
                "stage": "authenticated"
            }
            program = safe_db_operation(get_program_info, None, program_id)
            handle_hub_access(bot, call.message.chat.id, program, telegram_id, message_id=loading_msg_id)
        except Exception as e:
            edit_message_safe(
                bot,
                call.message.chat.id,
                loading_msg_id,
                " An error occurred while opening your hub.",
                parse_mode="Markdown"
            )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("hub:toggle_semester:"))
    def toggle_semester(call):
        user_id = call.from_user.id
        new_semester = call.data.split(":")[2]
        
        session = user_sessions.get(user_id, {})
        session['active_semester'] = new_semester
        user_sessions[user_id] = session
        
        # Reload the hub panel
        program_id = session.get("program_id") or safe_db_operation(get_user_program_id, None, user_id)
        if program_id:
            program = safe_db_operation(get_program_info, None, program_id)
            if program:
                handle_hub_access(bot, call.message.chat.id, program, user_id, message_id=call.message.message_id)
                bot.answer_callback_query(call.id, f"Switched to {new_semester} Semester")
                return
        
        bot.answer_callback_query(call.id, "Error switching semester.")

    @bot.callback_query_handler(func=lambda call: call.data == "action:goto_space")
    def goto_program_space(call):
        user_id = call.from_user.id
        # Check if user already has an active program (checks session first, then DB)
        program_id = get_active_program_id(user_id)
        
        if program_id:
            program = safe_db_operation(get_program_info, None, program_id)
            if program:
                # Update session to ensure it's still marked as authenticated
                session = user_sessions.get(user_id, {})
                session.update({
                    "program_id": program_id,
                    "stage": "authenticated"
                })
                user_sessions[user_id] = session
                
                handle_hub_access(bot, call.message.chat.id, program, user_id, message_id=call.message.message_id)
                return

        # If no program was found, only then prompt for ID
        bot.send_message(
            call.message.chat.id,
            " ⚠️ *Connection Required*\n\nPlease enter the **Program ID** you wish to join (or check /whoami for your ID):",
            parse_mode="Markdown"
        )
        user_sessions[user_id] = {
            "stage": "awaiting_program_id"
        }

    @bot.message_handler(func=lambda m: user_sessions.get(m.from_user.id, {}).get("stage") == "awaiting_program_id")
    def verify_program_id(message):
        user_id = message.from_user.id
        program_id_input = message.text.strip()
        
        loading_msg_id = send_loading_message(bot, message.chat.id, " *Verifying Program ID...*")
        
        try:
            program_id = int(program_id_input)
            try:
                program = safe_db_operation(get_program_info, None, program_id)
                if program:
                    user_sessions[user_id] = {
                        "program_id": program_id,
                        "stage": "authenticated"
                    }
                    safe_db_operation(link_user_to_program, False, user_id, program_id)
                    handle_hub_access(bot, message.chat.id, program, user_id, message_id=loading_msg_id, extra_text="*Welcome back!*\n\n")
                else:
                    edit_message_safe(
                        bot,
                        message.chat.id,
                        loading_msg_id,
                        " Invalid Program ID. Please try again or check the ID.",
                        parse_mode="Markdown"
                    )
                    user_sessions.pop(user_id, None)
                    
            except DatabaseTimeoutError:
                edit_message_safe(bot, message.chat.id, loading_msg_id, " *System is busy*", parse_mode="Markdown")
            except Exception as e:
                edit_message_safe(bot, message.chat.id, loading_msg_id, " An error occurred.", parse_mode="Markdown")
                
        except ValueError:
            edit_message_safe(bot, message.chat.id, loading_msg_id, " Invalid Program ID format.", parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data == "hub:reregister")
    def handle_reregister(call):
        user_id = call.from_user.id
        session = user_sessions.get(user_id, {})
        semester = session.get('active_semester', 'Alpha')
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton(f" ⚠️ Yes, Clear {semester} Semester", callback_data=f"reregister:confirm:{semester}"))
        kb.add(InlineKeyboardButton(" 📞 Contact Admin (Fix Mistake)", callback_data="action:contact_admin_mistake"))
        kb.add(InlineKeyboardButton(" Cancel", callback_data="hub:enter_own"))
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f" ⚠️ *Warning: Re-registration*\n\nYou are about to clear all courses and resources for the **{semester} Semester**.\n\n"
                 "This action is useful if there was a major mistake in course registration.\n\n"
                 "If you only have a minor error, please contact an Admin instead of wiping your data.",
            parse_mode="Markdown",
            reply_markup=kb
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("reregister:confirm:"))
    def confirm_reregister(call):
        user_id = call.from_user.id
        semester = call.data.split(":")[2]
        
        loading_msg_id = send_loading_message(bot, call.message.chat.id, f" *Clearing {semester} data...*")
        try:
            session = user_sessions.get(user_id, {})
            program_id = session.get("program_id") or safe_db_operation(get_user_program_id, None, user_id)
            if program_id:
                safe_db_operation(clear_semester_data, None, program_id, semester)
            
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton(" ➕ Add Courses", callback_data="notes:add_courses"))
            kb.add(InlineKeyboardButton(" ⬅️ Back to Hub", callback_data="hub:enter_own"))
            
            edit_message_safe(
                bot, call.message.chat.id, loading_msg_id,
                f" ✅ *{semester} Semester Data cleared!*\n\nAll courses and resources for this semester have been removed.\nYou can now add your courses again.",
                parse_mode="Markdown", reply_markup=kb
            )
        except Exception as e:
            edit_message_safe(bot, call.message.chat.id, loading_msg_id, " ❌ An error occurred.", parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data == "reregister:cancel")
    def cancel_reregister(call):
        bot.send_message(call.message.chat.id, " Re-registration cancelled. Your data remains intact.", parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data == "hub:update_details")
    def update_details_start(call):
        user_id = call.from_user.id
        user_sessions[user_id] = {
            "stage": "awaiting_registration",
            "is_update": True
        }
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=" 📝 <b>Re-register Your Details</b>\n\nPlease send your details again in the following format separated by commas (`,`):\n\n"
                 "<b>Name, Program, Level, Grad Year, College, Career</b>\n\n"
                 "⚠️ <b>IMPORTANT: YOUR PROGRAM NAME MUST BE IN FULL (e.g., \"COMPUTER SCIENCE\", NOT \"CS\" OR \"CompSci\"). FAILURE TO DO SO MAY RESULT IN PAYING FOR AN UNRECOGNIZED PROGRAM!</b> ⚠️\n\n"
                 "<i>Example: <code>Julia, Computer Science, 400, 2026, CST, Developer</code></i>",
            parse_mode="HTML"
        )

    @bot.message_handler(commands=['whoami'])
    def whoami(message):
        if message.chat.type in ['group', 'supergroup']:
            bot.send_message(
                message.chat.id,
                " *Private Command Only*\n\nPlease send me a private message to check your info.",
                parse_mode="Markdown"
            )
            return
        
        user_id = message.from_user.id
        loading_msg_id = send_loading_message(bot, message.chat.id, " *Fetching your info...*")
        
        try:
            program_id = safe_db_operation(get_user_program_id, None, user_id)
            user_info = safe_db_operation(get_user_info_by_telegram_id, None, user_id)
            if program_id and user_info:
                program_info = safe_db_operation(get_program_info, None, program_id)
                if program_info:
                    career_info = f" \n Career: {user_info.get('career', 'N/A')}" if user_info.get('career') else ""
                    edit_message_safe(
                        bot,
                        message.chat.id,
                        loading_msg_id,
                        f" <b>Your Info</b>\n\n"
                        f" Username: @{message.from_user.username or 'N/A'}\n"
                        f" Telegram ID: <code>{user_id}</code>{career_info}\n\n"
                        f" Program: <b>{program_info['program_name']}</b>\n"
                        f" College: {program_info['college']}\n"
                        f" Level: {program_info['level']}\n"
                        f" Program ID: <code>{program_id}</code>\n\n"
                        f"Use this Program ID with /setupgroup in your group chat",
                        parse_mode="HTML"
                    )
                else:
                    edit_message_safe(bot, message.chat.id, loading_msg_id, " Program info not found.", parse_mode="HTML")
            else:
                edit_message_safe(bot, message.chat.id, loading_msg_id, " Not registered yet.\n\nRun /start to complete registration.", parse_mode="HTML")
        except Exception:
            edit_message_safe(bot, message.chat.id, loading_msg_id, " An error occurred.", parse_mode="Markdown")

    @bot.message_handler(commands=['cleanup'])
    def cleanup_duplicates(message):
        user_id = message.from_user.id
        loading_msg_id = send_loading_message(bot, message.chat.id, " *Cleaning up duplicates...*")
        try:
            program_id = get_active_program_id(user_id)
            if not program_id:
                edit_message_safe(bot, message.chat.id, loading_msg_id, " No program found.", parse_mode="Markdown")
                return
            count = safe_db_operation(remove_duplicate_courses, 0, program_id)
            edit_message_safe(bot, message.chat.id, loading_msg_id, f" *Cleanup Complete!*\n\n{count} duplicate course(s) removed.", parse_mode="Markdown")
        except Exception as e:
            edit_message_safe(bot, message.chat.id, loading_msg_id, f" Error: {str(e)}", parse_mode="Markdown")

    # -------------------------
    # Contact Admin Flow
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "action:contact_admin")
    def contact_admin_start(call):
        user_id = call.from_user.id
        user_sessions[user_id] = {"stage": "awaiting_admin_message"}
        
        bot.send_message(
            call.message.chat.id,
            " *Contact Admin*\n\nPlease type your message below. It will be sent directly to our support team.\n\n_Type your message now..._",
            parse_mode="Markdown"
        )

    @bot.callback_query_handler(func=lambda call: call.data == "action:contact_admin_mistake")
    def contact_admin_mistake(call):
        user_id = call.from_user.id
        username = call.from_user.username or "N/A"
        first_name = call.from_user.first_name
        
        auto_msg = f"I made a mistake in my course registration/setup. Please help me fix it. (ID: {user_id})"
        
        loading_msg_id = send_loading_message(bot, call.message.chat.id, " *Notifying Admin...*")
        
        try:
            safe_db_operation(
                save_admin_message,
                None,
                telegram_id=user_id,
                username=username,
                first_name=first_name,
                message_text=auto_msg,
                message_type='support'
            )
            
            edit_message_safe(
                bot,
                call.message.chat.id,
                loading_msg_id,
                " ✅ *Admin Notified!*\n\nOur support team has been informed about your registration issue.\n"
                f"We will reach out to you directly at @{username} soon.\n\n"
                "You can continue using the Hub in the meantime.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton(" Back to Hub", callback_data="hub:enter_own"))
            )
        except Exception as e:
            edit_message_safe(bot, call.message.chat.id, loading_msg_id, " ❌ Failed to notify admin.")

    @bot.message_handler(func=lambda m: user_sessions.get(m.from_user.id, {}).get("stage") == "awaiting_admin_message")
    def handle_admin_message_input(message):
        user_id = message.from_user.id
        text = message.text.strip()
        
        if not text:
            return

        # Natural Confirmation Flow
        user_sessions[user_id]['pending_admin_msg'] = text
        user_sessions[user_id]['stage'] = "confirm_admin_message"

        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton("✅ Yes, Send", callback_data="admin_msg:confirm"),
            InlineKeyboardButton("❌ No, Re-type", callback_data="admin_msg:cancel")
        )

        bot.send_message(
            message.chat.id,
            f" *Confirm Your Message*\n\nYou are about to send this message to the admin:\n\n\"{text}\"\n\nIs this correct?",
            reply_markup=kb,
            parse_mode="Markdown"
        )

    @bot.callback_query_handler(func=lambda call: call.data == "admin_msg:confirm")
    def confirm_admin_message(call):
        user_id = call.from_user.id
        session = user_sessions.get(user_id, {})
        text = session.get('pending_admin_msg')
        
        if not text:
            bot.answer_callback_query(call.id, "Session expired, please try again.")
            return

        loading_msg_id = send_loading_message(bot, call.message.chat.id, " *Sending your message...*")
        
        try:
            safe_db_operation(
                save_admin_message,
                None,
                telegram_id=user_id,
                username=call.from_user.username,
                first_name=call.from_user.first_name,
                message_text=text,
                message_type='support'
            )
            
            user_sessions.pop(user_id, None)
            
            edit_message_safe(
                bot,
                call.message.chat.id,
                loading_msg_id,
                " ✅ *Message Sent!*\n\nOur admin team has received your message and will get back to you shortly if needed.\n\nUse /start to return home.",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"ERROR saving admin message: {e}")
            edit_message_safe(
                bot,
                call.message.chat.id,
                loading_msg_id,
                " ❌ Failed to send message. Please try again later.",
                parse_mode="Markdown"
            )

    @bot.callback_query_handler(func=lambda call: call.data == "admin_msg:cancel")
    def cancel_admin_message(call):
        user_id = call.from_user.id
        user_sessions[user_id] = {"stage": "awaiting_admin_message"}
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=" Message cancelled. Please type your message again below:",
            parse_mode="Markdown"
        )

    # -------------------------
    # Hub Promotion & Archives
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == 'hub:promote')
    def hub_promote_prompt(call):
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton(' ⚠️ Yes, Promote Hub', callback_data='promote:confirm'))
        kb.add(InlineKeyboardButton(' Cancel', callback_data='hub:enter_own'))
        
        warning_text = (
            "<b>📊 PROMOTE HUB LEVEL</b>\n\n"
            "This will advance your cohort's academic level (e.g., 100L → 200L).\n\n"
            "⚠️ <b>CRITICAL CONSEQUENCES:</b>\n"
            "• All current courses will be <b>FROZEN</b> and moved to archives.\n"
            "• Students will need to <b>PAY</b> (₦3,000) to access these archives later.\n"
            "• This action <b>CANNOT BE UNDONE</b>.\n\n"
            "🛡 <b>TRANSPARENCY NOTICE:</b>\n"
            "To prevent unauthorized changes, confirming this promotion will <b>BROADCAST your Name and Telegram ID</b> to everyone in this cohort."
        )
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=warning_text,
            reply_markup=kb,
            parse_mode='HTML'
        )

    @bot.callback_query_handler(func=lambda call: call.data == 'promote:confirm')
    def hub_promote_execution(call):
        user_id = call.from_user.id
        program_id = get_active_program_id(user_id)
        
        loading_id = send_loading_message(bot, call.message.chat.id, ' <b>Advancing Cohort Level...</b>')
        
        # Capture initiator details for the broadcast
        initiator = call.from_user
        initiator_name = f"{initiator.first_name} {initiator.last_name or ''}".strip()
        initiator_info = f"<b>{escape_html(initiator_name)}</b> (@{escape_html(initiator.username)})" if initiator.username else f"<b>{escape_html(initiator_name)}</b>"
        
        new_level = safe_db_operation(promote_program, None, program_id)
        
        if new_level:
            # Broadcast to all cohort members
            notify_users = safe_db_operation(get_users_by_program_id, [], program_id)
            broadcast_msg = (
                "📣 <b>HUB LEVEL PROMOTED</b>\n\n"
                f"Your Hub has been advanced to <b>{escape_html(new_level)}</b>.\n\n"
                f"👤 <b>Triggered By:</b> {initiator_info}\n"
                f"🆔 <b>User ID:</b> <code>{initiator.id}</code>\n\n"
                "Previous courses are now available in the <b>Past Level Archives</b>."
            )
            
            for tg_id in notify_users:
                if tg_id == call.message.chat.id: continue
                try:
                    bot.send_message(tg_id, broadcast_msg, parse_mode="HTML")
                except Exception:
                    pass

            edit_message_safe(
                bot, call.message.chat.id, loading_id,
                f" 🚀 <b>Promotion Successful!</b>\n\nYour hub has been advanced to <b>{escape_html(new_level)}</b>.\n\n"
                "A notification has been sent to all cohort members.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton(' Back to Hub', callback_data='hub:enter_own'))
            )
        else:
            edit_message_safe(bot, call.message.chat.id, loading_id, ' ❌ <b>Error:</b> Promotion failed. Please try again later.', parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == 'hub:archives')
    def hub_archives_root(call):
        user_id = call.from_user.id
        program_id = get_active_program_id(user_id)
        program = safe_db_operation(get_program_info, None, program_id)
        
        if not program: return
        
        # get_past_levels is imported from queries
        past_levels = safe_db_operation(get_past_levels, [], program_id, program['level'])
        
        if not past_levels:
            bot.answer_callback_query(call.id, 'No past levels found in archives.', show_alert=True)
            return

        kb = InlineKeyboardMarkup(row_width=2)
        for lvl in past_levels:
            kb.add(InlineKeyboardButton(f' {lvl}', callback_data=f'archive:lvl:{lvl}'))
        kb.add(InlineKeyboardButton(' Back', callback_data='hub:enter_own'))

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=' <b>🗄 Academic Vault (Archives)</b>\n\nSelect a past level to browse:',
            reply_markup=kb,
            parse_mode='HTML'
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith('archive:lvl:'))
    def archive_level_selected(call):
        level = call.data.split(':')[2]
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton(' Alpha Semester', callback_data=f'archive:sem:{level}:Alpha'),
            InlineKeyboardButton(' Omega Semester', callback_data=f'archive:sem:{level}:Omega')
        )
        kb.add(InlineKeyboardButton(' Back', callback_data='hub:archives'))

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f' <b>{escape_html(level)} Archives</b>\n\nSelect the semester:',
            reply_markup=kb,
            parse_mode='HTML'
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith('archive:sem:'))
    def archive_semester_selected(call):
        parts = call.data.split(':')
        level = parts[2]
        semester = parts[3]
        program_id = get_active_program_id(call.from_user.id)
        
        # get_courses_by_level_and_semester is imported from queries
        courses = safe_db_operation(get_courses_by_level_and_semester, [], program_id, level, semester)
        
        if not courses:
            bot.answer_callback_query(call.id, f'No courses found for {level} {semester}.', show_alert=True)
            return

        kb = InlineKeyboardMarkup(row_width=2)
        for c in courses:
            kb.add(InlineKeyboardButton(c['course_code'], callback_data=f'archive:get:{level}:{c["id"]}'))
        kb.add(InlineKeyboardButton(' Back', callback_data=f'archive:lvl:{level}'))

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f' <b>{escape_html(level)} {escape_html(semester)} Courses</b>\n\nSelect a course to access resources:',
            reply_markup=kb,
            parse_mode='HTML'
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith('archive:get:'))
    def handle_archive_access(call):
        parts = call.data.split(':')
        level = parts[2]
        course_id = int(parts[3])
        user_id = call.from_user.id
        
        # Check if user has access (check_archive_access imported from queries)
        has_access = safe_db_operation(check_archive_access, False, user_id=user_id, target_level=level, target_course_id=course_id)
        
        if has_access:
            bot.answer_callback_query(call.id, 'Access Granted!')
            # bypass standard gate for this session
            user_sessions[user_id]['archive_bypass'] = course_id
            
            # Show standard get resource flow
            from .files import show_resource_types_for_get
            show_resource_types_for_get(
                bot,
                call.message.chat.id,
                course_id,
                message_id=call.message.message_id,
                user_id=user_id
            )
        else:
            # Generate payment options
            loading_id = send_loading_message(bot, call.message.chat.id, " *Initializing vault access...*")
            email = f"user_{user_id}@stackaiv.com"
            
            # Course Access (₦500)
            ref_course = generate_payment_reference(user_id, None, 'ARC_C')
            pay_course = safe_db_operation(initialize_transaction, None, email, 500, ref_course, 'archive_access', None, course_id, None)
            
            # Level Access (₦2,500)
            ref_level = generate_payment_reference(user_id, None, 'ARC_L')
            pay_level = safe_db_operation(initialize_transaction, None, email, 2500, ref_level, 'archive_access', None, None, level)
            
            # Full Vault Access (₦10,000)
            ref_full = generate_payment_reference(user_id, None, 'ARC_F')
            pay_full = safe_db_operation(initialize_transaction, None, email, 10000, ref_full, 'archive_access', None, None, 'FULL_VAULT')

            kb = InlineKeyboardMarkup()
            if pay_course and pay_course.get('status'):
                kb.add(InlineKeyboardButton(f' Unlock This Course (₦500)', url=pay_course['authorization_url']))
            if pay_level and pay_level.get('status'):
                kb.add(InlineKeyboardButton(f' Unlock All {level} (₦2,500)', url=pay_level['authorization_url']))
            if pay_full and pay_full.get('status'):
                kb.add(InlineKeyboardButton(f' Full Archive Bypass (₦10,000)', url=pay_full['authorization_url']))
            
            kb.add(InlineKeyboardButton(' Back', callback_data=f'archive:sem:{level}:Alpha'))
            
            edit_message_safe(
                bot,
                call.message.chat.id,
                loading_id,
                f' 🔒 *Premium Vault Access Required*\n\nHistorical resources for **{level}** are locked.\n\nChoose a subscription tier to unlock access:',
                reply_markup=kb,
                parse_mode='Markdown'
            )

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
    activate_program,
    get_user_info_by_telegram_id,
    remove_duplicate_courses,
    save_admin_message,
)
from .notes import get_active_program_id
from ..utils.db_operations import with_db_timeout, safe_db_operation, DatabaseTimeoutError
from ..utils.sessions import TTLDict
from ..utils.messages import send_loading_message, safe_edit_or_send as edit_message_safe

user_sessions = TTLDict()

QUOTES = [
    "Programming is not about typing, it's about thinking.",
    "First, solve the problem. Then, write the code.",
    "Code is like humor. When you have to explain it, it's bad.",
    "Any fool can write code that a computer can understand. Good programmers write code that humans can understand."
]

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
            quote = random.choice(QUOTES)
            welcome_text = (
                f" Welcome back, {user_info['first_name']}!\n\n"
                f"_\"{quote}\"_\n\n"
                f"Select an option below to proceed:"
            )
            kb = InlineKeyboardMarkup()
            if program_id:
                kb.add(InlineKeyboardButton(" Proceed to Program Hub", callback_data="hub:enter_own"))
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
                "**Name | Program | Level | College | Career**\n\n"
                "_Example: `Julia | Computer Science | 400 | CST | Developer`_"
            )
            
            user_sessions[telegram_id] = {"stage": "awaiting_registration"}
            bot.send_message(message.chat.id, msg, parse_mode="Markdown")

    @bot.message_handler(func=lambda m: user_sessions.get(m.from_user.id, {}).get("stage") == "awaiting_registration")
    def process_registration(message):
        telegram_id = message.from_user.id
        text = message.text

        # Basic Check
        if "|" not in text:
            # Ignore or reprompt
            return

        parts = [p.strip() for p in text.split('|')]
        if len(parts) != 5:
            bot.send_message(
                message.chat.id, 
                " Invalid format. Please make sure to include all 5 details separated by `|`.\n\n"
                "_Example: `Julia | Computer Science | 400 | CST | Developer`_",
                parse_mode="Markdown"
            )
            return

        name, program_name, level, college, career = parts

        loading_msg_id = send_loading_message(bot, message.chat.id, " *Processing registration...*")

        try:
            # Save User
            saved_user_id = safe_db_operation(
                save_user,
                None,
                telegram_id=telegram_id,
                username=message.from_user.username,
                first_name=name,
                career=career
            )

            # Check if program exists
            existing_program = safe_db_operation(
                check_program_exists,
                None,
                level=level,
                college=college,
                program_name=program_name
            )

            if existing_program:
                # Program exists. Auto join them to it
                program_id = existing_program['id']
                user_sessions[telegram_id] = {
                    "program_id": program_id,
                    "stage": "authenticated"
                }

                kb = InlineKeyboardMarkup(row_width=2)
                kb.add(
                    InlineKeyboardButton(" All Courses", callback_data="hub:courses"),
                    InlineKeyboardButton(" Add Resource", callback_data="hub:add"),
                    InlineKeyboardButton(" Get Resource", callback_data="hub:get"),
                    InlineKeyboardButton(" Help Info", callback_data="hub:help"),
                )
                kb.add(InlineKeyboardButton(" Re-register (Reset)", callback_data="hub:reregister"))

                edit_message_safe(
                    bot,
                    message.chat.id,
                    loading_msg_id,
                    f" *Welcome to the {program_name} {level} Hub!*\n\nWhat would you like to do?",
                    reply_markup=kb,
                    parse_mode="Markdown"
                )
            else:
                # Program doesn't exist. Prepare activation.
                user_sessions[telegram_id]['pending_program'] = {
                    "level": level, "college": college, "program_name": program_name, "saved_user_id": saved_user_id
                }

                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton(" Activate Hub", callback_data="action:activate_hub"))
                
                edit_message_safe(
                    bot,
                    message.chat.id,
                    loading_msg_id,
                    f" The hub for **{program_name} {level}** doesn't exist yet.\n\nClick below to activate it and register your courses.",
                    reply_markup=kb,
                    parse_mode="Markdown"
                )

        except DatabaseTimeoutError:
            edit_message_safe(
                bot,
                message.chat.id,
                loading_msg_id,
                " *System is busy*\n\nPlease try again in a moment.",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"ERROR processing registration: {e}")
            edit_message_safe(
                bot,
                message.chat.id,
                loading_msg_id,
                " An error occurred during registration. Please try again.",
                parse_mode="Markdown"
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
            # Save and activate program
            program_id = safe_db_operation(save_program, None, level, college, program_name, saved_user_id)
            safe_db_operation(activate_program, None, program_id, is_paid=False)
            
            user_sessions[telegram_id] = {
                "program_id": program_id,
                "stage": "authenticated"
            }
            
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton(" Add Courses", callback_data="notes:add_courses"))
            
            edit_message_safe(
                bot,
                call.message.chat.id,
                loading_msg_id,
                f" *{program_name} {level} Hub Activated!*\n\nPlease proceed to register your courses.",
                reply_markup=kb,
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"ERROR activating hub: {e}")
            edit_message_safe(
                bot,
                call.message.chat.id,
                loading_msg_id,
                " Failed to activate hub. Please try again later.",
                parse_mode="Markdown"
            )


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
            
            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(
                InlineKeyboardButton(" All Courses", callback_data="hub:courses"),
                InlineKeyboardButton(" Add Resource", callback_data="hub:add"),
                InlineKeyboardButton(" Get Resource", callback_data="hub:get"),
                InlineKeyboardButton(" Help Info", callback_data="hub:help"),
            )
            kb.add(InlineKeyboardButton(" Re-register", callback_data="hub:reregister"))
            
            edit_message_safe(
                bot,
                call.message.chat.id,
                loading_msg_id,
                f" You're now in your **{program['program_name']} {program['level']}** digital central resource hub.\n\nWhat would you like to do?",
                reply_markup=kb,
                parse_mode="Markdown"
            )
        except Exception as e:
            edit_message_safe(
                bot,
                call.message.chat.id,
                loading_msg_id,
                " An error occurred while opening your hub.",
                parse_mode="Markdown"
            )

    @bot.callback_query_handler(func=lambda call: call.data == "action:goto_space")
    def goto_program_space(call):
        bot.send_message(
            call.message.chat.id,
            " Please enter the Program ID you want to join:",
            parse_mode="Markdown"
        )
        user_sessions[call.from_user.id] = {
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
                    kb = InlineKeyboardMarkup(row_width=2)
                    kb.add(
                        InlineKeyboardButton(" All Courses", callback_data="hub:courses"),
                        InlineKeyboardButton(" Add Resource", callback_data="hub:add"),
                        InlineKeyboardButton(" Get Resource", callback_data="hub:get"),
                        InlineKeyboardButton(" Help Info", callback_data="hub:help"),
                    )
                    kb.add(InlineKeyboardButton(" Re-register", callback_data="hub:reregister"))
                    
                    edit_message_safe(
                        bot,
                        message.chat.id,
                        loading_msg_id,
                        f" *Welcome back!*\n\nYou're now in your *{program['program_name']} {program['level']}* digital central resource hub.\n\nWhat would you like to do?",
                        parse_mode="Markdown",
                        reply_markup=kb
                    )
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
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton(" Yes, Clear Everything", callback_data="reregister:confirm"))
        kb.add(InlineKeyboardButton(" Cancel", callback_data="reregister:cancel"))
        
        bot.send_message(
            call.message.chat.id,
            " *Warning: Re-registration*\n\nThis will **delete all your courses and resource types**.\nYou'll need to start over from scratch.\n\nAre you sure you want to continue?",
            parse_mode="Markdown",
            reply_markup=kb
        )

    @bot.callback_query_handler(func=lambda call: call.data == "reregister:confirm")
    def confirm_reregister(call):
        user_id = call.from_user.id
        loading_msg_id = send_loading_message(bot, call.message.chat.id, " *Clearing your data...*")
        try:
            session = user_sessions.get(user_id, {})
            program_id = session.get("program_id") or safe_db_operation(get_user_program_id, None, user_id)
            if program_id:
                safe_db_operation(clear_user_program_data, None, program_id)
            
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton(" Add Courses", callback_data="notes:add_courses"))
            kb.add(InlineKeyboardButton(" Back to Space", callback_data="hub:enter_own"))
            
            edit_message_safe(
                bot, call.message.chat.id, loading_msg_id,
                " *Data cleared successfully!*\n\nAll courses and resource types have been removed.\nYou can now add your courses again.",
                parse_mode="Markdown", reply_markup=kb
            )
        except Exception as e:
            edit_message_safe(bot, call.message.chat.id, loading_msg_id, " An error occurred.", parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data == "reregister:cancel")
    def cancel_reregister(call):
        bot.send_message(call.message.chat.id, " Re-registration cancelled. Your data remains intact.", parse_mode="Markdown")

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

    @bot.message_handler(func=lambda m: user_sessions.get(m.from_user.id, {}).get("stage") == "awaiting_admin_message")
    def handle_admin_message(message):
        user_id = message.from_user.id
        text = message.text.strip()
        
        if not text:
            return

        loading_msg_id = send_loading_message(bot, message.chat.id, " *Sending your message...*")
        
        try:
            safe_db_operation(
                save_admin_message,
                None,
                telegram_id=user_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                message_text=text,
                message_type='support'
            )
            
            user_sessions.pop(user_id, None)
            
            edit_message_safe(
                bot,
                message.chat.id,
                loading_msg_id,
                " *Message Sent!*\n\nOur admin team has received your message and will get back to you shortly if needed.\n\nUse /start to return home.",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"ERROR saving admin message: {e}")
            edit_message_safe(
                bot,
                message.chat.id,
                loading_msg_id,
                " Failed to send message. Please try again later.",
                parse_mode="Markdown"
            )
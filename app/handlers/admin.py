import os
import time
import threading
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from ..database.queries import (
    get_all_transactions,
    get_transaction_by_id,
    get_all_programs,
    delete_program,
    get_all_users,
    get_user_program_id,
    get_all_admin_messages,
    get_admin_messages_count
)
from ..utils.sessions import TTLDict
from ..utils.messages import escape_markdown
from ..utils.pagination import paginate_items
admin_sessions = TTLDict()

# Replace with your actual admin Telegram ID
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))


def send_with_retry(bot, telegram_id, text, retries=3):
    """Send a message with retry logic and exponential backoff for transient errors."""
    for attempt in range(retries):
        try:
            bot.send_message(telegram_id, text, parse_mode="Markdown")
            return True
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1 * (attempt + 1))  # backoff: 1s, 2s
            else:
                return False


def admin_handler(bot):
    """
    Admin handler for special admin functions.
    Command: /admin7105
    """

    def _send_admin_panel(chat_id):
        """Helper to render the admin control panel (used by command and callbacks)."""
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton(" Transactions", callback_data="admin:list_transactions"),
            InlineKeyboardButton(" Fetch Transaction", callback_data="admin:fetch_transaction")
        )
        kb.add(
            InlineKeyboardButton(" All Programs", callback_data="admin:list_programs"),
            InlineKeyboardButton(" Delete Program", callback_data="admin:delete_program")
        )
        kb.add(
            InlineKeyboardButton(" User Messages", callback_data="admin:list_messages"),
            InlineKeyboardButton(" Broadcast", callback_data="admin:broadcast")
        )
        kb.add(
            InlineKeyboardButton(" List Users", callback_data="admin:list_users"),
            InlineKeyboardButton(" Stop Bot", callback_data="admin:stop_bot")
        )

        bot.send_message(
            chat_id,
            (
                " *Admin Control Panel*\n\n"
                "Welcome back, Administrator.\n"
                "Select an action below:"
            ),
            parse_mode="Markdown",
            reply_markup=kb
        )

    @bot.message_handler(commands=['admin7105'])
    def admin_command(message):
        user_id = message.from_user.id

        # Security check - only allow admin
        if user_id != ADMIN_ID:
            bot.send_message(
                message.chat.id,
                " *Unauthorized Access*\n\n"
                "This command is restricted to administrators only.",
                parse_mode="Markdown"
            )
            return

        _send_admin_panel(message.chat.id)

    @bot.callback_query_handler(func=lambda call: call.data == "admin:panel")
    def admin_panel_callback(call):
        """Allow returning to the admin panel via inline button."""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return
        _send_admin_panel(call.message.chat.id)

    # -------------------------
    # LIST ALL TRANSACTIONS
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin:list_transactions"))
    def list_transactions(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return

        try:
            transactions = get_all_transactions()

            total = len(transactions)
            if not total:
                bot.send_message(
                    call.message.chat.id,
                    " *Transactions*\n\nNo transactions found.",
                    parse_mode="Markdown"
                )
                return

            recent = transactions[-100:] if total > 100 else transactions
            page_items, page, total_pages = paginate_items(call.data, recent, 10)

            text = f" *Recent Transactions* (Page {page + 1}/{total_pages})\n\n"

            for t in page_items:
                status = " Success" if t['status'] == 'success' else " Pending"
                amount_naira = int(t['amount'])
                date = str(t.get('created_at', 'N/A'))[:10]
                ptype = t.get('payment_type', 'hub_activation').replace('_', ' ').title()

                text += (
                    f"*ID:* {t['id']} | *Type:* {ptype}\n"
                    f"*Status:* {status} | *Amount:* ₦{amount_naira:,}\n"
                    f"*Reference:* `{t['reference']}`\n"
                    f"*Date:* {date}\n"
                    f"──────────────────\n"
                )

            kb = InlineKeyboardMarkup()
            nav_buttons = []
            if page > 0:
                nav_buttons.append(InlineKeyboardButton(" Prev", callback_data=f"admin:list_transactions:{page - 1}"))
            if page + 1 < total_pages:
                nav_buttons.append(InlineKeyboardButton(" Next", callback_data=f"admin:list_transactions:{page + 1}"))
            if nav_buttons:
                kb.add(*nav_buttons)
            kb.add(InlineKeyboardButton(" Refresh", callback_data="admin:list_transactions:0"))

            bot.send_message(
                call.message.chat.id,
                text,
                parse_mode="Markdown",
                reply_markup=kb
            )

        except Exception as e:
            bot.send_message(
                call.message.chat.id,
                f" Error: {str(e)}",
                parse_mode="Markdown"
            )

    # -------------------------
    # FETCH TRANSACTION BY ID
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "admin:fetch_transaction")
    def fetch_transaction_handler(call):
        user_id = call.from_user.id
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return

        admin_sessions[user_id] = {"stage": "awaiting_transaction_id"}

        bot.send_message(
            call.message.chat.id,
            " *Fetch Transaction*\n\n"
            "Enter the transaction ID:",
            parse_mode="Markdown"
        )

    @bot.message_handler(func=lambda m: admin_sessions.get(m.from_user.id, {}).get("stage") == "awaiting_transaction_id")
    def receive_transaction_id(message):
        user_id = message.from_user.id

        try:
            transaction_id = int(message.text.strip())
            transaction = get_transaction_by_id(transaction_id)

            if transaction:
                amount_naira = int(transaction['amount'])
                ptype = transaction.get('payment_type', 'hub_activation').replace('_', ' ').title()
                
                text = (
                    f" *Transaction Details*\n\n"
                    f"ID: `{transaction['id']}`\n"
                    f"Type: **{ptype}**\n"
                    f"Reference: `{transaction['reference']}`\n"
                    f"Amount: ₦{amount_naira:,}\n"
                    f"Status: {transaction['status'].upper()}\n"
                    f"Program: {transaction.get('program_name', 'N/A')}\n"
                    f"User: {transaction.get('user_name', 'N/A')}\n"
                    f"Date: {transaction['created_at']}\n"
                )
                
                if transaction.get('metadata'):
                    import json
                    try:
                        meta = transaction['metadata']
                        if isinstance(meta, str): meta = json.loads(meta)
                        text += "\n*Metadata:*\n"
                        for k, v in meta.items():
                            if v: text += f"- {k}: `{v}`\n"
                    except: pass
            else:
                text = f" Transaction with ID `{transaction_id}` not found."

            bot.send_message(
                message.chat.id,
                text,
                parse_mode="Markdown"
            )
            admin_sessions.pop(user_id, None)

        except ValueError:
            bot.send_message(
                message.chat.id,
                " Invalid transaction ID. Please enter a number.",
                parse_mode="Markdown"
            )
        except Exception as e:
            bot.send_message(
                message.chat.id,
                f" Error: {str(e)}",
                parse_mode="Markdown"
            )
            admin_sessions.pop(user_id, None)

    # -------------------------
    # LIST ALL PROGRAMS
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin:list_programs"))
    def list_programs(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return

        try:
            programs = get_all_programs()

            programs = sorted(programs, key=lambda p: p['id'], reverse=True)
            total = len(programs)
            if not total:
                bot.send_message(
                    call.message.chat.id,
                    " *Programs*\n\nNo programs found.",
                    parse_mode="Markdown"
                )
                return

            page_items, page, total_pages = paginate_items(call.data, programs, 5)

            text = f" *All Programs* (Page {page + 1}/{total_pages})\n\n"

            for p in page_items:
                status = " Active" if p['is_active'] else " Inactive"

                program_name = str(p['name']).replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
                level = str(p['level']).replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
                college = str(p['college']).replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
                creator_name = str(p['creator_name']).replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
                creator_username = str(p['creator_username']).replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')

                text += (
                    f"ID: `{p['id']}`\n"
                    f"Name: {program_name}\n"
                    f"Level: {level} | College: {college}\n"
                    f"Creator: {creator_name} (@{creator_username})\n"
                    f"Status: {status}\n"
                    f"──────────────────\n"
                )

            kb = InlineKeyboardMarkup()
            nav_buttons = []
            if page > 0:
                nav_buttons.append(InlineKeyboardButton(" Prev", callback_data=f"admin:list_programs:{page - 1}"))
            if page + 1 < total_pages:
                nav_buttons.append(InlineKeyboardButton(" Next", callback_data=f"admin:list_programs:{page + 1}"))
            if nav_buttons:
                kb.add(*nav_buttons)
            kb.add(InlineKeyboardButton(" Refresh", callback_data="admin:list_programs:0"))

            bot.send_message(
                call.message.chat.id,
                text,
                parse_mode="Markdown",
                reply_markup=kb
            )

        except Exception as e:
            bot.send_message(
                call.message.chat.id,
                f" Error: {str(e)}",
                parse_mode="Markdown"
            )

    # -------------------------
    # DELETE PROGRAM
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "admin:delete_program")
    def delete_program_handler(call):
        user_id = call.from_user.id
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return

        admin_sessions[user_id] = {"stage": "awaiting_program_id_delete"}

        bot.send_message(
            call.message.chat.id,
            " *Delete Program*\n\n"
            " *WARNING: This action is irreversible!*\n\n"
            "Enter the Program ID to delete:",
            parse_mode="Markdown"
        )

    @bot.message_handler(func=lambda m: admin_sessions.get(m.from_user.id, {}).get("stage") == "awaiting_program_id_delete")
    def confirm_delete_program(message):
        user_id = message.from_user.id

        try:
            program_id = int(message.text.strip())

            programs = get_all_programs()
            program = next((p for p in programs if p['id'] == program_id), None)

            if not program:
                bot.send_message(
                    message.chat.id,
                    f" Program with ID `{program_id}` not found.",
                    parse_mode="Markdown"
                )
                admin_sessions.pop(user_id, None)
                return

            admin_sessions[user_id]["program_id"] = program_id
            admin_sessions[user_id]["stage"] = "confirming_delete"

            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton(" Yes, Delete", callback_data="admin:confirm_delete"))
            kb.add(InlineKeyboardButton(" Cancel", callback_data="admin:cancel_delete"))

            bot.send_message(
                message.chat.id,
                (
                    f" *Confirm Deletion*\n\n"
                    f"Program: {program['name']}\n"
                    f"Level: {program['level']}\n"
                    f"College: {program['college']}\n\n"
                    f"Are you sure you want to delete this program?\n"
                    f"All courses, resources, and transactions will be removed."
                ),
                parse_mode="Markdown",
                reply_markup=kb
            )

        except ValueError:
            bot.send_message(
                message.chat.id,
                " Invalid program ID. Please enter a number.",
                parse_mode="Markdown"
            )
        except Exception as e:
            bot.send_message(
                message.chat.id,
                f" Error: {str(e)}",
                parse_mode="Markdown"
            )
            admin_sessions.pop(user_id, None)

    @bot.callback_query_handler(func=lambda call: call.data == "admin:confirm_delete")
    def execute_delete_program(call):
        user_id = call.from_user.id
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return

        session = admin_sessions.get(user_id, {})
        program_id = session.get("program_id")

        try:
            delete_program(program_id)

            bot.send_message(
                call.message.chat.id,
                f" *Program Deleted*\n\n"
                f"Program ID {program_id} has been permanently deleted.",
                parse_mode="Markdown"
            )
            admin_sessions.pop(user_id, None)

        except Exception as e:
            bot.send_message(
                call.message.chat.id,
                f" Error: {str(e)}",
                parse_mode="Markdown"
            )

    @bot.callback_query_handler(func=lambda call: call.data == "admin:cancel_delete")
    def cancel_delete_program(call):
        user_id = call.from_user.id
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return

        admin_sessions.pop(user_id, None)

        bot.send_message(
            call.message.chat.id,
            " Deletion cancelled.",
            parse_mode="Markdown"
        )

    # -------------------------
    # LIST ALL USERS
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin:list_users"))
    def list_users(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return

        try:
            users = get_all_users()

            total = len(users)
            if not total:
                bot.send_message(
                    call.message.chat.id,
                    " *Users*\n\nNo users found.",
                    parse_mode="Markdown"
                )
                return

            page_items, page, total_pages = paginate_items(call.data, users, 10)

            text = f" *All Users* (Page {page + 1}/{total_pages})\n\n"
            text += f"Total Users: {total}\n\n"

            for u in page_items:
                first_name = str(u.get('first_name', 'N/A')).replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
                username = str(u.get('username', 'N/A')).replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')

                text += (
                    f"ID: {u['id']} | TG: {u['telegram_id']}\n"
                    f"Name: {first_name} | @{username}\n"
                    f"──────────────────\n"
                )

            kb = InlineKeyboardMarkup()
            nav_buttons = []
            if page > 0:
                nav_buttons.append(InlineKeyboardButton(" Prev", callback_data=f"admin:list_users:{page - 1}"))
            if page + 1 < total_pages:
                nav_buttons.append(InlineKeyboardButton(" Next", callback_data=f"admin:list_users:{page + 1}"))
            if nav_buttons:
                kb.add(*nav_buttons)
            kb.add(InlineKeyboardButton(" Refresh", callback_data="admin:list_users:0"))

            bot.send_message(
                call.message.chat.id,
                text,
                parse_mode="Markdown",
                reply_markup=kb
            )

        except Exception as e:
            bot.send_message(
                call.message.chat.id,
                f" Error: {str(e)}",
                parse_mode="Markdown"
            )

    # -------------------------
    # LIST ALL ADMIN MESSAGES
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin:list_messages"))
    def list_admin_messages(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return

        try:
            messages = get_all_admin_messages(limit=200)

            if not messages:
                bot.send_message(
                    call.message.chat.id,
                    " *User Messages*\n\n"
                    "No messages found.",
                    parse_mode="Markdown"
                )
                return

            unhandled_count = sum(1 for m in messages if not m['handled'])

            page_items, page, total_pages = paginate_items(call.data, messages, 5)

            text = f" *User Messages* (Page {page + 1}/{total_pages})\n\n"
            text += f"Total: {total} |  Unhandled: {unhandled_count}\n\n"

            for msg in page_items:
                status = " NEW" if not msg['handled'] else " Handled"

                username = escape_markdown(msg.get('username'))
                telegram_id = msg.get('telegram_id', 'N/A')
                user_info = f"@{username}" if msg.get('username') else f"ID: {telegram_id}"

                date = str(msg.get('created_at', 'N/A'))[:10]

                message_text = escape_markdown(msg.get('message_text', ''))
                message_preview = message_text[:60]
                if len(message_text) > 60:
                    message_preview += "\\.\\.\\."

                text += (
                    f"{status} | {user_info}\n"
                    f" {message_preview}\n"
                    f" {date}\n"
                    f"──────────────────\n"
                )

            kb = InlineKeyboardMarkup()
            nav_buttons = []
            if page > 0:
                nav_buttons.append(InlineKeyboardButton(" Prev", callback_data=f"admin:list_messages:{page - 1}"))
            if page + 1 < total_pages:
                nav_buttons.append(InlineKeyboardButton(" Next", callback_data=f"admin:list_messages:{page + 1}"))
            if nav_buttons:
                kb.add(*nav_buttons)
            kb.add(InlineKeyboardButton(" Refresh", callback_data="admin:list_messages:0"))

            bot.send_message(
                call.message.chat.id,
                text,
                parse_mode="Markdown",
                reply_markup=kb
            )

        except Exception as e:
            bot.send_message(
                call.message.chat.id,
                f" Error: {str(e)}",
                parse_mode="Markdown"
            )

    # -------------------------
    # BROADCAST MESSAGE — FIXED
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "admin:broadcast")
    def broadcast_handler(call):
        user_id = call.from_user.id
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return

        admin_sessions[user_id] = {"stage": "awaiting_broadcast_message"}

        bot.send_message(
            call.message.chat.id,
            " *Broadcast Message*\n\n"
            "Enter the message to broadcast to all users:\n\n"
            "(Use Markdown formatting: *bold*, _italic_, `code`)",
            parse_mode="Markdown"
        )

    @bot.message_handler(func=lambda m: admin_sessions.get(m.from_user.id, {}).get("stage") == "awaiting_broadcast_message")
    def receive_broadcast_message(message):
        user_id = message.from_user.id
        broadcast_text = message.text

        try:
            users = get_all_users()

            if not users:
                bot.send_message(
                    message.chat.id,
                    " No users to broadcast to.",
                    parse_mode="Markdown"
                )
                admin_sessions.pop(user_id, None)
                return

            admin_sessions[user_id]["broadcast_text"] = broadcast_text
            admin_sessions[user_id]["stage"] = "confirming_broadcast"

            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton(" Send", callback_data="admin:confirm_broadcast"))
            kb.add(InlineKeyboardButton(" Cancel", callback_data="admin:cancel_broadcast"))

            bot.send_message(
                message.chat.id,
                (
                    f" *Confirm Broadcast*\n\n"
                    f"Message:\n\n{broadcast_text}\n\n"
                    f"This will be sent to {len(users)} users."
                ),
                parse_mode="Markdown",
                reply_markup=kb
            )

        except Exception as e:
            bot.send_message(
                message.chat.id,
                f" Error: {str(e)}",
                parse_mode="Markdown"
            )
            admin_sessions.pop(user_id, None)

    @bot.callback_query_handler(func=lambda call: call.data == "admin:confirm_broadcast")
    def execute_broadcast(call):
        user_id = call.from_user.id
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return

        session = admin_sessions.get(user_id, {})
        broadcast_text = session.get("broadcast_text")

        # Clear session immediately so admin isn't locked out
        admin_sessions.pop(user_id, None)

        def do_broadcast():
            """Run broadcast in a background thread to avoid blocking the polling loop."""
            try:
                users = get_all_users()
                sent_count = 0
                failed_count = 0
                total_users = len(users)

                bot.send_message(
                    call.message.chat.id,
                    f" *Broadcasting to {total_users} users\\.\\.\\.*\n\n"
                    f"This may take a while\\. You will be notified when done\\.",
                    parse_mode="MarkdownV2"
                )

                for user in users:
                    success = send_with_retry(
                        bot,
                        user['telegram_id'],
                        f" *Announcement from Admin*\n\n{broadcast_text}"
                    )
                    if success:
                        sent_count += 1
                    else:
                        failed_count += 1

                    # 50ms delay between each send — stays within Telegram's 30 msg/sec limit
                    time.sleep(0.05)

                bot.send_message(
                    call.message.chat.id,
                    (
                        f" *Broadcast Complete*\n\n"
                        f"Successfully sent: {sent_count}\n"
                        f"Failed: {failed_count}"
                    ),
                    parse_mode="Markdown"
                )

            except Exception as e:
                bot.send_message(
                    call.message.chat.id,
                    f" Broadcast error: {str(e)}",
                    parse_mode="Markdown"
                )

        # Launch in a daemon thread so it doesn't block bot polling
        threading.Thread(target=do_broadcast, daemon=True).start()

    @bot.callback_query_handler(func=lambda call: call.data == "admin:cancel_broadcast")
    def cancel_broadcast(call):
        user_id = call.from_user.id
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return

        admin_sessions.pop(user_id, None)

        bot.send_message(
            call.message.chat.id,
            " Broadcast cancelled.",
            parse_mode="Markdown"
        )

    # -------------------------
    # STOP BOT
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "admin:stop_bot")
    def stop_bot_handler(call):
        user_id = call.from_user.id
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return

        admin_sessions[user_id] = {"stage": "confirming_stop"}

        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton(" Yes, Stop Bot", callback_data="admin:confirm_stop"))
        kb.add(InlineKeyboardButton(" Cancel", callback_data="admin:cancel_stop"))

        bot.send_message(
            call.message.chat.id,
            (
                " *Stop Bot*\n\n"
                " *WARNING: This will stop the bot for all users!*\n\n"
                "Are you sure you want to proceed?"
            ),
            parse_mode="Markdown",
            reply_markup=kb
        )

    @bot.callback_query_handler(func=lambda call: call.data == "admin:confirm_stop")
    def execute_stop_bot(call):
        user_id = call.from_user.id
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return

        try:
            bot.send_message(
                call.message.chat.id,
                (
                    " *Bot Stopping*\n\n"
                    "The bot is now shutting down..."
                ),
                parse_mode="Markdown"
            )
            admin_sessions.pop(user_id, None)
            bot.stop_polling()

        except Exception as e:
            bot.send_message(
                call.message.chat.id,
                f" Error: {str(e)}",
                parse_mode="Markdown"
            )

    @bot.callback_query_handler(func=lambda call: call.data == "admin:cancel_stop")
    def cancel_stop_bot(call):
        user_id = call.from_user.id
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return

        admin_sessions.pop(user_id, None)

        bot.send_message(
            call.message.chat.id,
            " Bot stop cancelled.",
            parse_mode="Markdown"
        )
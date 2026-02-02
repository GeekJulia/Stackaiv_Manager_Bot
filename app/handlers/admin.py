import os
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

admin_sessions = {}

# Replace with your actual admin Telegram ID
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

def admin_handler(bot):
    """
    Admin handler for special admin functions.
    Command: /admin7105
    """

    @bot.message_handler(commands=['admin7105'])
    def admin_command(message):
        user_id = message.from_user.id
        
        # Security check - only allow admin
        if user_id != ADMIN_ID:
            bot.send_message(
                message.chat.id,
                "❌ *Unauthorized Access*\n\n"
                "This command is restricted to administrators only.",
                parse_mode="Markdown"
            )
            return
        
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("📊 Transactions", callback_data="admin:list_transactions"),
            InlineKeyboardButton("🔍 Fetch Transaction", callback_data="admin:fetch_transaction")
        )
        kb.add(
            InlineKeyboardButton("🏫 All Programs", callback_data="admin:list_programs"),
            InlineKeyboardButton("🗑️ Delete Program", callback_data="admin:delete_program")
        )
        kb.add(
            InlineKeyboardButton("💬 User Messages", callback_data="admin:list_messages"),
            InlineKeyboardButton("📢 Broadcast", callback_data="admin:broadcast")
        )
        kb.add(
            InlineKeyboardButton("👥 List Users", callback_data="admin:list_users"),
            InlineKeyboardButton("🛑 Stop Bot", callback_data="admin:stop_bot")
        )
        
        bot.send_message(
            message.chat.id,
            (
                "👨‍💼 *Admin Control Panel*\n\n"
                "Welcome back, Administrator.\n"
                "Select an action below:"
            ),
            parse_mode="Markdown",
            reply_markup=kb
        )

    # -------------------------
    # LIST ALL TRANSACTIONS
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "admin:list_transactions")
    def list_transactions(call):
        try:
            transactions = get_all_transactions()
            
            if not transactions:
                bot.send_message(
                    call.message.chat.id,
                    "📊 *Transactions*\n\n"
                    "No transactions found.",
                    parse_mode="Markdown"
                )
                return
            
            # Send in chunks to avoid message too long error
            text = "📊 *Recent Transactions*\n\n"
            
            for t in transactions[-100:]:  # Show last 100 transactions
                status = "✅ Success" if t['status'] == 'success' else "⏳ Pending"
                # Format amount properly (amount is in kobo, divide by 100 to get naira)
                amount_naira = int(t['amount'] / 100) if isinstance(t['amount'], (int, float)) else 0
                date = str(t.get('created_at', 'N/A'))[:10]  # Just the date portion
                
                entry = (
                    f"*ID:* {t['id']} | *Status:* {status}\n"
                    f"*Amount:* ₦{amount_naira:,} | *Program:* {t['program_id']}\n"
                    f"*Date:* {date}\n"
                    f"──────────────────\n"
                )
                
                # Send in chunks to avoid 4096 char limit
                if len(text) + len(entry) > 3500:
                    bot.send_message(
                        call.message.chat.id,
                        text,
                        parse_mode="Markdown"
                    )
                    text = ""
                
                text += entry
            
            if text:
                bot.send_message(
                    call.message.chat.id,
                    text,
                    parse_mode="Markdown"
                )
        
        except Exception as e:
            bot.send_message(
                call.message.chat.id,
                f"❌ Error: {str(e)}",
                parse_mode="Markdown"
            )

    # -------------------------
    # FETCH TRANSACTION BY ID
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "admin:fetch_transaction")
    def fetch_transaction_handler(call):
        user_id = call.from_user.id
        admin_sessions[user_id] = {"stage": "awaiting_transaction_id"}
        
        bot.send_message(
            call.message.chat.id,
            "🔍 *Fetch Transaction*\n\n"
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
                # Format amount properly (amount is in kobo)
                amount_naira = int(transaction['amount'] / 100) if isinstance(transaction['amount'], (int, float)) else 0
                text = (
                    f"💳 *Transaction Details*\n\n"
                    f"ID: `{transaction['id']}`\n"
                    f"Reference: `{transaction['reference']}`\n"
                    f"Amount: ₦{amount_naira:,}\n"
                    f"Status: {transaction['status'].upper()}\n"
                    f"Program: {transaction['program_name']}\n"
                    f"User: {transaction['user_name']}\n"
                    f"Date: {transaction['created_at']}"
                )
            else:
                text = f"❌ Transaction with ID `{transaction_id}` not found."
            
            bot.send_message(
                message.chat.id,
                text,
                parse_mode="Markdown"
            )
            admin_sessions.pop(user_id, None)
        
        except ValueError:
            bot.send_message(
                message.chat.id,
                "❌ Invalid transaction ID. Please enter a number.",
                parse_mode="Markdown"
            )
        except Exception as e:
            bot.send_message(
                message.chat.id,
                f"❌ Error: {str(e)}",
                parse_mode="Markdown"
            )
            admin_sessions.pop(user_id, None)

    # -------------------------
    # LIST ALL PROGRAMS
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "admin:list_programs")
    def list_programs(call):
        try:
            programs = get_all_programs()
            
            if not programs:
                bot.send_message(
                    call.message.chat.id,
                    "🏫 *Programs*\n\n"
                    "No programs found.",
                    parse_mode="Markdown"
                )
                return
            
            # Send in chunks due to message size limits
            text = "🏫 *All Programs*\n\n"
            
            for p in programs:
                status = "✅ Active" if p['is_active'] else "⏳ Inactive"
                text += (
                    f"ID: `{p['id']}`\n"
                    f"Name: {p['name']}\n"
                    f"Level: {p['level']} | College: {p['college']}\n"
                    f"Creator: {p['creator_name']} (@{p['creator_username']})\n"
                    f"Status: {status}\n"
                    f"─" * 40 + "\n"
                )
                
                # Send in chunks to avoid message size limit
                if len(text) > 3500:
                    bot.send_message(
                        call.message.chat.id,
                        text,
                        parse_mode="Markdown"
                    )
                    text = ""
            
            if text:
                bot.send_message(
                    call.message.chat.id,
                    text,
                    parse_mode="Markdown"
                )
        
        except Exception as e:
            bot.send_message(
                call.message.chat.id,
                f"❌ Error: {str(e)}",
                parse_mode="Markdown"
            )

    # -------------------------
    # DELETE PROGRAM
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "admin:delete_program")
    def delete_program_handler(call):
        user_id = call.from_user.id
        admin_sessions[user_id] = {"stage": "awaiting_program_id_delete"}
        
        bot.send_message(
            call.message.chat.id,
            "🗑️ *Delete Program*\n\n"
            "⚠️ *WARNING: This action is irreversible!*\n\n"
            "Enter the Program ID to delete:",
            parse_mode="Markdown"
        )

    @bot.message_handler(func=lambda m: admin_sessions.get(m.from_user.id, {}).get("stage") == "awaiting_program_id_delete")
    def confirm_delete_program(message):
        user_id = message.from_user.id
        
        try:
            program_id = int(message.text.strip())
            
            # Get program info for confirmation
            programs = get_all_programs()
            program = next((p for p in programs if p['id'] == program_id), None)
            
            if not program:
                bot.send_message(
                    message.chat.id,
                    f"❌ Program with ID `{program_id}` not found.",
                    parse_mode="Markdown"
                )
                admin_sessions.pop(user_id, None)
                return
            
            # Store for confirmation step
            admin_sessions[user_id]["program_id"] = program_id
            admin_sessions[user_id]["stage"] = "confirming_delete"
            
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("✅ Yes, Delete", callback_data="admin:confirm_delete"))
            kb.add(InlineKeyboardButton("❌ Cancel", callback_data="admin:cancel_delete"))
            
            bot.send_message(
                message.chat.id,
                (
                    f"⚠️ *Confirm Deletion*\n\n"
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
                "❌ Invalid program ID. Please enter a number.",
                parse_mode="Markdown"
            )
        except Exception as e:
            bot.send_message(
                message.chat.id,
                f"❌ Error: {str(e)}",
                parse_mode="Markdown"
            )
            admin_sessions.pop(user_id, None)

    @bot.callback_query_handler(func=lambda call: call.data == "admin:confirm_delete")
    def execute_delete_program(call):
        user_id = call.from_user.id
        session = admin_sessions.get(user_id, {})
        program_id = session.get("program_id")
        
        try:
            delete_program(program_id)
            
            bot.send_message(
                call.message.chat.id,
                f"✅ *Program Deleted*\n\n"
                f"Program ID {program_id} has been permanently deleted.",
                parse_mode="Markdown"
            )
            admin_sessions.pop(user_id, None)
        
        except Exception as e:
            bot.send_message(
                call.message.chat.id,
                f"❌ Error: {str(e)}",
                parse_mode="Markdown"
            )

    @bot.callback_query_handler(func=lambda call: call.data == "admin:cancel_delete")
    def cancel_delete_program(call):
        user_id = call.from_user.id
        admin_sessions.pop(user_id, None)
        
        bot.send_message(
            call.message.chat.id,
            "❌ Deletion cancelled.",
            parse_mode="Markdown"
        )

    # -------------------------
    # LIST ALL USERS
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "admin:list_users")
    def list_users(call):
        try:
            users = get_all_users()
            
            if not users:
                bot.send_message(
                    call.message.chat.id,
                    "👥 *Users*\n\n"
                    "No users found.",
                    parse_mode="Markdown"
                )
                return
            
            text = "👥 *All Users*\n\n"
            text += f"Total Users: {len(users)}\n\n"
            
            for u in users[-100:]:  # Show last 100 users
                text += (
                    f"ID: {u['id']} | Telegram: {u['telegram_id']}\n"
                    f"Name: {u['first_name']} | Username: @{u['username']}\n"
                    f"─" * 40 + "\n"
                )
                
                if len(text) > 3500:
                    bot.send_message(
                        call.message.chat.id,
                        text,
                        parse_mode="Markdown"
                    )
                    text = ""
            
            if text:
                bot.send_message(
                    call.message.chat.id,
                    text,
                    parse_mode="Markdown"
                )
        
        except Exception as e:
            bot.send_message(
                call.message.chat.id,
                f"❌ Error: {str(e)}",
                parse_mode="Markdown"
            )

    # -------------------------
    # LIST ALL ADMIN MESSAGES
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "admin:list_messages")
    def list_admin_messages(call):
        try:
            messages = get_all_admin_messages(limit=200)
            
            if not messages:
                bot.send_message(
                    call.message.chat.id,
                    "💬 *User Messages*\n\n"
                    "No messages found.",
                    parse_mode="Markdown"
                )
                return
            
            # Count unhandled messages
            unhandled_count = sum(1 for m in messages if not m['handled'])
            
            text = f"💬 *User Messages*\n\n"
            text += f"Total Messages: {len(messages)}\n"
            text += f"⚠️ Unhandled: {unhandled_count}\n\n"
            
            for msg in messages:
                status = "🔴 NEW" if not msg['handled'] else "✅ Handled"
                user_info = f"@{msg['username']}" if msg['username'] else f"ID: {msg['telegram_id']}"
                date = str(msg.get('created_at', 'N/A'))[:10]
                
                # Truncate message if too long
                message_preview = msg['message_text'][:100]
                if len(msg['message_text']) > 100:
                    message_preview += "..."
                
                entry = (
                    f"{status} | {user_info}\n"
                    f"📝 {message_preview}\n"
                    f"🕐 {date}\n"
                    f"──────────────────\n"
                )
                
                # Send in chunks to avoid 4096 char limit
                if len(text) + len(entry) > 3500:
                    bot.send_message(
                        call.message.chat.id,
                        text,
                        parse_mode="Markdown"
                    )
                    text = ""
                
                text += entry
            
            if text:
                bot.send_message(
                    call.message.chat.id,
                    text,
                    parse_mode="Markdown"
                )
        
        except Exception as e:
            bot.send_message(
                call.message.chat.id,
                f"❌ Error: {str(e)}",
                parse_mode="Markdown"
            )

    # -------------------------
    # BROADCAST MESSAGE
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "admin:broadcast")
    def broadcast_handler(call):
        user_id = call.from_user.id
        admin_sessions[user_id] = {"stage": "awaiting_broadcast_message"}
        
        bot.send_message(
            call.message.chat.id,
            "📢 *Broadcast Message*\n\n"
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
                    "❌ No users to broadcast to.",
                    parse_mode="Markdown"
                )
                admin_sessions.pop(user_id, None)
                return
            
            admin_sessions[user_id]["broadcast_text"] = broadcast_text
            admin_sessions[user_id]["stage"] = "confirming_broadcast"
            
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("✅ Send", callback_data="admin:confirm_broadcast"))
            kb.add(InlineKeyboardButton("❌ Cancel", callback_data="admin:cancel_broadcast"))
            
            bot.send_message(
                message.chat.id,
                (
                    f"📢 *Confirm Broadcast*\n\n"
                    f"Message:\n\n{broadcast_text}\n\n"
                    f"This will be sent to {len(users)} users."
                ),
                parse_mode="Markdown",
                reply_markup=kb
            )
        
        except Exception as e:
            bot.send_message(
                message.chat.id,
                f"❌ Error: {str(e)}",
                parse_mode="Markdown"
            )
            admin_sessions.pop(user_id, None)

    @bot.callback_query_handler(func=lambda call: call.data == "admin:confirm_broadcast")
    def execute_broadcast(call):
        user_id = call.from_user.id
        session = admin_sessions.get(user_id, {})
        broadcast_text = session.get("broadcast_text")
        
        try:
            users = get_all_users()
            sent_count = 0
            failed_count = 0
            
            bot.send_message(
                call.message.chat.id,
                f"📢 *Broadcasting to {len(users)} users...*",
                parse_mode="Markdown"
            )
            
            for user in users:
                try:
                    bot.send_message(
                        user['telegram_id'],
                        f"📢 *Announcement from Admin*\n\n{broadcast_text}",
                        parse_mode="Markdown"
                    )
                    sent_count += 1
                except:
                    failed_count += 1
            
            bot.send_message(
                call.message.chat.id,
                (
                    f"✅ *Broadcast Complete*\n\n"
                    f"Successfully sent: {sent_count}\n"
                    f"Failed: {failed_count}"
                ),
                parse_mode="Markdown"
            )
            admin_sessions.pop(user_id, None)
        
        except Exception as e:
            bot.send_message(
                call.message.chat.id,
                f"❌ Error: {str(e)}",
                parse_mode="Markdown"
            )

    @bot.callback_query_handler(func=lambda call: call.data == "admin:cancel_broadcast")
    def cancel_broadcast(call):
        user_id = call.from_user.id
        admin_sessions.pop(user_id, None)
        
        bot.send_message(
            call.message.chat.id,
            "❌ Broadcast cancelled.",
            parse_mode="Markdown"
        )

    # -------------------------
    # STOP BOT
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "admin:stop_bot")
    def stop_bot_handler(call):
        user_id = call.from_user.id
        admin_sessions[user_id] = {"stage": "confirming_stop"}
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("✅ Yes, Stop Bot", callback_data="admin:confirm_stop"))
        kb.add(InlineKeyboardButton("❌ Cancel", callback_data="admin:cancel_stop"))
        
        bot.send_message(
            call.message.chat.id,
            (
                "🛑 *Stop Bot*\n\n"
                "⚠️ *WARNING: This will stop the bot for all users!*\n\n"
                "Are you sure you want to proceed?"
            ),
            parse_mode="Markdown",
            reply_markup=kb
        )

    @bot.callback_query_handler(func=lambda call: call.data == "admin:confirm_stop")
    def execute_stop_bot(call):
        user_id = call.from_user.id
        
        try:
            bot.send_message(
                call.message.chat.id,
                (
                    "🛑 *Bot Stopping*\n\n"
                    "The bot is now shutting down..."
                ),
                parse_mode="Markdown"
            )
            admin_sessions.pop(user_id, None)
            bot.stop_polling()
        
        except Exception as e:
            bot.send_message(
                call.message.chat.id,
                f"❌ Error: {str(e)}",
                parse_mode="Markdown"
            )

    @bot.callback_query_handler(func=lambda call: call.data == "admin:cancel_stop")
    def cancel_stop_bot(call):
        user_id = call.from_user.id
        admin_sessions.pop(user_id, None)
        
        bot.send_message(
            call.message.chat.id,
            "❌ Bot stop cancelled.",
            parse_mode="Markdown"
        )

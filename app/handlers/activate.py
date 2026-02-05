from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from ..database.queries import (
    get_user_program_id,
    get_group_program_id,
    get_program_info,
    get_program_activation_status,
    get_courses_by_program
)
from ..services.payments import initialize_transaction, generate_payment_reference

activation_sessions = {}

def resolve_program_from_chat(call_or_message):
        chat_id = call_or_message.chat.id
        program_id = get_group_program_id(chat_id)

        if not program_id:
            raise Exception(
                "No program is linked to this group.\n"
                "An admin must register and link a program first."
            )
        return program_id

def activation_handler(bot):
    """
    Handles program activation flow.
    Called after program registration but before course setup.
    """

    # -------------------------
    # Show Activation Payment Screen
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "action:activate_program")
    def show_activation_screen(call):
        # user_id = call.from_user.id
        message_id = call.message.message_id
        program_id = resolve_program_from_chat(call.message)
        
        try:
            program_id = get_group_program_id(program_id)
            program_info = get_program_info(program_id)
            
            # Check if already active
            is_active = get_program_activation_status(program_id)
            if is_active:
                # Get existing courses
                courses = get_courses_by_program(program_id)
                
                if courses:
                    courses_list = "\n".join([f"• {c['course_code']}" for c in courses])
                    message_text = (
                        "✅ *Your program space is activated!*\n\n"
                        f"📚 *Registered Courses:*\n{courses_list}\n\n"
                        "You can now proceed to add resources or access the resource hub."
                    )
                else:
                    message_text = (
                        "✅ *Your program space is activated!*\n\n"
                        "📚 *No courses added yet.*\n\n"
                        "You can proceed to add courses and start sharing/accessing resources."
                    )
                
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton("➕ Add Courses", callback_data="notes:add_courses"))
                kb.add(InlineKeyboardButton("📚 Resource Hub", callback_data="action:goto_space"))
                kb.add(InlineKeyboardButton("⬅️ Back", callback_data="action:activate_program"))
                
                try:
                    bot.edit_message_text(
                        message_text,
                        call.message.chat.id,
                        message_id,
                        parse_mode="Markdown",
                        reply_markup=kb
                    )
                except:
                    bot.send_message(
                        call.message.chat.id,
                        message_text,
                        parse_mode="Markdown",
                        reply_markup=kb
                    )
                return
            
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("💳 Proceed with Payment", callback_data="activate:pay"))
            kb.add(InlineKeyboardButton("❌ Cancel Registration", callback_data="activate:cancel"))
            
            message_text = (
                "🎓 *Activate Your Program Space*\n\n"
                f"📘 Program: *{program_info['program_name']}*\n"
                f"📊 Level: *{program_info['level']}*\n"
                f"🏫 College: *{program_info['college']}*\n\n"
                "💰 *Activation Fee:* ₦3,000.00\n\n"
                "This fee activates your resource sharing space, allowing you and your classmates "
                "to upload and access course materials.\n\n"
                "Would you like to proceed with the payment?"
            )
            
            try:
                bot.edit_message_text(
                    message_text,
                    call.message.chat.id,
                    message_id,
                    parse_mode="Markdown",
                    reply_markup=kb
                )
            except:
                bot.send_message(
                    call.message.chat.id,
                    message_text,
                    parse_mode="Markdown",
                    reply_markup=kb
                )
            
        except Exception as e:
            bot.send_message(
                call.message.chat.id,
                f"❌ Error: {str(e)}",
                parse_mode="Markdown"
            )

    # -------------------------
    # Initiate Payment - Ask for Email
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "activate:pay")
    def ask_for_email(call):
        user_id = call.from_user.id
        
        try:
            program_id = resolve_program_from_chat(call.message)
            
            # Store in session - awaiting email
            activation_sessions[user_id] = {
                "program_id": program_id,
                "stage": "awaiting_email"
            }
            
            # Ask for email
            bot.send_message(
                call.message.chat.id,
                "📧 *Please provide your email address*\n\n"
                "We need a valid email address to process your payment through Paystack.\n\n"
                "Example: `john@gmail.com` or `jane@yahoo.com`",
                parse_mode="Markdown"
            )
            
        except Exception as e:
            bot.send_message(
                call.message.chat.id,
                f"❌ Error: {str(e)}",
                parse_mode="Markdown"
            )

    # -------------------------
    # Process Email and Initiate Payment
    # -------------------------
    @bot.message_handler(func=lambda m: activation_sessions.get(m.from_user.id, {}).get("stage") == "awaiting_email")
    def process_email_and_pay(message):
        user_id = message.from_user.id
        user_email = message.text.strip()
        
        try:
            # Basic email validation
            if "@" not in user_email or "." not in user_email:
                bot.send_message(
                    message.chat.id,
                    "❌ *Invalid email format*\n\n"
                    "Please provide a valid email address (e.g., user@example.com)",
                    parse_mode="Markdown"
                )
                return
            
            session = activation_sessions.get(user_id, {})
            program_id = session.get("program_id")
            
            # Generate unique payment reference
            payment_ref = generate_payment_reference(user_id, program_id)
            
            # Update session with payment ref
            activation_sessions[user_id] = {
                "program_id": program_id,
                "payment_ref": payment_ref,
                "email": user_email,
                "stage": "initiating_payment"
            }
            
            # Show processing message
            bot.send_message(
                message.chat.id,
                "🔄 *Processing payment...*",
                parse_mode="Markdown"
            )
            
            # Initialize Paystack transaction
            result = initialize_transaction(
                program_id=program_id,
                email=user_email,
                reference=payment_ref
            )
            
            if result.get("status"):
                auth_url = result["authorization_url"]
                
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton("💳 Pay Now", url=auth_url))
                kb.add(InlineKeyboardButton("✅ Payment Complete?", callback_data="activate:check_status"))
                kb.add(InlineKeyboardButton("❌ Cancel", callback_data="activate:cancel"))
                
                bot.send_message(
                    message.chat.id,
                    (
                        "💳 *Ready to Complete Payment*\n\n"
                        "Click the button below to proceed to Paystack's secure checkout page.\n\n"
                        "You'll be redirected to pay ₦3,000 via:\n"
                        "• 💳 Card (Visa, Mastercard)\n"
                        "• 🏦 Bank Transfer\n"
                        "• 📱 USSD\n\n"
                        "After successful payment, click *'Payment Complete?'* to verify your payment."
                    ),
                    parse_mode="Markdown",
                    reply_markup=kb
                )
            else:
                error_msg = result.get('error', 'Unknown error')
                bot.send_message(
                    message.chat.id,
                    f"❌ *Payment Initialization Failed*\n\n{error_msg}",
                    parse_mode="Markdown"
                )
                activation_sessions.pop(user_id, None)
        
        except Exception as e:
            bot.send_message(
                message.chat.id,
                f"❌ Error: {str(e)}",
                parse_mode="Markdown"
            )
            activation_sessions.pop(user_id, None)

    # -------------------------
    # Cancel Activation
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "activate:cancel")
    def cancel_activation(call):
        user_id = call.from_user.id
        activation_sessions.pop(user_id, None)
        
        bot.send_message(
            call.message.chat.id,
            "❌ *Registration Cancelled*\n\n"
            "Your program registration has been cancelled. "
            "You can start over anytime with /start",
            parse_mode="Markdown"
        )

    # -------------------------
    # Check Payment Status
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "activate:check_status")
    def check_payment_status(call):
        user_id = call.from_user.id
        message_id = call.message.message_id
        
        try:
            # Show processing message
            loading_msg = bot.send_message(
                call.message.chat.id,
                "⏳ *Verifying payment...*",
                parse_mode="Markdown"
            )
            
            program_id = resolve_program_from_chat(call.message)
            is_active = get_program_activation_status(program_id)
            
            if is_active:
                # Program is activated!
                activation_sessions.pop(user_id, None)
                
                # Get existing courses
                courses = get_courses_by_program(program_id)
                
                if courses:
                    courses_list = "\n".join([f"• {c['course_code']}" for c in courses])
                    message_text = (
                        "✅ *Payment Verified!*\n\n"
                        "🎉 Your program space is now activated!\n\n"
                        f"🆔 *Program ID:* `{program_id}`\n\n"
                        f"📚 *Registered Courses:*\n{courses_list}\n\n"
                        "You can now proceed to add resources or access the resource hub."
                    )
                else:
                    message_text = (
                        "✅ *Payment Verified!*\n\n"
                        "🎉 Your program space is now activated!\n\n"
                        f"🆔 *Program ID:* `{program_id}`\n\n"
                        "📚 *No courses added yet.*\n\n"
                        "You can now proceed to add courses and start sharing/accessing resources."
                    )
                
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton("➕ Add Courses", callback_data="notes:add_courses"))
                kb.add(InlineKeyboardButton("📚 Resource Hub", callback_data="action:goto_space"))
                
                # Delete loading message
                try:
                    bot.delete_message(call.message.chat.id, loading_msg.message_id)
                except:
                    pass
                
                try:
                    bot.edit_message_text(
                        message_text,
                        call.message.chat.id,
                        message_id,
                        parse_mode="Markdown",
                        reply_markup=kb
                    )
                except:
                    bot.send_message(
                        call.message.chat.id,
                        message_text,
                        parse_mode="Markdown",
                        reply_markup=kb
                    )
            else:
                # Payment still processing
                try:
                    bot.edit_message_text(
                        "⏳ *Payment Still Processing*\n\n"
                        "Your payment is being verified by Paystack. "
                        "This usually takes a few seconds to a few minutes.\n\n"
                        "Please wait a moment and try again.",
                        call.message.chat.id,
                        loading_msg.message_id,
                        parse_mode="Markdown"
                    )
                except:
                    pass
        
        except Exception as e:
            bot.send_message(
                call.message.chat.id,
                f"❌ Error: {str(e)}",
                parse_mode="Markdown"
            )

    # -------------------------
    # Payment Verification Command
    # -------------------------
    @bot.message_handler(commands=['verify_payment'])
    def verify_payment_command(message):
        """
        Manual verification command.
        Usage: /verify_payment <reference>
        """
        user_id = message.from_user.id
        
        try:
            args = message.text.split()
            if len(args) < 2:
                bot.send_message(
                    message.chat.id,
                    "⚠️ Usage: `/verify_payment <reference>`",
                    parse_mode="Markdown"
                )
                return
            
            reference = args[1]
            
            bot.send_message(
                message.chat.id,
                "🔄 *Verifying payment...*",
                parse_mode="Markdown"
            )
            
            # Verification is typically done via webhook, but this allows manual check
            program_id = resolve_program_from_chat(message)
            is_active = get_program_activation_status(program_id)
            
            if is_active:
                bot.send_message(
                    message.chat.id,
                    "✅ *Payment Verified!*\n\n"
                    "Your program is now activated. You can proceed to add courses.",
                    parse_mode="Markdown"
                )
            else:
                bot.send_message(
                    message.chat.id,
                    "⏳ *Payment Still Processing*\n\n"
                    "Your payment is being verified. Please wait a moment and try again.",
                    parse_mode="Markdown"
                )
        
        except Exception as e:
            bot.send_message(
                message.chat.id,
                f"❌ Error: {str(e)}",
                parse_mode="Markdown"
            )

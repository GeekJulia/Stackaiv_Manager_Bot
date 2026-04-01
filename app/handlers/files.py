from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import threading
import re
from ..utils.messages import safe_edit_or_send, send_loading_message, escape_markdown, safe_edit_or_send as edit_message_safe
from ..utils.keyboards import build_course_keyboard, build_resource_type_keyboard
from ..database.queries import (
    get_user_program_id,
    get_courses_by_program,
    get_resource_types,
    save_resource,
    get_resources_by_course_and_type,
    get_course_info,
    check_duplicate_resource_by_type,
    save_resource_with_type_check,
    save_admin_message,
)

from ..utils.db_operations import safe_db_operation, DatabaseTimeoutError
from ..utils.sessions import TTLDict, get_active_program_id

file_sessions = TTLDict()

# Batch upload handling for files.py (per user)
file_batch_queues = TTLDict(cleanup_interval_seconds=600)  # Shorter cleanup for file queues
file_batch_timers = TTLDict(cleanup_interval_seconds=600)  
file_batch_messages = TTLDict(cleanup_interval_seconds=600)


def files_handler(bot):

    # -------------------------
    # HELP
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "hub:help")
    def help_info(call):
        message_id = call.message.message_id
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📧 Contact Admin", callback_data="hub:contact_admin"))
        kb.add(InlineKeyboardButton("⬅️ Back", callback_data="action:goto_space"))
        
        help_text = (
            "ℹ️ *Help Guide*\n\n"
            "📚 *All Courses* — View courses in your program\n"
            "➕ *Add Resource* — Upload notes, slides, PDFs, etc\n"
            "📥 *Get Resource* — Download resources shared by others\n\n"
            "Resources are organized by *course* and *type*.\n\n"
            "*Format:*\n"
            "• Send courses: `MAT 111, CSC 111` (comma-separated)\n"
            "• Request slots: `Slot 1, Slot 2` (comma-separated)\n\n"
            "For serious issues, contact the admin."
        )
        safe_edit_or_send(
            bot,
            call.message.chat.id,
            message_id,
            help_text,
            parse_mode="Markdown",
            reply_markup=kb
        )
    
    # -------------------------
    # CONTACT ADMIN
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "hub:contact_admin")
    def contact_admin(call):
        message_id = call.message.message_id
        file_sessions[call.from_user.id] = {
            "stage": "composing_admin_message"
        }
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("⬅️ Cancel", callback_data="hub:help"))
        
        try:
            bot.edit_message_text(
                (
                    "📧 *Contact Administrator*\n\n"
                    "Please describe your issue or concern:\n\n"
                    "_Your message will be forwarded to the admin team._"
                ),
                call.message.chat.id,
                message_id,
                parse_mode="Markdown",
                reply_markup=kb
            )
        except:
            bot.send_message(
                call.message.chat.id,
                (
                    "📧 *Contact Administrator*\n\n"
                    "Please describe your issue or concern:"
                ),
                parse_mode="Markdown",
                reply_markup=kb
            )
    
    # -------------------------
    # RECEIVE ADMIN MESSAGE
    # -------------------------
    @bot.message_handler(func=lambda m: file_sessions.get(m.from_user.id, {}).get("stage") == "composing_admin_message")
    def receive_admin_message(message):
        user_id = message.from_user.id
        user_message = message.text.strip()

        # Persist message so admin can see it in the panel
        try:
            save_admin_message(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                message_text=user_message,
                message_type="general",
            )
        except Exception as e:
            # Don't break user flow if saving fails
            print(f"ERROR saving admin message: {e}")

        bot.send_message(
            message.chat.id,
            "✅ *Message Received*\n\n"
            "Thank you for contacting us! The admin team will review your message shortly.\n\n"
            "We'll get back to you as soon as possible.",
            parse_mode="Markdown"
        )
        
        file_sessions.pop(user_id, None)
    
    #CANCEL OPERATION
    @bot.message_handler(func=lambda m: m.text and m.text.lower() == "cancel")
    def cancel_operation(message):
        user_id = message.from_user.id

        if user_id in file_sessions:
            file_sessions.pop(user_id)

            bot.send_message(
                message.chat.id,
                "❌ Operation cancelled.\nYou're back in your resource hub."
            )

    # -------------------------
    # ALL COURSES (TEXT LIST) - ✅ FIXED
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "hub:courses")
    def all_courses(call):
        # Send loading message
        loading_msg_id = send_loading_message(
            bot,
            call.message.chat.id,
            "⏳ *Loading your courses...*"
        )
        
        try:
            # ✅ USE NEW HELPER FUNCTION
            program_id = get_active_program_id(call.from_user.id)
            courses = []
            if program_id:
                courses = safe_db_operation(get_courses_by_program, [], program_id)

            text = "📚 *Registered Courses*\n\n"
            if courses:
                for c in courses:
                    text += f"• {c['course_code']}\n"
            else:
                text += "No courses registered yet."

            edit_message_safe(
                bot,
                call.message.chat.id,
                loading_msg_id,
                text,
                parse_mode="Markdown"
            )
            
        except DatabaseTimeoutError:
            edit_message_safe(
                bot,
                call.message.chat.id,
                loading_msg_id,
                "⏰ *System is busy*\n\nPlease try again in a moment.",
                parse_mode="Markdown"
            )
        except Exception as e:
            edit_message_safe(
                bot,
                call.message.chat.id,
                loading_msg_id,
                f"❌ Error: {str(e)}",
                parse_mode="Markdown"
            )

    # -------------------------
    # ADD RESOURCE → SELECT COURSE - ✅ FIXED
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "hub:add")
    def add_resource_courses(call):
        # Send loading message
        loading_msg_id = send_loading_message(
            bot,
            call.message.chat.id,
            "⏳ *Loading available courses...*"
        )
        
        try:
            # ✅ USE NEW HELPER FUNCTION
            program_id = get_active_program_id(call.from_user.id)
            courses = []
            if program_id:
                courses = safe_db_operation(get_courses_by_program, [], program_id)
            
            if not courses:
                edit_message_safe(
                    bot,
                    call.message.chat.id,
                    loading_msg_id,
                    "📚 *No Courses Found*\n\nYou need to add courses first before uploading resources.",
                    parse_mode="Markdown"
                )
                return

            kb = build_course_keyboard(courses, callback_prefix="add:course")

            # Edit loading message with course selection
            edit_message_safe(
                bot,
                call.message.chat.id,
                loading_msg_id,
                "📘 *Select a course:*",
                parse_mode="Markdown",
                reply_markup=kb,
            )
            
        except DatabaseTimeoutError:
            edit_message_safe(
                bot,
                call.message.chat.id,
                loading_msg_id,
                "⏰ *System is busy*\n\nPlease try again in a moment.",
                parse_mode="Markdown"
            )
        except Exception as e:
            edit_message_safe(
                bot,
                call.message.chat.id,
                loading_msg_id,
                f"❌ Error: {str(e)}",
                parse_mode="Markdown"
            )

    # -------------------------
    # ADD RESOURCE → SELECT TYPE
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data.startswith("add:course:"))
    def add_resource_type(call):
        course_id = int(call.data.split(":")[2])
        resource_types = get_resource_types()

        file_sessions[call.from_user.id] = {
            "stage": "awaiting_file",
            "course_id": course_id
        }

        course = get_course_info(course_id)

        kb = build_resource_type_keyboard(resource_types, callback_prefix="add:type")

        # Replace the course selection message with resource type selection
        safe_edit_or_send(
            bot,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"📂 *Select resource type for {course['course_code']}:*",
            parse_mode="Markdown",
            reply_markup=kb,
        )

    # -------------------------
    # ADD RESOURCE → WAIT FOR FILE
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data.startswith("add:type:"))
    def await_file(call):
        user_id = call.from_user.id
        res_type_id = int(call.data.split(":")[2])

        # Ensure we have an active session for this user
        session = file_sessions.get(user_id)
        if not session or session.get("stage") != "awaiting_file":
            # This can happen if:
            # - The user clicked an old inline button from before a restart
            # - Their session was cleared (e.g. cancel, timeout, restart)
            # Fail gracefully instead of raising KeyError
            bot.answer_callback_query(
                call.id,
                "Your upload session has expired. Please tap 'Add Resource' again.",
                show_alert=True,
            )
            return

        session["resource_type_id"] = res_type_id

        # Replace the resource type selection message with the "send file" prompt
        safe_edit_or_send(
            bot,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="📎 Send the file or documents now (PDF, DOCX, etc).",
            parse_mode="Markdown",
        )

    # -------------------------
    # RECEIVE FILE & SAVE (PRIVATE CHAT ONLY!) - BATCHED
    # -------------------------
    @bot.message_handler(content_types=['document'], func=lambda m: m.chat.type == 'private')
    def receive_file(message):
        user_id = message.from_user.id
        session = file_sessions.get(user_id)
        
        # Must have active session from course/type selection
        if not session or session.get("stage") != "awaiting_file":
            return

        doc = message.document
        course_id = session["course_id"]
        resource_type_id = session["resource_type_id"]
        file_name = doc.file_name
        
        print(f"File queued for batch: {file_name} (user: {user_id})")
        
        # Add to batch queue
        if user_id not in file_batch_queues:
            file_batch_queues[user_id] = []
        
        file_batch_queues[user_id].append({
            "file_id": doc.file_id,
            "file_name": file_name,
            "course_id": course_id,
            "resource_type_id": resource_type_id,
            "uploader_id": user_id
        })
        
        # Cancel existing timer if present
        if user_id in file_batch_timers:
            file_batch_timers[user_id].cancel()
        
        # Set new timer to process batch after 2 seconds
        def process_batch_callback():
            display_file_batch_prompt(user_id, message.chat.id, bot)
        
        timer = threading.Timer(2.0, process_batch_callback)
        file_batch_timers[user_id] = timer
        timer.start()
        
        print(f"File batch queue for user {user_id}: {len(file_batch_queues[user_id])} files")

    # -------------------------
    # Display File Batch Prompt
    # -------------------------
    def display_file_batch_prompt(user_id, chat_id, bot):
        """Show batch prompt for all queued files"""
        if user_id not in file_batch_queues or not file_batch_queues[user_id]:
            return
        
        queue = file_batch_queues[user_id]
        
        # Build file list text - use plain Markdown (not V2) for simplicity
        file_list = "📎 *Files queued for upload:*\n\n"
        for i, f in enumerate(queue, 1):
            course = get_course_info(f['course_id'])
            # Don't use backticks for filenames with special chars in Markdown
            # Just show them plain to avoid parsing issues
            file_list += f"{i}. {f['file_name']}\n   → {course['course_code']}\n"
        
        file_list += f"\n✅ *{len(queue)} file(s) ready*\n\n"
        file_list += "Review files above. Confirm to upload all."
        
        # Build keyboard
        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton("✅ Upload All", callback_data="fbatch:process"),
            InlineKeyboardButton("❌ Cancel", callback_data="fbatch:cancel")
        )
        
        # Send batch prompt with regular Markdown and error handling
        try:
            msg = bot.send_message(
                chat_id,
                file_list,
                parse_mode="Markdown",
                reply_markup=kb
            )
            
            # Store message_id for this batch
            file_batch_messages[user_id] = msg.message_id
            
            # Initialize batch session (shared for all files in this batch)
            session_key = f"fbatch:{user_id}"
            file_sessions[session_key] = {
                "stage": "batch_processing",
                "user_id": user_id,
                "file_count": len(queue)
            }
        except Exception as e:
            print(f"ERROR sending batch prompt: {e}")
            # Fallback: send without Markdown
            try:
                msg = bot.send_message(
                    chat_id,
                    file_list.replace("*", ""),
                    reply_markup=kb
                )
                
                file_batch_messages[user_id] = msg.message_id
                session_key = f"fbatch:{user_id}"
                file_sessions[session_key] = {
                    "stage": "batch_processing",
                    "user_id": user_id,
                    "file_count": len(queue)
                }
            except Exception as e2:
                print(f"ERROR sending batch prompt (fallback): {e2}")

    # -------------------------
    # GET RESOURCE → SELECT COURSE - ✅ FIXED
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "hub:get")
    def get_resource_course(call):
        # Send loading message
        loading_msg_id = send_loading_message(
            bot,
            call.message.chat.id,
            "⏳ *Loading available courses...*"
        )
        
        try:
            # ✅ USE NEW HELPER FUNCTION
            program_id = get_active_program_id(call.from_user.id)
            courses = []
            if program_id:
                courses = safe_db_operation(get_courses_by_program, [], program_id)

            if not courses:
                edit_message_safe(
                    bot,
                    call.message.chat.id,
                    loading_msg_id,
                    "📚 *No Courses Found*\n\nYou need to add courses first before downloading resources.",
                    parse_mode="Markdown"
                )
                return

            kb = build_course_keyboard(courses, callback_prefix="get:course")

            # Edit loading message with course selection
            edit_message_safe(
                bot,
                call.message.chat.id,
                loading_msg_id,
                "📘 *Select a course:*",
                parse_mode="Markdown",
                reply_markup=kb,
            )
            
        except DatabaseTimeoutError:
            edit_message_safe(
                bot,
                call.message.chat.id,
                loading_msg_id,
                "⏰ *System is busy*\n\nPlease try again in a moment.",
                parse_mode="Markdown"
            )
        except Exception as e:
            edit_message_safe(
                bot,
                call.message.chat.id,
                loading_msg_id,
                f"❌ Error: {str(e)}",
                parse_mode="Markdown"
            )

    # -------------------------
    # GET RESOURCE → TYPE
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data.startswith("get:course:"))
    def get_resource_type(call):
        course_id = int(call.data.split(":")[2])
        resource_types = get_resource_types()

        file_sessions[call.from_user.id] = {
            "stage": "select_slot",
            "course_id": course_id
        }

        course = get_course_info(course_id)

        kb = build_resource_type_keyboard(resource_types, callback_prefix="get:type")

        # Replace the course selection message with resource type selection
        safe_edit_or_send(
            bot,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"📂 *Select resource type for {course['course_code']}:*",
            parse_mode="Markdown",
            reply_markup=kb,
        )

    # -------------------------
    # GET RESOURCE → SLOT SYSTEM
    # -------------------------
# In files.py, modify the list_slots function:

    @bot.callback_query_handler(func=lambda call: call.data.startswith("get:type:"))
    def list_slots(call):
        user_id = call.from_user.id
        res_type_id = int(call.data.split(":")[2])
        session = file_sessions.get(user_id)

        if not session or session.get("stage") != "select_slot":
            bot.answer_callback_query(
                call.id,
                "Your session has expired. Please use 'Get Resource' again.",
                show_alert=True,
            )
            return

        resources = get_resources_by_course_and_type(
            session["course_id"], res_type_id
        )

        # Build text exactly like groups.py does
        text = "📁 *Available Resources*\n\n"
        
        if resources:
            for i, r in enumerate(resources, start=1):
                # Use backticks for filenames like groups.py does
                text += f"{i}. `{r['file_name']}`\n"
        else:
            text += "No resources available.\n"
        
        text += (
            "\n\n📥 *How to download:*\n"
            "• Send: `Slot 1`\n"
            "• Send: `Slot 1, Slot 2, Slot 3` (comma-separated)\n"
            "• Send: `All` for everything"
        )

        session["resources"] = resources

        # Try with Markdown first - this should work since we use backticks
        try:
            safe_edit_or_send(
                bot,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=text,
                parse_mode="Markdown",
            )
        except Exception as e:
            print(f"ERROR sending slot list (Markdown failed): {e}")
            # Fallback to plain text
            plain_text = "📁 Available Resources\n\n"
            for i, r in enumerate(resources, start=1):
                plain_text += f"{i}. {r['file_name']}\n"
            
            plain_text += (
                "\n\n📥 How to download:\n"
                "• Send: Slot 1\n"
                "• Send: Slot 1, Slot 2, Slot 3 (comma-separated)\n"
                "• Send: All (for everything)"
            )
            
            safe_edit_or_send(
                bot,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=plain_text,
            )

    # -------------------------
    # SEND SLOT NUMBER
    # -------------------------
    @bot.message_handler(func=lambda m: m.text and ( m.text.lower() == "all" or m.text.lower().startswith("slot")))
    def send_resource(message):
        user_id = message.from_user.id
        session = file_sessions.get(user_id)

        if not session or "resources" not in session:
            return

        text = message.text.lower().strip()
        resources = session["resources"]

        # -------------------------
        # ALL
        # -------------------------
        if text == "all":
            # Show loading indicator
            loading_msg = bot.send_message(
                message.chat.id,
                "⏳ *Downloading all resources...*",
                parse_mode="Markdown"
            )
            
            for r in resources:
                bot.send_document(message.chat.id, r["file_id"])

            try:
                bot.delete_message(message.chat.id, loading_msg.message_id)
            except:
                pass

            file_sessions.pop(user_id, None)
            return

        # -------------------------
        # MULTI-SLOT (Slot 1, Slot 2 or Slot 1 | Slot 2)
        # -------------------------
        try:
            # Support both comma and pipe separators
            separator = "," if "," in text else "|"
            slots = [
                int(part.strip().replace("slot", "").strip()) - 1
                for part in text.split(separator)
            ]
        except ValueError:
            bot.send_message(
                message.chat.id,
                "❌ *Invalid format*\n\n"
                "Use comma-separated format:\n"
                "• `Slot 1`\n"
                "• `Slot 1, Slot 2, Slot 3`\n"
                "• `All`",
                parse_mode="Markdown"
            )
            return

        sent_any = False
        for idx in slots:
            if 0 <= idx < len(resources):
                bot.send_document(
                    message.chat.id,
                    resources[idx]["file_id"]
                )
                sent_any = True

        if not sent_any:
            bot.send_message(
                message.chat.id,
                "❌ No valid slot numbers found.",
                parse_mode="Markdown"
            )
            return

        # Cleanup
        file_sessions.pop(user_id, None)
    
    # -------------------------
    # File Batch: Process All
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "fbatch:process")
    def fbatch_process_all(call):
        user_id = call.from_user.id
        
        queue = file_batch_queues.get(user_id, [])
        if not queue:
            bot.answer_callback_query(call.id, "Queue is empty", show_alert=True)
            return
        
        # Send processing message
        processing_msg_id = send_loading_message(
            bot,
            call.message.chat.id,
            f"⏳ *Processing {len(queue)} file(s)...*"
        )
        
        # Process all files
        success_count = 0
        duplicate_count = 0
        error_count = 0
        
        for file_data in queue:
            try:
                is_duplicate = safe_db_operation(
                    check_duplicate_resource_by_type,
                    False,
                    file_data['course_id'],
                    file_data['resource_type_id'],
                    file_data['file_name']
                )
                
                if is_duplicate:
                    duplicate_count += 1
                    continue
                
                resource_id = safe_db_operation(
                    save_resource_with_type_check,
                    None,
                    course_id=file_data['course_id'],
                    resource_type_id=file_data['resource_type_id'],
                    file_id=file_data['file_id'],
                    file_name=file_data['file_name'],
                    uploader_id=user_id
                )
                
                if resource_id:
                    success_count += 1
                else:
                    error_count += 1
            except DatabaseTimeoutError:
                error_count += 1
            except Exception as e:
                print(f"Error processing file {file_data['file_name']}: {e}")
                error_count += 1
        
        # Show result
        result_msg = f"✅ *Batch Upload Complete*\n\n"
        result_msg += f"✔️ {success_count} file(s) uploaded\n"
        if duplicate_count > 0:
            result_msg += f"⏭️ {duplicate_count} file(s) skipped (duplicates)\n"
        if error_count > 0:
            result_msg += f"❌ {error_count} file(s) failed\n"
        result_msg += "\nYour resources are now available for your program community."
        
        edit_message_safe(
            bot,
            call.message.chat.id,
            processing_msg_id,
            result_msg,
            parse_mode="Markdown"
        )
        
        # Clean up
        file_batch_queues.pop(user_id, None)
        file_batch_messages.pop(user_id, None)
        file_sessions.pop(f"fbatch:{user_id}", None)
        file_sessions.pop(user_id, None)
    
    # -------------------------
    # File Batch: Cancel
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "fbatch:cancel")
    def fbatch_cancel(call):
        user_id = call.from_user.id
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="❌ *Batch upload cancelled*",
            parse_mode="Markdown"
        )
        
        # Clean up
        file_batch_queues.pop(user_id, None)
        file_batch_messages.pop(user_id, None)
        file_sessions.pop(f"fbatch:{user_id}", None)
        file_sessions.pop(user_id, None)
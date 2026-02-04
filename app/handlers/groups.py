import re
import threading
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from ..database.queries import (
    get_program_by_id,
    save_group,
    get_group_program_id,
    get_courses_by_program,
    get_resource_types,
    save_resource,
    check_duplicate_resource,
    save_approval
)

group_sessions = {}
# Sessions are keyed by f"{chat_id}_{message_id}" to support concurrent uploads

# Batch upload handling
batch_queues = {}  # {chat_id: [file_dict1, file_dict2, ...]}
batch_timers = {}  # {chat_id: threading.Timer}
batch_messages = {}  # {chat_id: message_id} - stores the batch prompt message_id

def groups_handler(bot):
    
    # -------------------------
    # Bot Added to Group - FIXED
    # -------------------------
    @bot.message_handler(content_types=['new_chat_members'])
    def welcome_to_group(message):
        # Check if bot was added
        for member in message.new_chat_members:
            if member.id == bot.get_me().id:
                kb = InlineKeyboardMarkup()
                kb.add(
                    InlineKeyboardButton(
                        "🔧 Setup Group",
                        callback_data="group:setup"
                    )
                )
                
                bot.send_message(
                    message.chat.id,
                    (
                        "👋 *Hello everyone!*\n\n"
                        "I'm your academic resource management bot.\n\n"
                        "I help you:\n"
                        "• 📁 Organize course materials\n"
                        "• 📚 Track shared resources\n"
                        "• ✅ Prevent duplicate uploads\n\n"
                        "Click below to set up this group."
                    ),
                    parse_mode="Markdown",
                    reply_markup=kb
                )
                break  # Only process once if bot is added
    
    # -------------------------
    # Setup Group Command - FIXED
    # -------------------------
    @bot.message_handler(commands=['setupgroup'])
    def setup_group_command(message):
        # Only work in groups
        if message.chat.type not in ['group', 'supergroup']:
            bot.send_message(
                message.chat.id,
                "❌ *This command is only for group chats!*\n\n"
                "Please add me to your group chat and use this command there.",
                parse_mode="Markdown"
            )
            return
        
        # In group - show setup button
        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton(
                "🔧 Setup Group",
                callback_data="group:setup"
            )
        )
        
        bot.send_message(
            message.chat.id,
            "Click the button below to begin setup:",
            reply_markup=kb
        )
    
    # -------------------------
    # Setup Group - Request Program ID
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "group:setup")
    def request_program_id(call):
        if call.message.chat.type not in ['group', 'supergroup']:
            bot.answer_callback_query(
                call.id,
                "This feature is only for groups!",
                show_alert=True
            )
            return
        
        group_sessions[call.message.chat.id] = {
            "stage": "awaiting_program_id",
            "setup_by": call.from_user.id
        }
        
        bot.send_message(
            call.message.chat.id,
            (
                "🎓 *Group Setup*\n\n"
                "Please send your *Program ID*.\n\n"
                "💡 Get your Program ID by sending /whoami to me in private chat."
            ),
            parse_mode="Markdown"
        )
    
    # -------------------------
    # Receive Program ID
    # -------------------------
    @bot.message_handler(func=lambda m: m.chat.type in ['group', 'supergroup'] and 
                         group_sessions.get(m.chat.id, {}).get("stage") == "awaiting_program_id")
    def receive_program_id(message):
        chat_id = message.chat.id
        
        try:
            program_id = int(message.text.strip())
        except ValueError:
            bot.send_message(
                chat_id,
                "❌ Invalid Program ID. Please send a valid number.",
                parse_mode="Markdown"
            )
            return
        
        try:
            # Verify program exists
            program = get_program_by_id(program_id)
            
            if not program:
                bot.send_message(
                    chat_id,
                    "❌ Program ID not found. Please check and try again.",
                    parse_mode="Markdown"
                )
                # Clear session on error
                group_sessions.pop(chat_id, None)
                return
            
            # Save group with program
            group_id = save_group(chat_id, program_id)
            
            if group_id:
                bot.send_message(
                    chat_id,
                    (
                        "✅ *Group Setup Complete!*\n\n"
                        f"📚 Program: *{program['name']}*\n"
                        f"🎓 Level: *{program['level']}*\n"
                        f"🏫 College: *{program['college']}*\n\n"
                        "You can now share files and I'll track them automatically!\n\n"
                        "📎 Just upload files with course codes in the filename "
                        "(e.g., `MAT111_notes.pdf` or `CSC 234 slides.pptx`)"
                    ),
                    parse_mode="Markdown"
                )
            else:
                bot.send_message(
                    chat_id,
                    "❌ Failed to save group configuration. Please try again.",
                    parse_mode="Markdown"
                )
            
            # Clean up session
            group_sessions.pop(chat_id, None)
            
        except Exception as e:
            print(f"ERROR in receive_program_id: {e}")
            bot.send_message(
                chat_id,
                "❌ An error occurred during setup. Please try again with /setupgroup",
                parse_mode="Markdown"
            )
            # Clear session on error
            group_sessions.pop(chat_id, None)
    
    # -------------------------
    # Extract Course Code from Filename
    # -------------------------
    def extract_course_code(filename):
        """
        Extract course code from filename.
        Patterns: XXX 111 or XXX111 (3 letters + 3 numbers)
        Returns: (course_code, confidence)
        """
        # Pattern with space: MAT 111
        pattern_space = r'\b([A-Z]{3})\s+(\d{3})\b'
        # Pattern without space: MAT111
        pattern_no_space = r'\b([A-Z]{3})(\d{3})\b'
        
        filename_upper = filename.upper()
        
        # Try with space first
        match = re.search(pattern_space, filename_upper)
        if match:
            return f"{match.group(1)} {match.group(2)}", "high"
        
        # Try without space
        match = re.search(pattern_no_space, filename_upper)
        if match:
            return f"{match.group(1)} {match.group(2)}", "medium"
        
        return None, "none"
    
    def normalize_course_code(code):
        """Normalize course code for comparison (remove spaces)"""
        return code.replace(" ", "").upper()
    
    def courses_match(code1, code2):
        """Check if two course codes match (ignoring spacing)"""
        return normalize_course_code(code1) == normalize_course_code(code2)
    
    # -------------------------
    # Handle Document Upload in Group - BATCHED
    # -------------------------
    @bot.message_handler(content_types=['document'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def handle_group_document(message):
        chat_id = message.chat.id
        doc = message.document
        file_id = doc.file_id
        filename = doc.file_name or "untitled"
        
        print(f"Document queued: {filename} (chat: {chat_id})")
        
        program_id = get_group_program_id(chat_id)
        if not program_id:
            bot.send_message(
                chat_id,
                "❌ This group is not configured. An admin should run /setupgroup or press 'Setup Group'.",
                parse_mode="Markdown"
            )
            return
        
        courses = get_courses_by_program(program_id)
        if not courses:
            bot.send_message(
                chat_id,
                "⚠️ No courses are registered for this program yet. Please register courses in the program before uploading files.",
                parse_mode="Markdown"
            )
            return
        
        # Extract course code
        course_code, confidence = extract_course_code(filename)
        
        # Add to batch queue
        if chat_id not in batch_queues:
            batch_queues[chat_id] = []
        
        batch_queues[chat_id].append({
            "file_id": file_id,
            "file_name": filename,
            "uploader_id": message.from_user.id,
            "course_code": course_code,
            "program_id": program_id
        })
        
        # Cancel existing timer if present
        if chat_id in batch_timers:
            batch_timers[chat_id].cancel()
        
        # Set new timer to process batch after 2 seconds
        def process_batch_callback():
            display_batch_prompt(chat_id, bot)
        
        timer = threading.Timer(2.0, process_batch_callback)
        batch_timers[chat_id] = timer
        timer.start()
        
        print(f"Batch queue for chat {chat_id}: {len(batch_queues[chat_id])} files")
    
    # -------------------------
    # Confirm Detected Course - Yes
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data.startswith("gconf:yes:"))
    def confirm_course_yes(call):
        chat_id = call.message.chat.id
        parts = call.data.split(":")
        course_id = int(parts[2])
        
        session_key = f"{chat_id}_{call.message.message_id}"
        session = group_sessions.get(session_key)
        if not session:
            bot.answer_callback_query(call.id, "Session expired", show_alert=True)
            return
        
        # Proceed to resource type selection
        show_resource_types(chat_id, course_id, call.message.message_id, session_key)
    
    # -------------------------
    # Confirm Detected Course - No (manual selection)
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data.startswith("gconf:no"))
    def confirm_course_no(call):
        chat_id = call.message.chat.id
        session_key = f"{chat_id}_{call.message.message_id}"
        
        session = group_sessions.get(session_key)
        if not session:
            bot.answer_callback_query(call.id, "Session expired", show_alert=True)
            return
        
        program_id = get_group_program_id(chat_id)
        
        if not program_id:
            return
        
        courses = get_courses_by_program(program_id)
        
        kb = InlineKeyboardMarkup()
        for c in courses:
            kb.add(
                InlineKeyboardButton(
                    c['course_code'],
                    callback_data=f"gcourse:{c['id']}"
                )
            )
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="📚 *Select the course for this file:*",
            parse_mode="Markdown",
            reply_markup=kb
        )
    
    # -------------------------
    # Course Selected Manually
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data.startswith("gcourse:"))
    def select_course_manual(call):
        chat_id = call.message.chat.id
        parts = call.data.split(":")
        course_id = int(parts[1])
        
        session_key = f"{chat_id}_{call.message.message_id}"
        session = group_sessions.get(session_key)
        if not session:
            bot.answer_callback_query(call.id, "Session expired", show_alert=True)
            return
        
        session["course_id"] = course_id
        
        # Proceed to resource type selection
        show_resource_types(chat_id, course_id, call.message.message_id, session_key)
    
    # -------------------------
    # Show Resource Types
    # -------------------------
    def show_resource_types(chat_id, course_id, message_id, session_key):
        session = group_sessions.get(session_key)
        if not session:
            return
        
        resource_types = get_resource_types()
        
        kb = InlineKeyboardMarkup()
        for r in resource_types:
            kb.add(
                InlineKeyboardButton(
                    r['name'],
                    callback_data=f"gtype:{r['id']}"
                )
            )
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="📂 *What resource type should this be added to?*",
            parse_mode="Markdown",
            reply_markup=kb
        )
    
    # -------------------------
    # Display Batch Upload Prompt
    # -------------------------
    def display_batch_prompt(chat_id, bot):
        """Show batch prompt for all queued files"""
        if chat_id not in batch_queues or not batch_queues[chat_id]:
            return
        
        queue = batch_queues[chat_id]
        courses = get_courses_by_program(queue[0]['program_id'])
        
        # Build file list text
        file_list = "📎 *Files queued for upload:*\n\n"
        for i, f in enumerate(queue, 1):
            detected = f['course_code'] if f['course_code'] else "❓ No course detected"
            file_list += f"{i}. `{f['file_name']}`\n   → {detected}\n"
        
        file_list += f"\n✅ *{len(queue)} file(s) ready*\n\n"
        file_list += "📚 *Select course & resource type for all files:*"
        
        # Build keyboard with courses and resource types
        kb = InlineKeyboardMarkup()
        
        # Course selection row
        kb.add(InlineKeyboardButton("📚 Select Course", callback_data="batch:course"))
        
        # Resource type selection row
        kb.add(InlineKeyboardButton("📂 Select Type", callback_data="batch:type"))
        
        # Action buttons
        kb.add(
            InlineKeyboardButton("✅ Process All", callback_data="batch:process"),
            InlineKeyboardButton("❌ Cancel", callback_data="batch:cancel")
        )
        
        # Send batch prompt
        msg = bot.send_message(
            chat_id,
            file_list,
            parse_mode="Markdown",
            reply_markup=kb
        )
        
        # Store message_id for this batch
        batch_messages[chat_id] = msg.message_id
        
        # Initialize batch session (shared for all files in this batch)
        session_key = f"{chat_id}_{msg.message_id}"
        group_sessions[session_key] = {
            "stage": "batch_awaiting_course",
            "batch_id": chat_id,
            "file_count": len(queue),
            "course_id": None,
            "resource_type_id": None
        }
    
    # -------------------------
    # Batch: Select Course for All Files
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "batch:course")
    def batch_select_course(call):
        chat_id = call.message.chat.id
        session_key = f"{chat_id}_{call.message.message_id}"
        session = group_sessions.get(session_key)
        if not session:
            bot.answer_callback_query(call.id, "Session expired", show_alert=True)
            return
        
        program_id = batch_queues[chat_id][0]['program_id']
        courses = get_courses_by_program(program_id)
        
        kb = InlineKeyboardMarkup()
        for c in courses:
            kb.add(InlineKeyboardButton(c['course_code'], callback_data=f"batch_course:{c['id']}"))
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="📚 *Select the course for all files:*",
            parse_mode="Markdown",
            reply_markup=kb
        )
        session["stage"] = "batch_selecting_course"
    
    # -------------------------
    # Batch: Course Selected
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data.startswith("batch_course:"))
    def batch_course_selected(call):
        chat_id = call.message.chat.id
        course_id = int(call.data.split(":")[1])
        session_key = f"{chat_id}_{call.message.message_id}"
        session = group_sessions.get(session_key)
        if not session:
            bot.answer_callback_query(call.id, "Session expired", show_alert=True)
            return
        
        session["course_id"] = course_id
        
        # Show resource type selection
        resource_types = get_resource_types()
        kb = InlineKeyboardMarkup()
        for r in resource_types:
            kb.add(InlineKeyboardButton(r['name'], callback_data=f"batch_type:{r['id']}"))
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="📂 *Select the resource type for all files:*",
            parse_mode="Markdown",
            reply_markup=kb
        )
        session["stage"] = "batch_selecting_type"
    
    # -------------------------
    # Batch: Resource Type Selected
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data.startswith("batch_type:"))
    def batch_type_selected(call):
        chat_id = call.message.chat.id
        resource_type_id = int(call.data.split(":")[1])
        session_key = f"{chat_id}_{call.message.message_id}"
        session = group_sessions.get(session_key)
        if not session:
            bot.answer_callback_query(call.id, "Session expired", show_alert=True)
            return
        
        session["resource_type_id"] = resource_type_id
        
        # Go back to main batch prompt showing selections
        course_id = session.get("course_id")
        resource_type_id_val = session.get("resource_type_id")
        
        course = None
        resource_type = None
        
        if course_id:
            courses = get_courses_by_program(batch_queues[chat_id][0]['program_id'])
            for c in courses:
                if c['id'] == course_id:
                    course = c
                    break
        
        if resource_type_id_val:
            types = get_resource_types()
            for t in types:
                if t['id'] == resource_type_id_val:
                    resource_type = t
                    break
        
        queue = batch_queues[chat_id]
        file_list = f"📎 *{len(queue)} files ready to upload*\n\n"
        file_list += f"📚 **Course:** `{course['course_code'] if course else 'Not selected'}`\n"
        file_list += f"📂 **Type:** `{resource_type['name'] if resource_type else 'Not selected'}`\n\n"
        file_list += "Files:\n"
        for i, f in enumerate(queue, 1):
            file_list += f"  {i}. `{f['file_name']}`\n"
        
        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton("✅ Process All", callback_data="batch:process"),
            InlineKeyboardButton("↩️ Back", callback_data="batch:back")
        )
        kb.add(InlineKeyboardButton("❌ Cancel", callback_data="batch:cancel"))
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=file_list,
            parse_mode="Markdown",
            reply_markup=kb
        )
    
    # -------------------------
    # Batch: Back to Main Menu
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "batch:back")
    def batch_back(call):
        chat_id = call.message.chat.id
        session_key = f"{chat_id}_{call.message.message_id}"
        session = group_sessions.get(session_key)
        if not session:
            return
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📚 Select Course", callback_data="batch:course"))
        kb.add(InlineKeyboardButton("📂 Select Type", callback_data="batch:type"))
        kb.add(
            InlineKeyboardButton("✅ Process All", callback_data="batch:process"),
            InlineKeyboardButton("❌ Cancel", callback_data="batch:cancel")
        )
        
        queue = batch_queues[chat_id]
        file_list = "📎 *Files queued for upload:*\n\n"
        for i, f in enumerate(queue, 1):
            detected = f['course_code'] if f['course_code'] else "❓ No course detected"
            file_list += f"{i}. `{f['file_name']}`\n   → {detected}\n"
        
        file_list += f"\n✅ *{len(queue)} file(s) ready*\n\n"
        file_list += "📚 *Select course & resource type for all files:*"
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=file_list,
            parse_mode="Markdown",
            reply_markup=kb
        )
        session["stage"] = "batch_awaiting_course"
    
    # -------------------------
    # Batch: Process All Files
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "batch:process")
    def batch_process_all(call):
        chat_id = call.message.chat.id
        session_key = f"{chat_id}_{call.message.message_id}"
        session = group_sessions.get(session_key)
        if not session:
            bot.answer_callback_query(call.id, "Session expired", show_alert=True)
            return
        
        course_id = session.get("course_id")
        resource_type_id = session.get("resource_type_id")
        
        if not course_id or not resource_type_id:
            bot.answer_callback_query(
                call.id,
                "⚠️ Please select both course and resource type",
                show_alert=True
            )
            return
        
        queue = batch_queues.get(chat_id, [])
        if not queue:
            bot.answer_callback_query(call.id, "Queue is empty", show_alert=True)
            return
        
        # Process all files
        success_count = 0
        duplicate_count = 0
        
        for file_data in queue:
            is_duplicate = check_duplicate_resource(
                course_id,
                resource_type_id,
                file_data['file_name']
            )
            
            if is_duplicate:
                duplicate_count += 1
                continue
            
            resource_id = save_resource(
                course_id=course_id,
                resource_type_id=resource_type_id,
                file_id=file_data['file_id'],
                file_name=file_data['file_name'],
                uploader_id=file_data['uploader_id']
            )
            
            save_approval(resource_id, call.from_user.id)
            success_count += 1
        
        # Show result
        approver_username = call.from_user.username or call.from_user.first_name
        result_msg = f"✅ *Batch Upload Complete*\n\n"
        result_msg += f"✔️ {success_count} file(s) added\n"
        if duplicate_count > 0:
            result_msg += f"⏭️ {duplicate_count} file(s) skipped (already exist)\n"
        result_msg += f"\n👤 Approved by: @{approver_username}"
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=result_msg,
            parse_mode="Markdown"
        )
        
        # Clean up
        batch_queues.pop(chat_id, None)
        batch_messages.pop(chat_id, None)
        group_sessions.pop(session_key, None)
    
    # -------------------------
    # Batch: Cancel
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "batch:cancel")
    def batch_cancel(call):
        chat_id = call.message.chat.id
        session_key = f"{chat_id}_{call.message.message_id}"
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="❌ *Batch upload cancelled*"
        )
        
        # Clean up
        batch_queues.pop(chat_id, None)
        batch_messages.pop(chat_id, None)
        group_sessions.pop(session_key, None)
    
    # -------------------------
    # Resource Type Selected - Check Duplicate & Save
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data.startswith("gtype:"))
    def select_resource_type(call):
        chat_id = call.message.chat.id
        parts = call.data.split(":")
        resource_type_id = int(parts[1])
        
        session_key = f"{chat_id}_{call.message.message_id}"
        session = group_sessions.get(session_key)
        if not session:
            bot.answer_callback_query(call.id, "Session expired", show_alert=True)
            return
        
        course_id = session["course_id"]
        file_name = session["file_name"]
        file_id_session = session["file_id"]
        uploader_id = session["uploader_id"]
        
        # Check for duplicate
        is_duplicate = check_duplicate_resource(course_id, resource_type_id, file_name)
        
        if is_duplicate:
            bot.send_message(
                chat_id,
                "✅ *Already Added*",
                parse_mode="Markdown"
            )
        else:
            # Save resource
            resource_id = save_resource(
                course_id=course_id,
                resource_type_id=resource_type_id,
                file_id=file_id_session,
                file_name=file_name,
                uploader_id=uploader_id
            )
            
            # Save approval
            save_approval(resource_id, call.from_user.id)
            
            # Get approver username
            approver_username = call.from_user.username or call.from_user.first_name
            
            bot.send_message(
                chat_id,
                f"✅ *Added and Approved by* @{approver_username}",
                parse_mode="Markdown"
            )
        
        # Clean up session using the same key
        group_sessions.pop(session_key, None)
import re
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
# Track files being processed to prevent duplicate handling
processing_files = {}  # Format: {file_id: chat_id}

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
    # Handle Document Upload in Group
    # -------------------------
    @bot.message_handler(content_types=['document'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def handle_group_document(message):
        chat_id = message.chat.id
        doc = message.document
        file_id = doc.file_id
        
        # Check if this file is already being processed
        if file_id in processing_files:
            return  # Already processing this file
        
        # Mark file as being processed
        processing_files[file_id] = chat_id
        
        try:
            # DEBUG: Log everything
            print(f"Document received in chat: {chat_id}")
            print(f"Filename: {message.document.file_name}")
            print(f"Chat type: {message.chat.type}")
            
            program_id = get_group_program_id(chat_id)
            print(f"Program ID: {program_id}")
            
            if not program_id:
                bot.send_message(
                    chat_id,
                    "❌ This group is not configured. An admin should run /setupgroup or press 'Setup Group'.",
                    parse_mode="Markdown"
                )
                return  # Group not set up, inform users
            
            filename = doc.file_name or "untitled"
            
            # Extract course code
            course_code, confidence = extract_course_code(filename)
            
            # Get all courses for this program
            courses = get_courses_by_program(program_id)

            if not courses:
                bot.send_message(
                    chat_id,
                    "⚠️ No courses are registered for this program yet. Please register courses in the program before uploading files.",
                    parse_mode="Markdown"
                )
                return
            
            # Initialize/update session for this file
            # Use a unique key combining chat_id and file_id to handle multiple simultaneous uploads
            session_key = f"{chat_id}_{file_id}"
            group_sessions[session_key] = {
                "stage": "awaiting_resource_type",
                "file_id": file_id,
                "file_name": filename,
                "uploader_id": message.from_user.id,
                "message_id": message.message_id,
                "chat_id": chat_id
            }
            
            # -------------------------
            # Course Code Detected
            # -------------------------
            if course_code:
                # Check if detected course code is registered (match with or without space)
                matching_course = None
                for c in courses:
                    if courses_match(course_code, c['course_code']):
                        matching_course = c
                        break
                
                if matching_course:
                    course_id = matching_course['id']
                    registered_code = matching_course['course_code']
                    
                    group_sessions[session_key]["course_id"] = course_id
                    group_sessions[session_key]["course_code"] = registered_code
                    
                    kb = InlineKeyboardMarkup()
                    kb.add(
                        InlineKeyboardButton(
                            f"✅ Yes, {registered_code}",
                            callback_data=f"gconf:yes:{course_id}:{file_id}"
                        ),
                        InlineKeyboardButton(
                            "❌ No, choose manually",
                            callback_data=f"gconf:no:{file_id}"
                        )
                    )
                    
                    bot.send_message(
                        chat_id,
                        f"📎 Detected course code: *{registered_code}*\n\nIs this correct?",
                        parse_mode="Markdown",
                        reply_markup=kb
                    )
                else:
                    # Detected but not registered - show manual selection with warning
                    kb = InlineKeyboardMarkup()
                    for c in courses:
                        kb.add(
                            InlineKeyboardButton(
                                c['course_code'],
                                callback_data=f"gcourse:{c['id']}:{file_id}"
                            )
                        )
                    
                    bot.send_message(
                        chat_id,
                        (
                            f"⚠️ Detected *{course_code}* but it's not registered in your program.\n\n"
                            "📚 *Select from your registered courses:*"
                        ),
                        parse_mode="Markdown",
                        reply_markup=kb
                    )
            
            # -------------------------
            # No Detection - Ask to select course
            # -------------------------
            else:
                kb = InlineKeyboardMarkup()
                for c in courses:
                    kb.add(
                        InlineKeyboardButton(
                            c['course_code'],
                            callback_data=f"gcourse:{c['id']}:{file_id}"
                        )
                    )
                
                bot.send_message(
                    chat_id,
                    "📚 *Select the course for this file:*",
                    parse_mode="Markdown",
                    reply_markup=kb
                )
        
        finally:
            # Always clean up processing flag after handling
            processing_files.pop(file_id, None)
    
    # -------------------------
    # Confirm Detected Course - Yes
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data.startswith("gconf:yes:"))
    def confirm_course_yes(call):
        chat_id = call.message.chat.id
        parts = call.data.split(":")
        course_id = int(parts[2])
        file_id = parts[3] if len(parts) > 3 else None
        
        session_key = f"{chat_id}_{file_id}" if file_id else chat_id
        session = group_sessions.get(session_key)
        if not session:
            bot.answer_callback_query(call.id, "Session expired", show_alert=True)
            return
        
        # Proceed to resource type selection
        show_resource_types(call.message.chat.id, course_id, call.message.message_id, file_id)
    
    # -------------------------
    # Confirm Detected Course - No (manual selection)
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data.startswith("gconf:no:"))
    def confirm_course_no(call):
        chat_id = call.message.chat.id
        file_id = call.data.split(":")[2] if len(call.data.split(":")) > 2 else None
        program_id = get_group_program_id(chat_id)
        
        if not program_id:
            return
        
        courses = get_courses_by_program(program_id)
        
        kb = InlineKeyboardMarkup()
        for c in courses:
            kb.add(
                InlineKeyboardButton(
                    c['course_code'],
                    callback_data=f"gcourse:{c['id']}:{file_id}" if file_id else f"gcourse:{c['id']}"
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
        file_id = parts[2] if len(parts) > 2 else None
        
        session_key = f"{chat_id}_{file_id}" if file_id else chat_id
        session = group_sessions.get(session_key)
        if not session:
            bot.answer_callback_query(call.id, "Session expired", show_alert=True)
            return
        
        session["course_id"] = course_id
        
        # Proceed to resource type selection
        show_resource_types(chat_id, course_id, call.message.message_id, file_id)
    
    # -------------------------
    # Show Resource Types
    # -------------------------
    def show_resource_types(chat_id, course_id, message_id, file_id=None):
        resource_types = get_resource_types()
        
        kb = InlineKeyboardMarkup()
        for r in resource_types:
            callback = f"gtype:{r['id']}:{file_id}" if file_id else f"gtype:{r['id']}"
            kb.add(
                InlineKeyboardButton(
                    r['name'],
                    callback_data=callback
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
    # Resource Type Selected - Check Duplicate & Save
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data.startswith("gtype:"))
    def select_resource_type(call):
        chat_id = call.message.chat.id
        parts = call.data.split(":")
        resource_type_id = int(parts[1])
        file_id = parts[2] if len(parts) > 2 else None
        
        session_key = f"{chat_id}_{file_id}" if file_id else chat_id
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
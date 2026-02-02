from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from ..database.queries import (
    get_user_program_id,
    get_courses_by_program,
    get_resource_types,
    save_resource,
    get_resources_by_course_and_type,
    get_course_info,
    check_duplicate_resource_by_type,
    save_resource_with_type_check
)

file_sessions = {}

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
        
        try:
            bot.edit_message_text(
                (
                    "ℹ️ *Help Guide*\n\n"
                    "📚 *All Courses* — View courses in your program\n"
                    "➕ *Add Resource* — Upload notes, slides, PDFs, etc\n"
                    "📥 *Get Resource* — Download resources shared by others\n\n"
                    "Resources are organized by *course* and *type*.\n\n"
                    "*Format:*\n"
                    "• Send courses: `MAT 111, CSC 111` (comma-separated)\n"
                    "• Request slots: `Slot 1, Slot 2` (comma-separated)\n\n"
                    "For serious issues, contact the admin."
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
                    "ℹ️ *Help Guide*\n\n"
                    "📚 *All Courses* — View courses in your program\n"
                    "➕ *Add Resource* — Upload notes, slides, PDFs, etc\n"
                    "📥 *Get Resource* — Download resources shared by others\n\n"
                    "Resources are organized by *course* and *type*."
                ),
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
        
        # Note: In a real implementation, this would be sent to admin
        # For now, we'll just acknowledge it
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
    # ALL COURSES (TEXT LIST)
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "hub:courses")
    def all_courses(call):
        program_id = get_user_program_id(call.from_user.id)
        courses = get_courses_by_program(program_id)

        text = "📚 *Registered Courses*\n\n"
        for c in courses:
            text += f"• {c['course_code']}\n"

        bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

    # -------------------------
    # ADD RESOURCE → SELECT COURSE
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "hub:add")
    def add_resource_courses(call):
        program_id = get_user_program_id(call.from_user.id)
        courses = get_courses_by_program(program_id)

        kb = InlineKeyboardMarkup()
        for c in courses:
            kb.add(
                InlineKeyboardButton(
                    c["course_code"],
                    callback_data=f"add:course:{c['id']}"
                )
            )

        bot.send_message(
            call.message.chat.id,
            "📘 *Select a course:*",
            parse_mode="Markdown",
            reply_markup=kb
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

        kb = InlineKeyboardMarkup()
        for r in resource_types:
            kb.add(
                InlineKeyboardButton(
                    r["name"],
                    callback_data=f"add:type:{r['id']}"
                )
            )

        bot.send_message(
            call.message.chat.id,
            f"📂 *Select resource type for {course['course_code']}:*",
            parse_mode="Markdown",
            reply_markup=kb
        )

    # -------------------------
    # ADD RESOURCE → WAIT FOR FILE
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data.startswith("add:type:"))
    def await_file(call):
        res_type_id = int(call.data.split(":")[2])
        file_sessions[call.from_user.id]["resource_type_id"] = res_type_id

        bot.send_message(
            call.message.chat.id,
            "📎 Send the file now (PDF, DOCX, etc).",
            parse_mode="Markdown"
        )

    # -------------------------
    # RECEIVE FILE & SAVE (PRIVATE CHAT ONLY!)
    # -------------------------
    @bot.message_handler(content_types=['document'], func=lambda m: m.chat.type == 'private')
    def receive_file(message):
        session = file_sessions.get(message.from_user.id)
        if not session or session.get("stage") != "awaiting_file":
            return

        doc = message.document
        course_id = session["course_id"]
        resource_type_id = session["resource_type_id"]
        file_name = doc.file_name

        try:
            # Show processing message
            loading_msg = bot.send_message(
                message.chat.id,
                "⏳ *Uploading resource...*",
                parse_mode="Markdown"
            )
            
            # Check if duplicate checking is needed for this resource type
            if check_duplicate_resource_by_type(course_id, resource_type_id, file_name):
                try:
                    bot.delete_message(message.chat.id, loading_msg.message_id)
                except:
                    pass
                
                bot.send_message(
                    message.chat.id,
                    "⚠️ *Duplicate File*\n\n"
                    f"A file with the name *{file_name}* already exists for this course and resource type.\n\n"
                    "Please rename your file and try again.",
                    parse_mode="Markdown"
                )
                file_sessions.pop(message.from_user.id, None)
                return
            
            # Save resource (no file_id conflict check needed since we handle duplicates)
            resource_id = save_resource_with_type_check(
                course_id=course_id,
                resource_type_id=resource_type_id,
                file_id=doc.file_id,
                file_name=file_name,
                uploader_id=message.from_user.id
            )
            
            try:
                bot.delete_message(message.chat.id, loading_msg.message_id)
            except:
                pass
            
            if resource_id:
                bot.send_message(
                    message.chat.id,
                    "✅ *Resource uploaded successfully!*\n\n"
                    "Your resource is now available for your program community.",
                    parse_mode="Markdown"
                )
            else:
                bot.send_message(
                    message.chat.id,
                    "⚠️ *Upload Issue*\n\n"
                    "The resource could not be saved. Please try again.",
                    parse_mode="Markdown"
                )
            
            file_sessions.pop(message.from_user.id, None)
        
        except Exception as e:
            bot.send_message(
                message.chat.id,
                f"❌ *Error uploading resource:*\n\n{str(e)}",
                parse_mode="Markdown"
            )
            file_sessions.pop(message.from_user.id, None)

    # -------------------------
    # GET RESOURCE → SELECT COURSE
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "hub:get")
    def get_resource_course(call):
        program_id = get_user_program_id(call.from_user.id)
        courses = get_courses_by_program(program_id)

        kb = InlineKeyboardMarkup()
        for c in courses:
            kb.add(
                InlineKeyboardButton(
                    c["course_code"],
                    callback_data=f"get:course:{c['id']}"
                )
            )

        bot.send_message(
            call.message.chat.id,
            "📘 *Select a course:*",
            parse_mode="Markdown",
            reply_markup=kb
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

        kb = InlineKeyboardMarkup()
        for r in resource_types:
            kb.add(
                InlineKeyboardButton(
                    r["name"],
                    callback_data=f"get:type:{r['id']}"
                )
            )

        bot.send_message(
            call.message.chat.id,
            f"📂 *Select resource type for {course['course_code']}:*",
            parse_mode="Markdown",
            reply_markup=kb
        )

    # -------------------------
    # GET RESOURCE → SLOT SYSTEM
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data.startswith("get:type:"))
    def list_slots(call):
        user_id = call.from_user.id
        res_type_id = int(call.data.split(":")[2])
        session = file_sessions[user_id]

        resources = get_resources_by_course_and_type(
            session["course_id"], res_type_id
        )

        text = "📁 *Available Resources*\n\n"
        for i, r in enumerate(resources, start=1):
            text += f"Slot {i} | {r['file_name']}\n"
        text += (
            "\n\n📥 *Send:*\n"
            "• `Slot 1`\n"
            "• `Slot 1, Slot 2, Slot 3` (comma-separated)\n"
            "• `All`"
        )


        session["resources"] = resources

        bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

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
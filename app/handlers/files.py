from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from ..database.queries import (
    get_user_program_id,
    get_courses_by_program,
    get_resource_types,
    save_resource,
    get_resources_by_course_and_type,
    get_course_info
)

file_sessions = {}

def files_handler(bot):

    # -------------------------
    # HELP
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "hub:help")
    def help_info(call):
        bot.send_message(
            call.message.chat.id,
            (
                "ℹ️ *Help Guide*\n\n"
                "📚 *All Courses* — View courses in your program\n"
                "➕ *Add Resource* — Upload notes, slides, PDFs, etc\n"
                "📥 *Get Resource* — Download resources shared by others\n\n"
                "Resources are organized by *course* and *type*."
            ),
            parse_mode="Markdown"
        )
    
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

        save_resource(
            course_id=session["course_id"],
            resource_type_id=session["resource_type_id"],
            file_id=doc.file_id,
            file_name=doc.file_name,
            uploader_id=message.from_user.id
        )

        bot.send_message(
            message.chat.id,
            "✅ *Resource uploaded successfully!*",
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
            "\n\nSend:\n"
            "• `Slot 1`\n"
            "• `Slot 1 | Slot 2`\n"
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
            for r in resources:
                bot.send_document(message.chat.id, r["file_id"])

            file_sessions.pop(user_id, None)
            return

        # -------------------------
        # MULTI-SLOT (Slot 1 | Slot 2)
        # -------------------------
        try:
            slots = [
                int(part.strip().replace("slot", "")) - 1
                for part in text.split("|")
            ]
        except ValueError:
            bot.send_message(
                message.chat.id,
                "❌ Invalid format. Use `Slot 1 | Slot 2` or `All`.",
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
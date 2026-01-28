import re
from telebot import types
from ..database.queries import (
    get_group_program_id,
    get_courses_by_program,
    get_course_by_code,
    get_resource_types,
    save_resource,
    save_approval,
    is_file_duplicate,
    save_user,
    save_group
)

# Regex: "CSC 234" OR "CSC234"
COURSE_REGEX = re.compile(r'\b([A-Z]{3})\s?(\d{3})\b', re.IGNORECASE)

# Temporary in-memory state (safe for academic groups)
PENDING_FILES = {}
GROUP_SETUP_SESSIONS = {}


def extract_course_code(text):
    if not text:
        return None
    match = COURSE_REGEX.search(text.upper())
    if match:
        return f"{match.group(1)} {match.group(2)}"
    return None


def groups_handler(bot):

    # -------------------------
    # SETUP GROUP (Admin command)
    # -------------------------
    @bot.message_handler(commands=['setupgroup'], chat_types=['group', 'supergroup'])
    def setup_group(message):
        # Simple check: user must be group admin or creator
        user_id = message.from_user.id
        
        bot.send_message(
            message.chat.id,
            (
                "🔗 <b>Group Setup</b>\n\n"
                "Enter your program ID to link this group:\n"
                "(Ask your bot admin for your program ID)"
            ),
            parse_mode="HTML"
        )
        
        GROUP_SETUP_SESSIONS[message.chat.id] = {"user_id": user_id}

    @bot.message_handler(func=lambda m: m.chat.id in GROUP_SETUP_SESSIONS and m.text.isdigit(), chat_types=['group', 'supergroup'])
    def receive_program_id(message):
        program_id = int(message.text)
        chat_id = message.chat.id
        
        save_group(chat_id, program_id)
        GROUP_SETUP_SESSIONS.pop(chat_id)
        
        bot.send_message(
            chat_id,
            f"✅ <b>Group linked to program {program_id}</b>\n\n"
            "Files can now be shared and organized!",
            parse_mode="HTML"
        )

    # -------------------------
    # WELCOME MESSAGE ON ADD
    # -------------------------
    @bot.message_handler(content_types=['new_chat_members'])
    def handle_bot_added(message):
        for member in message.new_chat_members:
            if member.id == bot.get_me().id:
                # Extract program_id from group description or require setup
                bot.send_message(
                    message.chat.id,
                    (
                        "👋 <b>Hello! I'm your Academic Resource Manager</b>\n\n"
                        "📚 I automatically organize files shared in this group by:\n"
                        "• Course code\n"
                        "• Resource type (Notes, Slides, Past Questions, etc.)\n\n"
                        "📎 Just send a file and I'll take care of the rest.\n"
                        "✅ Approved resources are saved to your program's central hub.\n\n"
                        "⚠️ <b>Setup Required:</b> Contact an admin to link this group to your program."
                    ),
                    parse_mode="HTML"
                )
                break

    # -------------------------
    # HANDLE FILE UPLOAD
    # -------------------------
    @bot.message_handler(content_types=['document'], chat_types=['group', 'supergroup'])
    def handle_group_file(message):
        chat_id = message.chat.id
        doc = message.document

        program_id = get_group_program_id(chat_id)
        if not program_id:
            bot.send_message(
                chat_id,
                "⚠️ <b>Group not set up yet</b>\n\n"
                "Run /setupgroup to link this group to your program.",
                reply_to_message_id=message.message_id,
                parse_mode="HTML"
            )
            return

        # Save uploader
        save_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name
        )

        course_code = extract_course_code(doc.file_name)

        if course_code:
            course = get_course_by_code(program_id, course_code)
            if course and is_file_duplicate(doc.file_name, course["id"]):
                bot.send_message(
                    chat_id,
                    "✅ <b>Already added</b>",
                    reply_to_message_id=message.message_id,
                    parse_mode="HTML"
                )
                return

        # Store pending file
        PENDING_FILES[message.message_id] = {
            "file_id": doc.file_id,
            "file_name": doc.file_name,
            "course_code": course_code,
            "uploader_id": message.from_user.id,
            "chat_id": chat_id
        }

        if not course_code:
            ask_course_code(bot, message)
        else:
            ask_resource_type(bot, message.message_id)


    # -------------------------
    # ASK COURSE CODE
    # -------------------------
    def ask_course_code(bot, message):
        program_id = get_group_program_id(message.chat.id)
        courses = get_courses_by_program(program_id)

        markup = types.InlineKeyboardMarkup()
        for c in courses:
            markup.add(
                types.InlineKeyboardButton(
                    c["course_code"],
                    callback_data=f"course:{c['course_code']}"
                )
            )

        bot.send_message(
            message.chat.id,
            "❗ <b>Course code not detected</b>\nSelect course:",
            reply_markup=markup,
            reply_to_message_id=message.message_id,
            parse_mode="HTML"
        )


    # -------------------------
    # COURSE SELECT CALLBACK
    # -------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("course:"))
    def handle_course_select(call):
        msg_id = call.message.reply_to_message.message_id
        course_code = call.data.split(":")[1]

        PENDING_FILES[msg_id]["course_code"] = course_code
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id)

        ask_resource_type(bot, msg_id)


    # -------------------------
    # ASK RESOURCE TYPE
    # -------------------------
    def ask_resource_type(bot, message_id):
        types_list = get_resource_types()
        markup = types.InlineKeyboardMarkup()

        for r in types_list:
            markup.add(
                types.InlineKeyboardButton(
                    r["name"],
                    callback_data=f"type:{r['id']}"
                )
            )

        bot.send_message(
            PENDING_FILES[message_id]["chat_id"],
            "📚 Select resource type:",
            reply_markup=markup,
            reply_to_message_id=message_id
        )


    # -------------------------
    # RESOURCE TYPE SELECT
    # -------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("type:"))
    def handle_type_select(call):
        resource_type_id = int(call.data.split(":")[1])
        reply_msg_id = call.message.reply_to_message.message_id
        data = PENDING_FILES.pop(reply_msg_id)

        program_id = get_group_program_id(call.message.chat.id)
        course = get_course_by_code(program_id, data["course_code"])

        # Duplicate check (final)
        if is_file_duplicate(data["file_name"], course["id"]):
            bot.edit_message_text(
                "✅ <b>Already added</b>",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="HTML"
            )
            return

        save_resource(
            course["id"],
            resource_type_id,
            data["file_id"],
            data["file_name"],
            data["uploader_id"]
        )

        save_approval(
            resource_id=None,  # handled via trigger / FK if needed
            approved_by=call.from_user.id
        )

        bot.edit_message_text(
            f"✅ <b>Approved by @{call.from_user.username}</b>",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML"
        )

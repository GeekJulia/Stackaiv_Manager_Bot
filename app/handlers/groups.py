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
    save_group,
    get_course_info,
    get_program_info
)

# Regex: Three letters + optional space + three numbers (case-insensitive)
COURSE_REGEX = re.compile(r'\b([A-Z]{3})\s?(\d{3})\b', re.IGNORECASE)

# Temporary in-memory state
PENDING_FILES = {}
GROUP_SETUP_SESSIONS = {}

# -------------------------
# Extract course code from filename
# -------------------------
def extract_course_code(text):
    if not text:
        return None
    match = COURSE_REGEX.search(text.upper())
    if match:
        return f"{match.group(1)} {match.group(2)}"
    return None

def groups_handler(bot):

    # -------------------------
    # BOT ADDED → WELCOME + SETUP BUTTON
    # -------------------------
    @bot.message_handler(content_types=['new_chat_members'])
    def handle_bot_added(message):
        for member in message.new_chat_members:
            if member.id == bot.get_me().id:
                kb = types.InlineKeyboardMarkup()
                kb.add(types.InlineKeyboardButton("🔧 Set Up Group", callback_data="setup:group"))
                bot.send_message(
                    message.chat.id,
                    (
                        "👋 <b>Hello! I'm your Academic Resource Manager</b>\n\n"
                        "📚 I automatically organize files shared in this group by:\n"
                        "• Course code\n"
                        "• Resource type (Notes, Slides, Past Questions, etc.)\n\n"
                        "📎 Just send a file and I'll take care of the rest.\n\n"
                        "⚠️ <b>Setup Required:</b> Click 'Set Up Group' to link this group to your program."
                    ),
                    parse_mode="HTML",
                    reply_markup=kb
                )
                break

    # -------------------------
    # INLINE BUTTON → START SETUP
    # -------------------------
    @bot.callback_query_handler(func=lambda c: c.data == "setup:group")
    def setup_group_button(call):
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        bot.send_message(
            chat_id,
            "🔗 <b>Group Setup</b>\n\nEnter your program ID to link this group:\n(Ask your bot admin for your program ID)",
            parse_mode="HTML"
        )
        GROUP_SETUP_SESSIONS[chat_id] = {"user_id": user_id}

    # -------------------------
    # RECEIVE PROGRAM ID
    # -------------------------
    @bot.message_handler(func=lambda m: m.chat.id in GROUP_SETUP_SESSIONS and m.text.isdigit(), chat_types=['group', 'supergroup'])
    def receive_program_id(message):
        program_id = int(message.text)
        chat_id = message.chat.id
        save_group(chat_id, program_id)
        GROUP_SETUP_SESSIONS.pop(chat_id)
        program_info = get_program_info(program_id)
        bot.send_message(
            chat_id,
            f"✅ <b>Group linked to program {program_info['name']} ({program_info['level']})</b>\n\n🎉 Welcome! Files can now be shared, accessed, and organized automatically.",
            parse_mode="HTML"
        )

    # -------------------------
    # HANDLE DOCUMENT UPLOAD
    # -------------------------
    @bot.message_handler(content_types=['document'], chat_types=['group', 'supergroup'])
    def handle_group_file(message):
        chat_id = message.chat.id
        doc = message.document
        program_id = get_group_program_id(chat_id)
        if not program_id:
            bot.send_message(
                chat_id,
                "⚠️ <b>Group not set up yet</b>\nClick 'Set Up Group' or run /setupgroup to link this group.",
                reply_to_message_id=message.message_id,
                parse_mode="HTML"
            )
            return

        # Save uploader info
        save_user(message.from_user.id, message.from_user.username, message.from_user.first_name)

        # Extract course code from filename
        course_code = extract_course_code(doc.file_name)
        course = get_course_by_code(program_id, course_code) if course_code else None

        # Store pending file
        PENDING_FILES[message.message_id] = {
            "file_id": doc.file_id,
            "file_name": doc.file_name,
            "course_code": course_code,
            "course_id": course["id"] if course else None,
            "uploader_id": message.from_user.id,
            "chat_id": chat_id
        }

        if course_code and course:
            # Ask for resource type immediately
            ask_resource_type(bot, message.message_id)
        else:
            # Ask user to select course manually
            ask_course_selection(bot, message)

    # -------------------------
    # ASK COURSE (IF NOT FOUND)
    # -------------------------
    def ask_course_selection(bot, message):
        program_id = get_group_program_id(message.chat.id)
        courses = get_courses_by_program(program_id)
        markup = types.InlineKeyboardMarkup()
        for c in courses:
            markup.add(types.InlineKeyboardButton(c["course_code"], callback_data=f"course:{c['id']}"))
        bot.send_message(
            message.chat.id,
            "❗ <b>Course code not detected or invalid.</b>\nSelect the correct course:",
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
        course_id = int(call.data.split(":")[1])
        course_info = get_course_info(course_id)
        PENDING_FILES[msg_id]["course_id"] = course_id
        PENDING_FILES[msg_id]["course_code"] = course_info["course_code"]
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id)
        ask_resource_type(bot, msg_id)

    # -------------------------
    # ASK RESOURCE TYPE
    # -------------------------
    def ask_resource_type(bot, msg_id):
        types_list = get_resource_types()
        markup = types.InlineKeyboardMarkup()
        for r in types_list:
            markup.add(types.InlineKeyboardButton(r["name"], callback_data=f"type:{msg_id}:{r['id']}"))
        bot.send_message(
            PENDING_FILES[msg_id]["chat_id"],
            "📚 Select resource type:",
            reply_markup=markup,
            reply_to_message_id=msg_id
        )

    # -------------------------
    # RESOURCE TYPE SELECT → CONFIRM
    # -------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("type:"))
    def handle_type_select(call):
        parts = call.data.split(":")
        msg_id = int(parts[1])
        resource_type_id = int(parts[2])
        PENDING_FILES[msg_id]["resource_type_id"] = resource_type_id
        course_id = PENDING_FILES[msg_id]["course_id"]
        file_name = PENDING_FILES[msg_id]["file_name"]

        # Check duplicate now
        if is_file_duplicate(file_name, course_id):
            bot.edit_message_text(
                "✅ <b>Already been added</b>",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="HTML"
            )
            PENDING_FILES.pop(msg_id)
            return

        resource_name = [r['name'] for r in get_resource_types() if r['id'] == resource_type_id][0]
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(f"✅ Submit", callback_data=f"submit:{msg_id}"))

        bot.edit_message_text(
            f"⚠️ Confirm adding this file for <b>{PENDING_FILES[msg_id]['course_code']} - {resource_name}</b>?",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=markup
        )

    # -------------------------
    # FINAL SUBMIT → SAVE & APPROVE
    # -------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("submit:"))
    def handle_submit(call):
        msg_id = int(call.data.split(":")[1])
        data = PENDING_FILES.pop(msg_id)
        # Save resource
        save_resource(
            course_id=data["course_id"],
            resource_type_id=data["resource_type_id"],
            file_id=data["file_id"],
            file_name=data["file_name"],
            uploader_id=data["uploader_id"]
        )
        # Save approval
        save_approval(resource_id=None, approved_by=call.from_user.id)
        bot.edit_message_text(
            f"✅ <b>Approved by @{call.from_user.username}</b>",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML"
        )

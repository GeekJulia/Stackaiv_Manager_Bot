from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from ..database.queries import (
    get_user_program_id,
    save_courses,
    get_resource_types,
    save_course_resource_types
)

notes_sessions = {}

#Add Courses → Save Courses
#Button → Instruction Message
#--------------------------
def notes_handler(bot):

    @bot.callback_query_handler(func=lambda call: call.data == "cmd:addcourses")
    def add_courses_info(call):
        bot.send_message(
            call.message.chat.id,
            (
                "📚 *Add Your Courses*\n\n"
                "Send your courses in this format:\n\n"
                "`MAT 111 | CSC 111 | PHY 101`\n\n"
                "Use `|` to separate courses."
            ),
            parse_mode="Markdown"
        )

        notes_sessions[call.from_user.id] = {
            "stage": "awaiting_courses"
        }

#Receive Course Message & Save to DB
#--------------------------
    @bot.message_handler(func=lambda m: notes_sessions.get(m.from_user.id, {}).get("stage") == "awaiting_courses")
    def receive_courses(message):
        user_id = message.from_user.id
        raw_courses = message.text.upper()

        course_codes = [c.strip() for c in raw_courses.split("|") if c.strip()]

        program_id = get_user_program_id(user_id)

        course_ids = save_courses(program_id, course_codes)

        notes_sessions[user_id] = {
            "stage": "select_resources",
            "course_ids": course_ids,
            "selected_resources": set()
        }

        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton(
                "📂 Select Preferred Resource Type",
                callback_data="cmd:addresources"
            )
        )

        bot.send_message(
            message.chat.id,
            "✅ *Courses saved successfully!*",
            parse_mode="Markdown",
            reply_markup=kb
        )

#Resource Type Selection (Checkbox Style)
#Show Resource Types
#--------------------------
        @bot.callback_query_handler(func=lambda call: call.data == "cmd:addresources")
        def show_resource_types(call):
            user_id = call.from_user.id
            resource_types = get_resource_types()

            kb = InlineKeyboardMarkup()
            for r in resource_types:
                kb.add(
                    InlineKeyboardButton(
                        f"⬜ {r['name']}",
                        callback_data=f"res:{r['id']}"
                    )
                )

            kb.add(
                InlineKeyboardButton("✅ Submit", callback_data="cmd:submit")
            )

            bot.send_message(
                call.message.chat.id,
                "📁 *Select resource types (multiple allowed):*",
                parse_mode="Markdown",
                reply_markup=kb
            )

#Toggle Checkbox
#--------------------------
        @bot.callback_query_handler(func=lambda call: call.data.startswith("res:"))
        def toggle_resource(call):
            user_id = call.from_user.id
            res_id = int(call.data.split(":")[1])

            selected = notes_sessions[user_id]["selected_resources"]

            if res_id in selected:
                selected.remove(res_id)
            else:
                selected.add(res_id)

            bot.answer_callback_query(call.id, "Selection updated")

#Submit → Save for ALL Courses
#--------------------------
        @bot.callback_query_handler(func=lambda call: call.data == "cmd:submit")
        def submit_resources(call):
            user_id = call.from_user.id
            session = notes_sessions[user_id]

            for course_id in session["course_ids"]:
                save_course_resource_types(
                    course_id,
                    list(session["selected_resources"])
                )

            bot.send_message(
                call.message.chat.id,
                "🎉 *Resource setup complete!*\nYour program hub is ready.",
                parse_mode="Markdown"
            )

            notes_sessions.pop(user_id, None)
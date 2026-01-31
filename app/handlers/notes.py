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
                "⚠️ *Important Notice:*\n"
                "Please enter your courses carefully. Any mistakes will require you to re-register, "
                "which will clear all courses and resource types.\n\n"
                "Send your courses in this format:\n\n"
                "`MAT 111 | CSC 111 | PHY 101`\n\n"
                "Use `|` to separate courses."
            ),
            parse_mode="Markdown"
        )

        notes_sessions[call.from_user.id] = {
            "stage": "awaiting_courses"
        }

#Receive Course Message & Show Confirmation
#--------------------------
    @bot.message_handler(func=lambda m: notes_sessions.get(m.from_user.id, {}).get("stage") == "awaiting_courses")
    def receive_courses(message):
        user_id = message.from_user.id
        raw_courses = message.text.upper()

        course_codes = [c.strip() for c in raw_courses.split("|") if c.strip()]

        # Store courses temporarily for confirmation
        notes_sessions[user_id]["pending_courses"] = course_codes
        notes_sessions[user_id]["stage"] = "confirming_courses"

        # Format courses for display
        courses_list = "\n".join([f"• {code}" for code in course_codes])

        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("✅ Yes, Proceed", callback_data="confirm:courses:yes"))
        kb.add(InlineKeyboardButton("❌ No, Re-enter", callback_data="confirm:courses:no"))

        bot.send_message(
            message.chat.id,
            (
                f"📋 *Confirm Your Courses*\n\n"
                f"{courses_list}\n\n"
                f"⚠️ *Please double-check these courses.*\n"
                f"Any mistakes will require re-registration.\n\n"
                f"Are these courses correct?"
            ),
            parse_mode="Markdown",
            reply_markup=kb
        )

#Confirm Courses - Yes
#--------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "confirm:courses:yes")
    def confirm_courses_yes(call):
        user_id = call.from_user.id
        session = notes_sessions.get(user_id)

        if not session or "pending_courses" not in session:
            bot.answer_callback_query(call.id, "Session expired. Please start again.")
            return

        course_codes = session["pending_courses"]
        program_id = get_user_program_id(user_id)

        # Save courses to database
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
            call.message.chat.id,
            "✅ *Courses saved successfully!*",
            parse_mode="Markdown",
            reply_markup=kb
        )

#Confirm Courses - No
#--------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "confirm:courses:no")
    def confirm_courses_no(call):
        user_id = call.from_user.id
        
        # Reset to awaiting courses stage
        notes_sessions[user_id] = {
            "stage": "awaiting_courses"
        }

        bot.send_message(
            call.message.chat.id,
            (
                "🔄 *Re-enter Your Courses*\n\n"
                "Send your courses in this format:\n\n"
                "`MAT 111 | CSC 111 | PHY 101`\n\n"
                "Use `|` to separate courses."
            ),
            parse_mode="Markdown"
        )

#Resource Type Selection (Checkbox Style)
#Show Resource Types
#--------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "cmd:addresources")
    def show_resource_types(call):
        user_id = call.from_user.id
        resource_types = get_resource_types()

        bot.send_message(
            call.message.chat.id,
            (
                "📁 *Select Resource Types*\n\n"
                "⚠️ *Important Notice:*\n"
                "Please select carefully. Any mistakes will require you to re-register, "
                "which will clear all courses and resource types.\n\n"
                "Select the resource types you want to use:"
            ),
            parse_mode="Markdown"
        )

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

        if not session.get("selected_resources"):
            bot.answer_callback_query(call.id, "Please select at least one resource type.")
            return

        for course_id in session["course_ids"]:
            save_course_resource_types(
                course_id,
                list(session["selected_resources"])
            )

        program_id = get_user_program_id(call.from_user.id)
        # program = get_program_info(program_id)

        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("📚 All Courses", callback_data="hub:courses"),
            InlineKeyboardButton("➕ Add Resource", callback_data="hub:add"),
            InlineKeyboardButton("📥 Get Resource", callback_data="hub:get"),
            InlineKeyboardButton("ℹ️ Help Info", callback_data="hub:help"),
        )
        kb.add(InlineKeyboardButton("🔄 Re-register", callback_data="hub:reregister"))

        bot.send_message(
        call.message.chat.id,
        (
            "🎉 *Resource setup successful!*\n\n"
            "👋 Welcome to your *Computer Science 400 Level* "
            "digital central resource hub.\n\n"
            "What would you like to do?"
        ),
        parse_mode="Markdown",
        reply_markup=kb
    )

        notes_sessions.pop(user_id, None)
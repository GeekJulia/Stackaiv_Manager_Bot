from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from ..database.queries import (
    get_user_program_id,
    get_program_info,
    save_courses,
    get_courses_by_program,
    get_resource_types,
    save_course_resource_types
)
from ..utils.db_operations import safe_db_operation, DatabaseTimeoutError
from ..utils.sessions import TTLDict, get_active_program_id
from ..utils.messages import send_loading_message, safe_edit_or_send as edit_message_safe

notes_sessions = TTLDict()

def notes_handler(bot):
    """
    Handles course registration and resource type selection.
    Flow: add_courses_info → receive_courses → confirm_courses → select_resources → confirm_resources → submit
    """
    # -------------------------
    # Start Notes/Courses Handler -  FIXED
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "notes:start")
    def notes_start(call):
        """Entry point for course management"""
        user_id = call.from_user.id
        message_id = call.message.message_id
        
        # Show loading indicator
        loading_msg_id = send_loading_message(
            bot,
            call.message.chat.id,
            " *Loading your courses...*"
        )
        
        try:
            #  USE NEW HELPER FUNCTION
            program_id = get_active_program_id(user_id)
            courses = []
            if program_id:
                courses = safe_db_operation(get_courses_by_program, [], program_id)
            
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton(" Add New Courses", callback_data="notes:add_courses"))
            if courses:
                kb.add(InlineKeyboardButton(" Modify Resource Types", callback_data="notes:modify_resources"))
            kb.add(InlineKeyboardButton(" Help", callback_data="notes:help"))
            kb.add(InlineKeyboardButton(" Back", callback_data="action:goto_space"))
            
            if courses:
                courses_list = "\n".join([f"• {c['course_code']}" for c in courses])
                message_text = f" *Your Courses:*\n\n{courses_list}\n\n*What would you like to do?*"
            else:
                message_text = " *You haven't added any courses yet.*\n\nAdd courses to get started!"
            
            # Edit loading message with content
            edit_message_safe(
                bot,
                call.message.chat.id,
                loading_msg_id,
                message_text,
                parse_mode="Markdown",
                reply_markup=kb
            )
            
        except DatabaseTimeoutError:
            edit_message_safe(
                bot,
                call.message.chat.id,
                loading_msg_id,
                " *System is busy*\n\nPlease try again in a moment.",
                parse_mode="Markdown"
            )
        except Exception as e:
            edit_message_safe(
                bot,
                call.message.chat.id,
                loading_msg_id,
                f" Error: {str(e)}",
                parse_mode="Markdown"
            )


    # -------------------------
    # Add Courses Info
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "notes:add_courses")
    def add_courses_info(call):
        user_id = call.from_user.id
        message_id = call.message.message_id

        # Capture the active semester from start.py sessions so we never need to ask
        from .start import user_sessions as start_sessions
        active_semester = start_sessions.get(user_id, {}).get('active_semester', 'Alpha')

        notes_sessions[user_id] = {
            "stage": "awaiting_courses",
            "semester": active_semester
        }
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton(" Back", callback_data="notes:start"))
        
        try:
            bot.edit_message_text(
                (
                    " *Add Your Courses*\n\n"
                    " *Important:*\n"
                    "Please enter your courses carefully. Format matters!\n\n"
                    "Send your courses separated by **commas**:\n\n"
                    "`MAT 111, CSC 111, PHY 101`\n\n"
                    "You can add 1-20 courses at a time.\n"
                    "(Supports both comma and pipe separators)"
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
                    " *Add Your Courses*\n\n"
                    "Send your courses separated by commas:\n\n"
                    "`MAT 111, CSC 111, PHY 101`"
                ),
                parse_mode="Markdown",
                reply_markup=kb
            )

    # -------------------------
    # Receive Courses
    # -------------------------
    @bot.message_handler(func=lambda m: notes_sessions.get(m.from_user.id, {}).get("stage") == "awaiting_courses")
    def receive_courses(message):
        user_id = message.from_user.id
        raw_courses = message.text.strip()

        # Convert to uppercase for consistency and parse courses - support both comma and pipe separation
        course_codes = [c.strip().upper() for c in raw_courses.replace("|", ",").split(",") if c.strip()]

        if not course_codes or len(course_codes) > 20:
            bot.send_message(
                message.chat.id,
                " *Invalid input*\n\n"
                "Please send 1-20 courses separated by commas.\n"
                "Example: `MAT 111, CSC 111, PHY 101`",
                parse_mode="Markdown"
            )
            return

        # Store courses temporarily for confirmation
        notes_sessions[user_id]["pending_courses"] = course_codes
        notes_sessions[user_id]["stage"] = "confirming_courses"

        # Format courses for display
        courses_list = "\n".join([f"☐ {code}" for code in course_codes])

        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton(" Correct", callback_data="notes:confirm_yes"))
        kb.add(InlineKeyboardButton(" Wrong", callback_data="notes:confirm_no"))
        kb.add(InlineKeyboardButton(" Back", callback_data="notes:start"))

        bot.send_message(
            message.chat.id,
            (
                f" *Confirm Your Courses*\n\n"
                f"{courses_list}\n\n"
                f"Is this correct?"
            ),
            parse_mode="Markdown",
            reply_markup=kb
        )

    # -------------------------
    # Confirm Courses - Yes -  FIXED
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "notes:confirm_yes")
    def confirm_courses_yes(call):
        user_id = call.from_user.id
        message_id = call.message.message_id
        session = notes_sessions.get(user_id)

        if not session or "pending_courses" not in session:
            bot.answer_callback_query(call.id, " Session expired. Start again.", show_alert=True)
            return

        # Use the semester captured when the user triggered add_courses (no prompt needed)
        semester = session.get("semester", "Alpha")
        course_codes = session["pending_courses"]

        loading_msg_id = send_loading_message(bot, call.message.chat.id, " *Saving courses...*")

        try:
            program_id = get_active_program_id(user_id)
            if not program_id:
                edit_message_safe(bot, call.message.chat.id, loading_msg_id, " Program not found.", parse_mode="Markdown")
                return

            program_info = safe_db_operation(get_program_info, None, program_id)
            academic_level = program_info['level'] if program_info else "Unknown"

            course_ids = safe_db_operation(save_courses, [], program_id, course_codes, academic_level, semester)

            notes_sessions[user_id].update({
                "stage": "select_resources",
                "course_ids": course_ids,
                "course_codes": course_codes,
                "selected_resources": set(),
                "message_id": message_id
            })

            show_resource_checkboxes(bot, call.message.chat.id, user_id, loading_msg_id)

        except Exception as e:
            edit_message_safe(
                bot,
                call.message.chat.id,
                loading_msg_id,
                f" Error saving courses: {str(e)}",
                parse_mode="Markdown"
            )

    # -------------------------
    # Confirm Courses - No
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "notes:confirm_no")
    def confirm_courses_no(call):
        user_id = call.from_user.id
        message_id = call.message.message_id
        
        # Reset to awaiting courses stage
        notes_sessions[user_id] = {
            "stage": "awaiting_courses"
        }

        try:
            bot.edit_message_text(
                (
                    " *Re-enter Your Courses*\n\n"
                    "Send your courses separated by commas:\n\n"
                    "`MAT 111, CSC 111, PHY 101`"
                ),
                call.message.chat.id,
                message_id,
                parse_mode="Markdown"
            )
        except:
            bot.send_message(
                call.message.chat.id,
                " *Re-enter Your Courses*\n\nSend courses separated by commas.",
                parse_mode="Markdown"
            )

    # -------------------------
    # Helper: Show Resource Type Checkboxes
    # -------------------------
    def show_resource_checkboxes(bot, chat_id, user_id, message_id=None):
        """Display resource types as a checkbox list with better UI"""
        session = notes_sessions.get(user_id, {})
        
        try:
            resource_types = safe_db_operation(get_resource_types, [])
            if not resource_types:
                edit_message_safe(
                    bot,
                    chat_id,
                    message_id or session.get("message_id"),
                    " No resource types available. Please contact support.",
                    parse_mode="Markdown"
                )
                return
        except DatabaseTimeoutError:
            edit_message_safe(
                bot,
                chat_id,
                message_id or session.get("message_id"),
                " *System is busy*\n\nPlease try again in a moment.",
                parse_mode="Markdown"
            )
            return
        
        selected = session.get("selected_resources", set())

        # Create checkbox display
        checkbox_list = ""
        for r in resource_types:
            checkbox = "" if r['id'] in selected else "☐"
            checkbox_list += f"{checkbox} {r['name']}\n"

        message_text = (
            " *Select Resource Types for Your Courses*\n\n"
            f"{checkbox_list}\n"
            "_Click buttons to toggle selections_"
        )

        kb = InlineKeyboardMarkup(row_width=2)
        for r in resource_types:
            checkbox = "" if r['id'] in selected else "☐"
            kb.add(InlineKeyboardButton(
                f"{checkbox} {r['name']}",
                callback_data=f"notes:res:{r['id']}"
            ))

        kb.add(InlineKeyboardButton(" Done Selecting", callback_data="notes:confirm_resources"))
        kb.add(InlineKeyboardButton(" Back", callback_data="notes:start"))

        edit_message_safe(
            bot,
            chat_id,
            message_id or session.get("message_id"),
            message_text,
            parse_mode="Markdown",
            reply_markup=kb
        )

    # -------------------------
    # Toggle Resource Selection
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data.startswith("notes:res:"))
    def toggle_resource(call):
        user_id = call.from_user.id
        message_id = call.message.message_id
        
        try:
            res_id = int(call.data.split(":")[2])
            selected = notes_sessions[user_id]["selected_resources"]

            if res_id in selected:
                selected.remove(res_id)
                action = "removed"
            else:
                selected.add(res_id)
                action = "added"

            # Update message with new checkbox states
            resource_types = get_resource_types()
            checkbox_list = ""
            for r in resource_types:
                checkbox = "" if r['id'] in selected else "☐"
                checkbox_list += f"{checkbox} {r['name']}\n"

            message_text = (
                " *Select Resource Types for Your Courses*\n\n"
                f"{checkbox_list}\n"
                "_Click buttons to toggle selections_"
            )

            kb = InlineKeyboardMarkup(row_width=2)
            for r in resource_types:
                checkbox = "" if r['id'] in selected else "☐"
                kb.add(InlineKeyboardButton(
                    f"{checkbox} {r['name']}",
                    callback_data=f"notes:res:{r['id']}"
                ))

            kb.add(InlineKeyboardButton(" Done Selecting", callback_data="notes:confirm_resources"))
            kb.add(InlineKeyboardButton(" Back", callback_data="notes:start"))

            try:
                bot.edit_message_text(
                    message_text,
                    call.message.chat.id,
                    message_id,
                    parse_mode="Markdown",
                    reply_markup=kb
                )
            except:
                pass

            bot.answer_callback_query(call.id, f" {action.capitalize()}")

        except Exception as e:
            bot.answer_callback_query(call.id, f" Error: {str(e)}", show_alert=True)

    # -------------------------
    # Confirm Resource Types
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "notes:confirm_resources")
    def confirm_resources(call):
        user_id = call.from_user.id
        message_id = call.message.message_id
        session = notes_sessions.get(user_id)

        if not session or not session.get("selected_resources"):
            bot.answer_callback_query(call.id, " Select at least one resource type", show_alert=True)
            return

        # Show confirmation message
        selected_ids = list(session["selected_resources"])
        resource_types = get_resource_types()
        selected_names = [r['name'] for r in resource_types if r['id'] in selected_ids]
        resources_list = "\n".join([f"• {name}" for name in selected_names])

        message_text = (
            " *Confirm Resource Types*\n\n"
            "You've selected the following resource types for all your courses:\n\n"
            f"{resources_list}\n\n"
            "Is this correct?"
        )

        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton(" Yes, Proceed", callback_data="notes:submit"))
        kb.add(InlineKeyboardButton(" No, Change", callback_data="notes:select_resources"))

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

    # -------------------------
    # Change Resource Selection
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "notes:select_resources")
    def select_resources_again(call):
        user_id = call.from_user.id
        show_resource_checkboxes(bot, call.message.chat.id, user_id)

    # -------------------------
    # Submit - Save Resource Types for All Courses -  FIXED
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "notes:submit")
    def submit_resources(call):
        user_id = call.from_user.id
        message_id = call.message.message_id
        session = notes_sessions.get(user_id)

        try:
            loading_msg = bot.send_message(
                call.message.chat.id,
                " *Processing...*\n\n Saving your setup...",
                parse_mode="Markdown"
            )

            # Save resource types for all newly registered courses
            selected_resources = list(session["selected_resources"])
            for course_id in session["course_ids"]:
                save_course_resource_types(course_id, selected_resources)

            # Build success message using ONLY the courses just registered
            course_codes = session.get("course_codes", [])
            semester = session.get("semester", "this")
            courses_list = "\n".join([f"• {code}" for code in course_codes])

            program_id = get_active_program_id(user_id)
            program_info = get_program_info(program_id)

            message_text = (
                f" *{semester} Semester — Courses Registered*\n\n"
                f"{courses_list}\n\n"
                "⚠️ *Important Notice*\n"
                "These courses represent your entire cohort's curriculum for this semester. "
                "Every student in your program will depend on this list to share and access resources.\n\n"
                "_Please ensure all departmental courses — including electives — are included before confirming._"
            )

            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton(" ✅ Confirm & Go to Hub", callback_data="notes:setup_done"))

            try:
                bot.delete_message(call.message.chat.id, loading_msg.message_id)
            except:
                pass
            try:
                bot.delete_message(call.message.chat.id, message_id)
            except:
                pass

            bot.send_message(
                call.message.chat.id,
                message_text,
                parse_mode="Markdown",
                reply_markup=kb
            )

            notes_sessions.pop(user_id, None)

        except Exception as e:
            bot.send_message(
                call.message.chat.id,
                f" Error: {str(e)}\n\nPlease try again.",
                parse_mode="Markdown"
            )

    @bot.callback_query_handler(func=lambda call: call.data == "notes:setup_done")
    def setup_done(call):
        """Dismiss the confirmation and open the hub."""
        user_id = call.from_user.id
        from .start import user_sessions as start_sessions, show_program_hub_panel
        program_id = get_active_program_id(user_id)
        program = safe_db_operation(get_program_info, None, program_id)
        if program:
            show_program_hub_panel(bot, call.message.chat.id, program, message_id=call.message.message_id)
        else:
            bot.answer_callback_query(call.id, "Could not load hub. Please /start again.", show_alert=True)

    # -------------------------
    # Modify Resource Types
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "notes:modify_resources")
    def modify_resources(call):
        user_id = call.from_user.id
        
        notes_sessions[user_id] = {
            "stage": "select_resources",
            "course_ids": [],  # Not needed for modification
            "selected_resources": set()
        }

        show_resource_checkboxes(bot, call.message.chat.id, user_id)

    # -------------------------
    # Help
    # -------------------------
    @bot.callback_query_handler(func=lambda call: call.data == "notes:help")
    def notes_help(call):
        message_id = call.message.message_id
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton(" Back", callback_data="notes:start"))

        try:
            bot.edit_message_text(
                (
                    " *Course Management Help*\n\n"
                    "*Adding Courses:*\n"
                    "• Format: `MAT 111, CSC 111, PHY 101`\n"
                    "• Separate courses with commas\n"
                    "• Max 20 courses per add\n\n"
                    "*Resource Types:*\n"
                    "Each course can have multiple resource types\n"
                    "• Notes, PQ Images, PQ Files\n"
                    "• Textbooks, Study Files, Code\n"
                    "• Drawings, Videos\n\n"
                    "*Pro Tips:*\n"
                    "• Double-check courses before confirming\n"
                    "• Select all resource types you'll use\n"
                    "• You can modify later\n"
                ),
                call.message.chat.id,
                message_id,
                parse_mode="Markdown",
                reply_markup=kb
            )
        except:
            bot.send_message(
                call.message.chat.id,
                " *Course Management Help*\n\n"
                "Format courses as: `MAT 111, CSC 111, PHY 101`",
                parse_mode="Markdown",
                reply_markup=kb
            )
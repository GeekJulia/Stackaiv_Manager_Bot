"""
Utility functions for building Telegram inline keyboards.
"""

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton


def build_course_keyboard(courses, callback_prefix="course", row_width=1):
    """
    Build an inline keyboard for course selection.
    
    Args:
        courses: List of course dicts with 'id' and 'course_code' keys
        callback_prefix: Prefix for callback data (e.g., "course", "get:course", "add:course")
        row_width: Number of buttons per row
    
    Returns:
        InlineKeyboardMarkup with course buttons
    """
    kb = InlineKeyboardMarkup(row_width=row_width)
    for course in courses:
        kb.add(
            InlineKeyboardButton(
                course['course_code'],
                callback_data=f"{callback_prefix}:{course['id']}"
            )
        )
    return kb


def build_resource_type_keyboard(resource_types, callback_prefix="type", row_width=1):
    """
    Build an inline keyboard for resource type selection.
    
    Args:
        resource_types: List of resource type dicts with 'id' and 'name' keys
        callback_prefix: Prefix for callback data (e.g., "type", "get:type", "add:type")
        row_width: Number of buttons per row
    
    Returns:
        InlineKeyboardMarkup with resource type buttons
    """
    kb = InlineKeyboardMarkup(row_width=row_width)
    for rtype in resource_types:
        kb.add(
            InlineKeyboardButton(
                rtype['name'],
                callback_data=f"{callback_prefix}:{rtype['id']}"
            )
        )
    return kb


def build_level_keyboard(levels=None, row_width=1):
    """
    Build an inline keyboard for level selection.
    
    Args:
        levels: List of level strings (defaults to standard 100-500 levels)
        row_width: Number of buttons per row
    
    Returns:
        InlineKeyboardMarkup with level buttons
    """
    if levels is None:
        levels = ['100 Level', '200 Level', '300 Level', '400 Level', '500 Level']
    
    kb = InlineKeyboardMarkup(row_width=row_width)
    for level in levels:
        kb.add(
            InlineKeyboardButton(
                level,
                callback_data=f"level:{level}"
            )
        )
    return kb


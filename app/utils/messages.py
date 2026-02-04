"""
Utility functions for safe message handling in Telegram bot.
"""

def safe_edit_or_send(bot, chat_id, message_id, text, parse_mode="Markdown", reply_markup=None, **kwargs):
    """
    Safely edit a message, falling back to sending a new message if edit fails.
    
    This is useful because:
    - Messages can't be edited if they're too old
    - Messages can't be edited if content hasn't changed
    - Network issues can cause edit failures
    
    Args:
        bot: The TeleBot instance
        chat_id: Chat ID where message is located
        message_id: Message ID to edit (if None, will always send new)
        text: Message text to send/edit
        parse_mode: Parse mode (Markdown, HTML, etc.)
        reply_markup: Inline keyboard markup
        **kwargs: Additional arguments for send_message
    
    Returns:
        The message object (either edited or newly sent)
    """
    if message_id:
        try:
            return bot.edit_message_text(
                text=text,
                chat_id=chat_id,
                message_id=message_id,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                **kwargs
            )
        except Exception:
            # Edit failed, send new message instead
            pass
    
    # Send new message (either because edit failed or message_id was None)
    return bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=parse_mode,
        reply_markup=reply_markup,
        **kwargs
    )


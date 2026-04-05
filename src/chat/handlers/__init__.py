# src/chat/handlers/__init__.py
from .message_handler import new_message_handler
from .read_handler import message_read_handler
from .status_handler import user_typing_handler, add_user_to_chat_handler, chat_deleted_handler

def get_handlers():
    return {
        "new_message": new_message_handler,
        "message_read": message_read_handler,
        "user_typing": user_typing_handler,
        "add_user_to_chat": add_user_to_chat_handler,
        "chat_deleted": chat_deleted_handler
    }
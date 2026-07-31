"""Conversation states for the Telegram bot.

Used by ConversationHandler to manage multi-step flows.
"""

from enum import IntEnum, auto


class BotState(IntEnum):
    """Enumeration of conversation states."""

    IDLE = auto()
    SPLIT_SELECT_DURATION = auto()
    SPLIT_ENTER_CUSTOM = auto()
    SPLIT_WAIT_VIDEO = auto()
    SPLIT_PROCESSING = auto()
    MERGE_COLLECT = auto()
    MERGE_PROCESSING = auto()

"""Conversation states."""

from enum import IntEnum, auto


class BotState(IntEnum):
    SPLIT_ENTER_DURATION = auto()
    SPLIT_WAIT_VIDEO = auto()
    MERGE_COLLECT = auto()
    TIMELINE_WAIT_VIDEO = auto()
    TIMELINE_WAIT_BUTTON = auto()
    TIMELINE_WAIT_RANGES = auto()

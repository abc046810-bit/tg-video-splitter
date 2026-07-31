# File 8 : states.py

from collections import defaultdict


class UserSession:

    def __init__(self):

        self.mode = None
        self.duration = None

        self.waiting_custom_duration = False

        self.current_video = None

        self.merge_files = []


USERS = defaultdict(UserSession)

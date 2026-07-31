"""Progress tracking and display."""

import time
import humanize


class ProgressTracker:
    """Tracks byte progress with speed and ETA."""

    def __init__(self, total: int, description: str = "Processing"):
        self.total = max(total, 1)
        self.description = description
        self.start_time = time.monotonic()

    def update(self, current: int) -> str:
        current = min(current, self.total)
        elapsed = time.monotonic() - self.start_time

        if elapsed <= 0:
            speed = 0.0
            eta = 0
        else:
            speed = current / elapsed
            remaining = self.total - current
            eta = int(remaining / speed) if speed > 0 else 0

        pct = int(current * 100 / self.total)
        bar_len = 10
        filled = int(bar_len * pct / 100)
        empty = bar_len - filled
        bar = ("#" * filled) + ("-" * empty)

        return (
            self.description + "\n"
            + bar + " " + str(pct) + "%\n"
            + humanize.naturalsize(current) + " / " + humanize.naturalsize(self.total) + "\n"
            + humanize.naturalsize(speed) + "/s | ETA " + str(eta) + "s"
        )
      

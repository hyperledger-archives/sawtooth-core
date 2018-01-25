import time
import logging

LOGGER = logging.getLogger(__name__)


class Heartbeat:
    """Logs a message every `period` seconds."""
    def __init__(self, message="heartbeat", period=3):
        self.message = message
        self.period = period
        self.next = time.time() + period

    def beat(self):
        now = time.time()
        if now > self.next:
            LOGGER.debug("%s; delay=%s", self.message, now - self.next)
            self.next = now + self.period

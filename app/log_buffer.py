"""In-memory log buffer for exposing backend logs to the UI."""
import logging
import threading

LOG_BUFFER_MAX_LINES = 1000
_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class InMemoryLogHandler(logging.Handler):
    """Thread-safe handler that appends formatted log records to a fixed-size buffer."""

    def __init__(self, buffer: list, lock: threading.Lock, max_lines: int = LOG_BUFFER_MAX_LINES):
        super().__init__()
        self._buffer = buffer
        self._lock = lock
        self._max_lines = max_lines
        self.setFormatter(logging.Formatter(_FORMAT))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            with self._lock:
                self._buffer.append(msg)
                while len(self._buffer) > self._max_lines:
                    self._buffer.pop(0)
        except Exception:
            self.handleError(record)


# Shared buffer and lock; populated by InMemoryLogHandler when attached to root logger
_log_lines: list[str] = []
_log_lock = threading.Lock()


def get_log_buffer() -> tuple[list[str], threading.Lock]:
    """Return the shared log buffer and its lock (for reading)."""
    return _log_lines, _log_lock


def get_log_lines() -> list[str]:
    """Return a copy of the current log lines (thread-safe)."""
    with _log_lock:
        return list(_log_lines)


def install_log_buffer_handler(max_lines: int = LOG_BUFFER_MAX_LINES) -> None:
    """Add InMemoryLogHandler to the root logger. Call from main.py on startup."""
    root = logging.getLogger()
    handler = InMemoryLogHandler(_log_lines, _log_lock, max_lines=max_lines)
    handler.setLevel(logging.DEBUG)
    root.addHandler(handler)

"""Process-local progress probes; a live thread alone is not a health signal."""
import threading
import time

_progress = {}
_lock = threading.Lock()


def beat(name):
    with _lock:_progress[name] = time.monotonic()


def state(name, thread, max_age=600):
    if not thread or not thread.is_alive():return 'offline'
    with _lock:last = _progress.get(name)
    return 'online' if last is not None and time.monotonic()-last < max_age else 'stalled'

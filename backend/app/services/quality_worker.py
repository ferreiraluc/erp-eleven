"""Daily quality work is separate from checkout and notification delivery."""
import logging
from .system_quality import run_once
from .worker_health import beat

logger = logging.getLogger(__name__)


def main(stop, health_provider=None):
    while not stop.is_set():
        beat('quality')
        try:
            run_once(stop, health_provider=health_provider)
        except Exception as error:
            logger.error('Daily quality review failed (%s); durable lease retained.', type(error).__name__)
        stop.wait(30)

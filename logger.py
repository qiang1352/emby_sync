import os, logging, time
from datetime import timezone, timedelta
from logging.handlers import TimedRotatingFileHandler
import coloredlogs

LOG_DIR = "/app/logs"
os.makedirs(LOG_DIR, exist_ok=True)

BEIJING = timezone(timedelta(hours=8))
logging.Formatter.converter = lambda *args: time.gmtime(time.time() + 8 * 3600)

class SamplingFilter(logging.Filter):
    def __init__(self):
        super().__init__()
        self._last = {}

    def filter(self, record):
        lib = getattr(record, "library", None)
        if not lib:
            return True
        now = time.time()
        first = self._last.setdefault(lib, now)
        if now - first > 300:
            self._last[lib] = now
            return True
        return False

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    coloredlogs.install(level="INFO", logger=logger,
                        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    file_handler = TimedRotatingFileHandler(os.path.join(LOG_DIR, "app.log"),
                                            when="midnight", backupCount=14, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s %(funcName)s:%(lineno)d | %(message)s"))
    file_handler.addFilter(SamplingFilter())
    logger.addHandler(file_handler)
    return logger
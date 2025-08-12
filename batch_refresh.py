import time, threading, asyncio, collections
from typing import Set, List
from .logger import get_logger
from .emby_client import refresh_libraries_by_names
from .config import get
log = get_logger("batch")
DEFAULT = 5.0

class DynamicBatch:
    def __init__(self):
        cfg = get()
        self.base = cfg.get("cooldown_seconds", DEFAULT)
        self.dynamic = cfg.get("dynamic_window", True)
        self.min_w = cfg.get("min_window", 2)
        self.max_w = cfg.get("max_window", 15)
        self._pending: Set[str] = set()
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()
        self._bucket = collections.deque()
        self._last_fire = 0

    def _window(self) -> float:
        if not self.dynamic:
            return self.base
        now = time.time()
        while self._bucket and self._bucket[0] < now - 60:
            self._bucket.popleft()
        count = len(self._bucket)
        return max(self.min_w, min(self.max_w, count / 10))

    def push(self, library: str):
        with self._lock:
            self._pending.add(library)
            self._bucket.append(time.time())
            if self._timer is None:
                w = self._window()
                self._timer = threading.Timer(w, self._fire)
                self._timer.start()
                log.debug("计划 %.1f 秒后刷新：%s", w, library)

    def _fire(self):
        with self._lock:
            libs = list(self._pending)
            self._pending.clear()
            self._timer = None
            self._last_fire = time.time()
        if libs:
            asyncio.run(refresh_libraries_by_names(libs))

batch = DynamicBatch()
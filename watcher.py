import os, time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .logger import get_logger
from .config import get
from .batch_refresh import batch
log = get_logger("watcher")
cfg = get()

class LibraryHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self.root = Path(cfg["cloudsync_root"]).expanduser().resolve()
        self.libs = set(cfg["libraries"])
        self.inc = {e.lower() for e in cfg.get("include_extensions", [])}
        self.exc = {e.lower() for e in cfg.get("exclude_extensions", [])}
        log.info("监控根目录：%s", self.root)

    def _should_handle(self, path: Path) -> str | None:
        try:
            rel = path.relative_to(self.root)
        except ValueError:
            return None
        if not rel.parts or rel.parts[0] not in self.libs:
            return None
        ext = path.suffix.lower()
        if ext not in self.inc or ext in self.exc:
            return None
        return rel.parts[0]

    def _handle(self, event):
        lib = self._should_handle(Path(event.src_path))
        if not lib:
            return
        log.info("检测到变更：%s (%s)", event.src_path, event.event_type, extra={"library": lib})
        batch.push(lib)

    def on_created(self, event): self._handle(event)
    def on_deleted(self, event): self._handle(event)
    def on_modified(self, event):
        if not event.is_directory:
            self._handle(event)

def start_watch():
    root = Path(get()["cloudsync_root"]).expanduser().resolve()
    observers = []
    for lib in get()["libraries"]:
        path = root / lib
        if not path.exists():
            log.warning("库目录不存在：%s", path)
            continue
        handler = LibraryHandler()
        obs = Observer()
        obs.schedule(handler, str(path), recursive=True)
        obs.start()
        observers.append(obs)
    log.info("文件监控已启动，共 %d 个库", len(observers))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("停止监控")
    finally:
        for obs in observers:
            obs.stop()
            obs.join()
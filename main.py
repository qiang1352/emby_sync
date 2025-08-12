from .logger import get_logger
from .watcher import start_watch
if __name__ == "__main__":
    log = get_logger("main")
    log.info("==== emby-sync 启动 ====")
    start_watch()
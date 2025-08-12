import os, time, yaml
from typing import Dict, Any
from .logger import get_logger
log = get_logger("config")
_CONFIG_FILE = "/app/config/settings.yml"
_last_mtime = 0
_cached_conf: Dict[str, Any] = {}

def _load() -> Dict[str, Any]:
    global _last_mtime, _cached_conf
    try:
        mtime = os.path.getmtime(_CONFIG_FILE)
    except FileNotFoundError:
        log.error("配置文件不存在")
        raise
    if mtime == _last_mtime:
        return _cached_conf
    log.info("重新加载配置")
    with open(_CONFIG_FILE, encoding="utf-8") as f:
        _cached_conf = yaml.safe_load(f) or {}
    _last_mtime = mtime
    return _cached_conf

def get() -> Dict[str, Any]:
    return _load()
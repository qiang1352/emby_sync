#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
emby_sync 最终可运行完整版
- 监控 /media 及子目录
- 支持目录/文件增删改
- 日志轮转、冷却、文件过滤、路径映射、无 RuntimeWarning
"""

import asyncio
import logging
import logging.handlers
import os
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import httpx
import pytz
import yaml
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

CONFIG_FILE = "config/config.yaml"
CN_TZ = pytz.timezone("Asia/Shanghai")

# 全局：把 watchdog 线程任务安全送回主事件循环
_TASK_QUEUE: asyncio.Queue = asyncio.Queue()


# --------------------------------------------------
def now_str() -> str:
    return datetime.now(CN_TZ).strftime("%Y-%m-%d %H:%M:%S")


class Config:
    def __init__(self, path: str):
        with open(path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        self.emby_host: str = cfg["emby"]["host"].rstrip("/")
        self.emby_key: str = cfg["emby"]["api_key"]
        self.libraries: Dict[str, str] = cfg["emby"]["libraries"]

        watch = cfg["watch"]
        self.watch_root: str = watch["root_path"]
        self.cooldown: int = watch["cooldown_seconds"]
        self.suffix_whitelist: Optional[List[str]] = watch.get("suffix_whitelist")
        self.suffix_blacklist: Optional[List[str]] = watch.get("suffix_blacklist")
        if self.suffix_whitelist and self.suffix_blacklist:
            raise ValueError("suffix_whitelist 与 suffix_blacklist 只能二选一")
        for lst in (self.suffix_whitelist, self.suffix_blacklist):
            if lst:
                lst[:] = [s.lower() for s in lst]

        log = cfg["log"]
        self.log_level: str = log["level"].upper()
        self.log_file: str = log["file_path"]
        self.log_max_bytes: int = log.get("max_bytes", 10 * 1024 * 1024)
        self.log_backup_count: int = log.get("backup_count", 5)

    def validate(self):
        assert self.emby_key != "YOUR_API_KEY_HERE", "请填写正确的 emby api_key"
        for name, rel_path in self.libraries.items():
            abs_path = Path(self.watch_root) / rel_path
            if not abs_path.is_dir():
                raise FileNotFoundError(f"容器内目录不存在: {abs_path} ({name})")


class EmbyClient:
    def __init__(self, host: str, api_key: str):
        self.host = host
        self.key = api_key
        self.client = httpx.AsyncClient(timeout=10)

    async def refresh_library(self, lib_name: str) -> bool:
        try:
            url = f"{self.host}/emby/Library/Refresh"
            params = {"api_key": self.key}
            resp = await self.client.post(url, params=params)
            if resp.status_code == 204:
                logger.info("已通知 Emby 刷新媒体库【%s】", lib_name)
                return True
            logger.error("Emby 刷新失败【%s】状态码：%s", lib_name, resp.status_code)
            return False
        except Exception as e:
            logger.exception("Emby 刷新异常【%s】%s", lib_name, e)
            return False


# --------------------------------------------------
class EventHandler(FileSystemEventHandler):
    def __init__(self, config: Config, emby: EmbyClient):
        super().__init__()
        self.config = config
        self.emby = emby
        self.pending: Dict[str, float] = defaultdict(float)

    def _should_ignore(self, event: FileSystemEvent) -> bool:
        if event.is_directory:
            return False
        suffix = Path(event.src_path).suffix.lower()
        if self.config.suffix_whitelist:
            return suffix not in self.config.suffix_whitelist
        if self.config.suffix_blacklist:
            return suffix in self.config.suffix_blacklist
        return False

    def dispatch(self, event: FileSystemEvent):
        logger.debug("RAW_EVENT: %s %s is_dir=%s",
                     event.event_type, event.src_path, event.is_directory)
        if self._should_ignore(event):
            logger.debug("忽略文件：%s", event.src_path)
            return
        if event.is_directory and event.event_type == "modified":
            return
        path = Path(event.src_path)
        lib = self._match_library(path)
        if lib:
            logger.info("检测到变化，计划刷新库【%s】：%s %s",
                        lib, event.event_type, event.src_path)
            self._schedule_refresh(lib)

    def _match_library(self, path: Path) -> Optional[str]:
        try:
            path = path.resolve()
            root = Path(self.config.watch_root).resolve()
            if root not in path.parents and path != root:
                return None
            top_dir = path.relative_to(root).parts[0]
            for name, rel_lib in self.config.libraries.items():
                if rel_lib == top_dir:
                    return name
        except ValueError:
            # 目录已被删除，用前缀兜底
            path_str = str(path)
            for name, rel_lib in self.config.libraries.items():
                if path_str.startswith(str(Path(self.config.watch_root) / rel_lib)):
                    return name
        return None

    def _schedule_refresh(self, lib_name: str):
        now = time.time()
        if now - self.pending[lib_name] > self.config.cooldown:
            self.pending[lib_name] = now
            _TASK_QUEUE.put_nowait(self._batch_refresh())

    async def _batch_refresh(self):
        logger.debug("开始执行批量刷新任务")
        await asyncio.sleep(self.config.cooldown)
        libs = list(self.pending.keys())
        for lib in libs:
            await self.emby.refresh_library(lib)
            self.pending.pop(lib, None)


# --------------------------------------------------
async def queue_worker():
    """常驻消费者：从线程安全队列取协程并调度"""
    while True:
        coro = await _TASK_QUEUE.get()
        if coro is None:
            break
        asyncio.create_task(coro)


# --------------------------------------------------
def setup_logger(cfg: Config) -> logging.Logger:
    os.makedirs(Path(cfg.log_file).parent, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        cfg.log_file,
        maxBytes=cfg.log_max_bytes,
        backupCount=cfg.log_backup_count,
        encoding="utf-8"
    )
    console = logging.StreamHandler()
    logging.basicConfig(
        level=getattr(logging, cfg.log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[handler, console],
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.Formatter.converter = lambda *args: datetime.now(CN_TZ).timetuple()
    return logging.getLogger("emby_sync")


# --------------------------------------------------
async def main():
    cfg = Config(CONFIG_FILE)
    cfg.validate()
    global logger
    logger = setup_logger(cfg)
    logger.info("emby_sync 启动成功，监控目录：%s", cfg.watch_root)

#    worker_task = asyncio.create_task(queue_worker())

    emby = EmbyClient(cfg.emby_host, cfg.emby_key)
    handler = EventHandler(cfg, emby)
    observer = Observer()
    observer.schedule(handler, cfg.watch_root, recursive=True)
    observer.start()

    # 创建一个事件来处理优雅退出
    stop_event = asyncio.Event()
    
    try:
        while not stop_event.is_set():
            # 检查队列是否有任务
            try:
                coro = _TASK_QUEUE.get_nowait()
                asyncio.create_task(coro)
            except asyncio.QueueEmpty:
                pass  # 队列为空，继续等待

            # 等待一小段时间，避免无限循环占用CPU
            await asyncio.sleep(0.1)

    except KeyboardInterrupt:
        logger.info("收到退出信号，正在关闭...")
    finally:
        observer.stop()
        observer.join()
        
        # 确保队列中的最后一个任务被执行
        while not _TASK_QUEUE.empty():
            coro = _TASK_QUEUE.get_nowait()
            await coro

        # 优雅关闭
        await emby.client.aclose()
        logger.info("程序已安全退出。")


if __name__ == "__main__":
    asyncio.run(main())

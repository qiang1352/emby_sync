import httpx, asyncio, time
from .logger import get_logger
from .config import get
log = get_logger("emby_client")
_cfg = get()["emby"]
URL, KEY = _cfg["url"].rstrip("/"), _cfg["api_key"]
_client = httpx.AsyncClient(timeout=15, limits=httpx.Limits(max_keepalive_connections=20))
_cache: dict[str, str] = {}
_cache_expire = 0

async def _get_lib_map() -> dict[str, str]:
    global _cache_expire
    now = time.time()
    if _cache_expire > now:
        return _cache
    r = await _client.get(f"{URL}/emby/Library/VirtualFolders", params={"api_key": KEY})
    r.raise_for_status()
    _cache = {lib["Name"]: lib["ItemId"] for lib in r.json()}
    if len(_cache) != len(r.json()):
        _cache_expire = 0
    else:
        _cache_expire = now + 1800
    return _cache

async def refresh_libraries_by_names(names: list[str]):
    try:
        lib_map = await _get_lib_map()
        ids = [lib_map[n] for n in names if n in lib_map]
        if ids:
            await _client.post(f"{URL}/emby/Library/Refresh",
                               params={"api_key": KEY},
                               json={"Ids": ids,
                                     "ReplaceAllImages": False,
                                     "ReplaceAllMetadata": False})
            log.info("已批量刷新 %d 个库：%s", len(ids), names)
    except Exception as e:
        log.exception("批量刷新失败: %s", e)
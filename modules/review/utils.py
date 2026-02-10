import hashlib
import random
from pathlib import Path
from typing import Dict

import aiofiles
from httpx import AsyncClient

from .constants import HEADERS

HTTPX_CLIENT = AsyncClient(headers=HEADERS)


async def get_res(url_base: str, path: str, bust_cache: bool = False) -> Dict:
    HTTPX_CLIENT.headers["Referer"] = url_base

    if url_base == "https://game.maj-soul.com/":
        url = f"{url_base}/1/{path}"
    else:
        url = f"{url_base}{path}"

    cache_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
    if bust_cache:
        url += f"?randv={str(random.random())[2:]}"

    cache_dir = Path(".cache")
    cache_dir.mkdir(exist_ok=True)
    cache_file = cache_dir / cache_hash

    resp = await HTTPX_CLIENT.get(url)
    resp.raise_for_status()
    async with aiofiles.open(cache_file, "wb") as f:
        await f.write(resp.content)

    return resp.json()

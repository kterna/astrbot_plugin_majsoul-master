import asyncio
import json
import time
from pathlib import Path
from typing import List, Optional

import msgspec

from .model import AccountInfo


class AccountStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    async def _load(self) -> List[AccountInfo]:
        async with self._lock:
            text = self.path.read_text(encoding="utf-8") if self.path.exists() else "[]"
            raw = json.loads(text or "[]")
            return [AccountInfo(**item) for item in raw]

    async def _save(self, accounts: List[AccountInfo]) -> None:
        async with self._lock:
            raw = [msgspec.to_builtins(a) for a in accounts]
            self.path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    async def list_accounts(self) -> List[AccountInfo]:
        return await self._load()

    async def add_or_update(
        self,
        uid: str,
        username: str,
        password: str,
        token: str,
        nickname: str,
        status: str = "ok",
        error: str = "",
    ) -> None:
        accounts = await self._load()
        now = int(time.time())

        for i, account in enumerate(accounts):
            if account.uid == uid or account.username == username:
                accounts[i] = AccountInfo(
                    uid=uid,
                    username=username,
                    password=password,
                    token=token,
                    nickname=nickname,
                    last_status=status,
                    last_error=error,
                    updated_at=now,
                )
                await self._save(accounts)
                return

        accounts.append(
            AccountInfo(
                uid=uid,
                username=username,
                password=password,
                token=token,
                nickname=nickname,
                last_status=status,
                last_error=error,
                updated_at=now,
            )
        )
        await self._save(accounts)

    async def update_status(self, uid: str, status: str, error: str = "") -> None:
        accounts = await self._load()
        now = int(time.time())
        changed = False
        for i, account in enumerate(accounts):
            if account.uid == uid:
                accounts[i] = AccountInfo(
                    uid=account.uid,
                    username=account.username,
                    password=account.password,
                    token=account.token,
                    nickname=account.nickname,
                    last_status=status,
                    last_error=error,
                    updated_at=now,
                )
                changed = True
                break
        if changed:
            await self._save(accounts)

    async def update_token(self, uid: str, token: str, nickname: Optional[str] = None) -> None:
        accounts = await self._load()
        now = int(time.time())
        changed = False
        for i, account in enumerate(accounts):
            if account.uid == uid:
                accounts[i] = AccountInfo(
                    uid=account.uid,
                    username=account.username,
                    password=account.password,
                    token=token,
                    nickname=nickname or account.nickname,
                    last_status="ok",
                    last_error="",
                    updated_at=now,
                )
                changed = True
                break
        if changed:
            await self._save(accounts)

    async def remove(self, identifier: str) -> bool:
        accounts = await self._load()

        idx: Optional[int] = None
        if identifier.isdigit():
            index = int(identifier) - 1
            if 0 <= index < len(accounts):
                idx = index

        if idx is None:
            for i, account in enumerate(accounts):
                if account.uid == identifier or account.username == identifier:
                    idx = i
                    break

        if idx is None:
            return False

        accounts.pop(idx)
        await self._save(accounts)
        return True

    @staticmethod
    def masked(username: str) -> str:
        if len(username) <= 4:
            return username[0] + "***"
        return username[:2] + "***" + username[-2:]

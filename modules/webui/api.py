import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Callable

from astrbot.api import logger
from quart import jsonify, request, send_file

from ..review.majsoul_connection import create_connection


PLUGIN_NAME = "astrbot_plugin_majsoul"


class MajsoulWebUIApi:
    """为 AstrBot 插件 Pages 提供雀魂管理 API。"""

    def __init__(self, plugin: Any):
        self.plugin = plugin
        self.review_service = plugin.review_service
        self.paipu_analysis = plugin.paipu_analysis
        self.config = plugin.config or {}
        self.timeout_seconds = int(self.config.get("webui_timeout_seconds", 180))
        self.error_preview_length = int(
            self.config.get("webui_error_preview_length", 240)
        )
        self._account_login_lock = asyncio.Lock()

    def register(self, context: Any) -> None:
        routes: list[tuple[str, Callable, list[str], str]] = [
            ("status", self.status, ["GET"], "雀魂 WebUI 概览状态"),
            ("accounts", self.accounts, ["GET"], "雀魂 WebUI 账号池列表"),
            ("accounts/login", self.accounts_login, ["POST"], "雀魂 WebUI 添加或更新国服账号"),
            ("accounts/delete", self.accounts_delete, ["POST"], "雀魂 WebUI 删除账号池账号"),
            ("accounts/test", self.accounts_test, ["POST"], "雀魂 WebUI 测试账号可用性"),
            ("paipus", self.paipus, ["GET"], "雀魂 WebUI 牌谱缓存列表"),
            ("paipus/fetch", self.paipus_fetch, ["POST"], "雀魂 WebUI 拉取原始牌谱"),
            ("paipus/detail", self.paipus_detail, ["GET"], "雀魂 WebUI 牌谱详情"),
            ("paipus/download", self.paipus_download, ["GET"], "雀魂 WebUI 下载原始牌谱"),
            ("paipus/delete", self.paipus_delete, ["POST"], "雀魂 WebUI 删除牌谱缓存"),
            ("analysis/rounds", self.analysis_rounds, ["GET"], "雀魂 WebUI 牌谱局列表分析"),
            ("analysis/round-result", self.analysis_round_result, ["GET"], "雀魂 WebUI 单局结果分析"),
            ("analysis/turn-state", self.analysis_turn_state, ["GET"], "雀魂 WebUI 巡目状态分析"),
            ("analysis/player-trace", self.analysis_player_trace, ["GET"], "雀魂 WebUI 玩家摸打轨迹"),
        ]
        for suffix, handler, methods, desc in routes:
            context.register_web_api(
                f"/{PLUGIN_NAME}/{suffix}",
                handler,
                methods,
                desc,
            )

    def _enabled(self) -> bool:
        return bool(self.config.get("webui_enable", True))

    def _ok(self, data: Any = None, message: str = ""):
        return jsonify({"ok": True, "data": data, "message": message})

    def _error(self, message: str, data: Any = None, status_code: int = 200):
        response = jsonify({"ok": False, "data": data, "message": message})
        response.status_code = status_code
        return response

    async def _payload(self) -> dict[str, Any]:
        if request.method == "GET":
            return {key: value for key, value in request.args.items()}
        body = await request.get_json(silent=True)
        return body if isinstance(body, dict) else {}

    @staticmethod
    def _preview(value: Any, limit: int = 160) -> str:
        text = str(value or "").strip()
        if len(text) <= limit:
            return text
        return text[:limit] + "..."

    def _mask_account_ref(self, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        if "@" in text:
            return self.review_service.store.masked(text)
        if len(text) > 12 and not text.isdigit():
            return text[:4] + "***" + text[-4:]
        return text

    def _debug_api(self, action: str, **fields: Any) -> None:
        safe_fields = {
            key: value
            for key, value in fields.items()
            if value is not None and value != ""
        }
        if safe_fields:
            logger.debug(f"[majsoul-webui] {action}: {safe_fields}")
        else:
            logger.debug(f"[majsoul-webui] {action}")

    async def _guarded(self, fn: Callable[[], Any]):
        if not self._enabled():
            self._debug_api("api_blocked", reason="webui_disabled")
            return self._error("WebUI 功能已在插件配置中关闭")
        try:
            result = fn()
            if asyncio.iscoroutine(result):
                result = await result
            return result
        except Exception as exc:
            logger.error(f"[majsoul-webui] API 执行异常: {exc}", exc_info=True)
            return self._error(f"执行失败: {exc}")

    def _format_time(self, ts: float | int | None) -> str:
        if not ts:
            return ""
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(ts)))

    def _truncate_error(self, value: str) -> str:
        text = str(value or "")
        if len(text) <= self.error_preview_length:
            return text
        return text[: self.error_preview_length] + "..."

    def _paipu_dir(self) -> Path:
        self.review_service.paipu_dir.mkdir(parents=True, exist_ok=True)
        return self.review_service.paipu_dir.resolve()

    def _safe_paipu_path(self, file_name: str) -> Path:
        raw_name = str(file_name or "").strip()
        if not raw_name:
            raise ValueError("缺少 file_name")
        if "/" in raw_name or "\\" in raw_name:
            raise ValueError("file_name 不能包含路径分隔符")
        path = (self._paipu_dir() / raw_name).resolve()
        paipu_dir = self._paipu_dir()
        if os.path.commonpath([str(path), str(paipu_dir)]) != str(paipu_dir):
            raise ValueError("非法牌谱路径")
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"找不到牌谱缓存文件: {raw_name}")
        return path

    def _load_raw(self, path: Path) -> dict[str, Any]:
        with open(path, "r", encoding="utf-8") as file:
            raw = json.load(file)
        if not isinstance(raw, dict):
            raise ValueError("raw.json 格式不是 JSON object")
        return raw

    def _game_id_from_path(self, path: Path, raw: dict[str, Any] | None = None) -> str:
        if raw:
            game_id = raw.get("game_id")
            if game_id:
                return str(game_id)
        name = path.name
        if name.endswith(" - raw.json"):
            return name[: -len(" - raw.json")]
        return path.stem

    def _raw_relative_path(self, path: Path) -> str:
        return self.review_service.to_repo_relative_path(path)

    def _brief_from_raw(self, path: Path, raw: dict[str, Any]) -> dict[str, Any]:
        rounds = raw.get("log") or []
        players = [str(item) for item in (raw.get("name") or [])]
        return {
            "file_name": path.name,
            "game_id": self._game_id_from_path(path, raw),
            "raw_json_path": self._raw_relative_path(path),
            "players": players,
            "round_count": len(rounds) if isinstance(rounds, list) else 0,
            "size_bytes": path.stat().st_size,
            "modified_at": self._format_time(path.stat().st_mtime),
            "modified_ts": int(path.stat().st_mtime),
        }

    def _read_paipu_briefs(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for path in sorted(self._paipu_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                raw = self._load_raw(path)
                items.append(self._brief_from_raw(path, raw))
            except Exception as exc:
                items.append(
                    {
                        "file_name": path.name,
                        "game_id": path.stem,
                        "raw_json_path": self._raw_relative_path(path),
                        "players": [],
                        "round_count": 0,
                        "size_bytes": path.stat().st_size,
                        "modified_at": self._format_time(path.stat().st_mtime),
                        "modified_ts": int(path.stat().st_mtime),
                        "error": self._truncate_error(str(exc)),
                    }
                )
        return items

    async def _account_items(self) -> list[dict[str, Any]]:
        accounts = await self.review_service.store.list_accounts()
        return [
            {
                "index": index,
                "uid": account.uid,
                "username_masked": self.review_service.store.masked(account.username),
                "nickname": account.nickname,
                "has_token": bool(account.token),
                "last_status": account.last_status,
                "last_error": self._truncate_error(account.last_error),
                "updated_at": self._format_time(account.updated_at),
                "updated_ts": account.updated_at,
            }
            for index, account in enumerate(accounts, 1)
        ]

    async def _resolve_account(self, identifier: str):
        accounts = await self.review_service.store.list_accounts()
        target = str(identifier or "").strip()
        if not target:
            raise ValueError("缺少账号标识")
        if target.isdigit():
            idx = int(target) - 1
            if 0 <= idx < len(accounts):
                return accounts[idx]
        for account in accounts:
            if account.uid == target or account.username == target:
                return account
        raise ValueError("未找到对应账号，请使用序号/uid/用户名")

    async def status(self):
        return await self._guarded(self._status)

    async def _status(self):
        accounts = await self._account_items()
        paipus = self._read_paipu_briefs()
        failed_accounts = [item for item in accounts if item["last_status"] != "ok"]
        total_size = sum(int(item.get("size_bytes") or 0) for item in paipus)
        latest = max((int(item.get("modified_ts") or 0) for item in paipus), default=0)
        self._debug_api(
            "status",
            accounts_total=len(accounts),
            accounts_failed=len(failed_accounts),
            paipus_total=len(paipus),
            paipus_total_size_bytes=total_size,
        )
        return self._ok(
            {
                "plugin_name": PLUGIN_NAME,
                "version": "1.5.3",
                "plugin_root": str(self.plugin.plugin_root),
                "data_root": str(self.plugin.plugin_data_dir),
                "webui_enable": self._enabled(),
                "accounts": {
                    "total": len(accounts),
                    "ok": len(accounts) - len(failed_accounts),
                    "failed": len(failed_accounts),
                    "recent_errors": failed_accounts[:5],
                },
                "paipus": {
                    "total": len(paipus),
                    "total_size_bytes": total_size,
                    "latest_modified_at": self._format_time(latest),
                },
            }
        )

    async def accounts(self):
        return await self._guarded(self._accounts)

    async def _accounts(self):
        items = await self._account_items()
        self._debug_api("accounts_list", count=len(items))
        return self._ok({"items": items})

    async def accounts_login(self):
        return await self._guarded(self._accounts_login)

    async def _accounts_login(self):
        payload = await self._payload()
        username = str(payload.get("username") or "").strip()
        password = str(payload.get("password") or "").strip()
        self._debug_api(
            "accounts_login_start",
            username=self._mask_account_ref(username),
            password_provided=bool(password),
            timeout_seconds=self.timeout_seconds,
        )
        if not username or not password:
            self._debug_api(
                "accounts_login_rejected",
                username=self._mask_account_ref(username),
                reason="missing_username_or_password",
            )
            return self._error("请输入用户名和密码")
        if self._account_login_lock.locked():
            self._debug_api(
                "accounts_login_rejected",
                username=self._mask_account_ref(username),
                reason="login_already_running",
            )
            return self._error("已有账号登录验证正在进行，请稍后")
        async with self._account_login_lock:
            success, message = await asyncio.wait_for(
                self.review_service.add_cn_account(username, password),
                timeout=self.timeout_seconds,
            )
        if not success:
            self._debug_api(
                "accounts_login_failed",
                username=self._mask_account_ref(username),
                message=self._truncate_error(message),
            )
            return self._error(message)
        accounts = await self._account_items()
        self._debug_api(
            "accounts_login_success",
            username=self._mask_account_ref(username),
            accounts_total=len(accounts),
            message=message,
        )
        return self._ok({"accounts": accounts}, message)

    async def accounts_delete(self):
        return await self._guarded(self._accounts_delete)

    async def _accounts_delete(self):
        payload = await self._payload()
        identifier = str(payload.get("identifier") or "").strip()
        self._debug_api(
            "accounts_delete_start",
            identifier=self._mask_account_ref(identifier),
        )
        if not identifier:
            self._debug_api("accounts_delete_rejected", reason="missing_identifier")
            return self._error("请输入要删除的账号序号、uid 或用户名")
        success, message = await self.review_service.remove_account(identifier)
        if not success:
            self._debug_api(
                "accounts_delete_failed",
                identifier=self._mask_account_ref(identifier),
                message=message,
            )
            return self._error(message)
        accounts = await self._account_items()
        self._debug_api(
            "accounts_delete_success",
            identifier=self._mask_account_ref(identifier),
            accounts_total=len(accounts),
        )
        return self._ok({"accounts": accounts}, message)

    async def accounts_test(self):
        return await self._guarded(self._accounts_test)

    async def _accounts_test(self):
        payload = await self._payload()
        identifier = payload.get("identifier") or ""
        self._debug_api(
            "accounts_test_start",
            identifier=self._mask_account_ref(identifier),
            timeout_seconds=self.timeout_seconds,
        )
        account = await self._resolve_account(identifier)
        self._debug_api(
            "accounts_test_resolved",
            uid=account.uid,
            username=self._mask_account_ref(account.username),
            nickname=account.nickname,
            has_token=bool(account.token),
        )
        conn = None
        try:
            if account.token:
                self._debug_api("accounts_test_login_method", uid=account.uid, method="access_token")
                try:
                    conn = await asyncio.wait_for(
                        create_connection(access_token=account.token),
                        timeout=self.timeout_seconds,
                    )
                except Exception as token_exc:
                    self._debug_api(
                        "accounts_test_token_failed_fallback_password",
                        uid=account.uid,
                        error=f"{token_exc.__class__.__name__}: {self._truncate_error(str(token_exc))}",
                    )
                    conn = await asyncio.wait_for(
                        create_connection(username=account.username, password=account.password),
                        timeout=self.timeout_seconds,
                    )
            else:
                self._debug_api("accounts_test_login_method", uid=account.uid, method="password")
                conn = await asyncio.wait_for(
                    create_connection(username=account.username, password=account.password),
                    timeout=self.timeout_seconds,
                )
            await self.review_service.store.update_token(
                account.uid,
                conn.access_token,
                conn.nick_name,
            )
            await self.review_service.store.update_status(account.uid, "ok", "")
            accounts = await self._account_items()
            self._debug_api(
                "accounts_test_success",
                uid=account.uid,
                account_id=conn.account_id,
                nickname=conn.nick_name,
                token_refreshed=bool(conn.access_token),
            )
            return self._ok({"accounts": accounts}, "账号测试成功")
        except Exception as exc:
            await self.review_service.store.update_status(
                account.uid,
                "failed",
                str(exc),
            )
            self._debug_api(
                "accounts_test_failed",
                uid=account.uid,
                error=f"{exc.__class__.__name__}: {self._truncate_error(str(exc))}",
            )
            return self._error(f"账号测试失败: {exc}")
        finally:
            await self.review_service._close_conn(conn)

    async def paipus(self):
        return await self._guarded(self._paipus)

    async def _paipus(self):
        payload = await self._payload()
        keyword = str(payload.get("q") or "").strip().lower()
        items = self._read_paipu_briefs()
        total = len(items)
        if keyword:
            items = [
                item
                for item in items
                if keyword in item["file_name"].lower()
                or keyword in item["game_id"].lower()
                or any(keyword in str(player).lower() for player in item["players"])
            ]
        self._debug_api(
            "paipus_list",
            keyword=self._preview(keyword, 80),
            total=total,
            returned=len(items),
        )
        return self._ok({"items": items})

    async def paipus_fetch(self):
        return await self._guarded(self._paipus_fetch)

    async def _paipus_fetch(self):
        payload = await self._payload()
        source = str(payload.get("source") or "").strip()
        parsed_game_id = self.review_service.parse_game_id(source) if source else None
        self._debug_api(
            "paipus_fetch_start",
            source=self._preview(source),
            parsed_game_id=parsed_game_id,
            timeout_seconds=self.timeout_seconds,
        )
        if not source:
            self._debug_api("paipus_fetch_rejected", reason="missing_source")
            return self._error("请输入牌谱 URL 或 paipu_id")
        success, message, fetch_result = await asyncio.wait_for(
            self.review_service.fetch_raw_paipu(source),
            timeout=self.timeout_seconds,
        )
        if not success or fetch_result is None:
            self._debug_api(
                "paipus_fetch_failed",
                parsed_game_id=parsed_game_id,
                message=self._truncate_error(message),
            )
            return self._error(message)
        rounds = self.paipu_analysis.list_rounds_from_raw(
            fetch_result.raw,
            game_id=fetch_result.game_id,
            raw_json_path=fetch_result.raw_path_relative,
        )
        self._debug_api(
            "paipus_fetch_success",
            game_id=fetch_result.game_id,
            file_name=fetch_result.raw_path.name,
            cache_hit=fetch_result.cache_hit,
            round_count=len(rounds) if isinstance(rounds, list) else None,
        )
        return self._ok(
            {
                "game_id": fetch_result.game_id,
                "file_name": fetch_result.raw_path.name,
                "raw_json_path": fetch_result.raw_path_relative,
                "cache_hit": fetch_result.cache_hit,
                "summary": rounds,
            },
            "牌谱拉取成功",
        )

    async def paipus_detail(self):
        return await self._guarded(self._paipus_detail)

    async def _paipus_detail(self):
        payload = await self._payload()
        file_name = str(payload.get("file_name") or "")
        self._debug_api("paipus_detail_start", file_name=self._preview(file_name))
        path = self._safe_paipu_path(file_name)
        raw = self._load_raw(path)
        brief = self._brief_from_raw(path, raw)
        rounds = self.paipu_analysis.list_rounds_from_raw(
            raw,
            game_id=brief["game_id"],
            raw_json_path=brief["raw_json_path"],
        )
        self._debug_api(
            "paipus_detail_success",
            file_name=path.name,
            game_id=brief["game_id"],
            round_count=len(rounds) if isinstance(rounds, list) else None,
            size_bytes=brief["size_bytes"],
        )
        return self._ok({"paipu": brief, "rounds": rounds})

    async def paipus_download(self):
        if not self._enabled():
            self._debug_api("paipus_download_blocked", reason="webui_disabled")
            return self._error("WebUI 功能已在插件配置中关闭")
        try:
            payload = await self._payload()
            file_name = str(payload.get("file_name") or "")
            self._debug_api("paipus_download_start", file_name=self._preview(file_name))
            path = self._safe_paipu_path(file_name)
            self._debug_api(
                "paipus_download_success",
                file_name=path.name,
                size_bytes=path.stat().st_size,
            )
            try:
                return await send_file(
                    str(path),
                    as_attachment=True,
                    attachment_filename=path.name,
                    mimetype="application/json",
                )
            except TypeError:
                return await send_file(
                    str(path),
                    as_attachment=True,
                    download_name=path.name,
                    mimetype="application/json",
                )
        except Exception as exc:
            self._debug_api(
                "paipus_download_failed",
                error=f"{exc.__class__.__name__}: {self._truncate_error(str(exc))}",
            )
            logger.error(f"[majsoul-webui] 下载牌谱失败: {exc}", exc_info=True)
            return self._error(f"下载失败: {exc}")

    async def paipus_delete(self):
        return await self._guarded(self._paipus_delete)

    async def _paipus_delete(self):
        payload = await self._payload()
        file_name = str(payload.get("file_name") or "")
        self._debug_api("paipus_delete_start", file_name=self._preview(file_name))
        path = self._safe_paipu_path(file_name)
        path.unlink()
        items = self._read_paipu_briefs()
        self._debug_api(
            "paipus_delete_success",
            file_name=path.name,
            remaining=len(items),
        )
        return self._ok({"items": items}, "牌谱缓存已删除")

    async def _analysis_raw_payload(self) -> tuple[dict[str, Any], Path, dict[str, Any]]:
        payload = await self._payload()
        path = self._safe_paipu_path(str(payload.get("file_name") or ""))
        raw = self._load_raw(path)
        return payload, path, raw

    async def analysis_rounds(self):
        return await self._guarded(self._analysis_rounds)

    async def _analysis_rounds(self):
        _, path, raw = await self._analysis_raw_payload()
        game_id = self._game_id_from_path(path, raw)
        result = self.paipu_analysis.list_rounds_from_raw(
            raw,
            game_id=game_id,
            raw_json_path=self._raw_relative_path(path),
        )
        self._debug_api(
            "analysis_rounds",
            file_name=path.name,
            game_id=game_id,
            round_count=len(result) if isinstance(result, list) else None,
        )
        return self._ok(result)

    async def analysis_round_result(self):
        return await self._guarded(self._analysis_round_result)

    async def _analysis_round_result(self):
        payload, path, raw = await self._analysis_raw_payload()
        round_selector = str(payload.get("round_selector") or "")
        game_id = self._game_id_from_path(path, raw)
        result = self.paipu_analysis.get_round_result_from_raw(
            raw,
            round_selector=round_selector,
            game_id=game_id,
            raw_json_path=self._raw_relative_path(path),
        )
        self._debug_api(
            "analysis_round_result",
            file_name=path.name,
            game_id=game_id,
            round_selector=round_selector,
            result_type=type(result).__name__,
        )
        return self._ok(result)

    async def analysis_turn_state(self):
        return await self._guarded(self._analysis_turn_state)

    async def _analysis_turn_state(self):
        payload, path, raw = await self._analysis_raw_payload()
        round_selector = str(payload.get("round_selector") or "")
        turn_mode = str(payload.get("turn_mode") or "global")
        turn_number = int(payload.get("turn_number") or 1)
        seat = int(payload.get("seat") if str(payload.get("seat", "")).strip() else -1)
        phase = str(payload.get("phase") or "discard")
        game_id = self._game_id_from_path(path, raw)
        result = self.paipu_analysis.get_round_turn_state_from_raw(
            raw,
            round_selector=round_selector,
            turn_mode=turn_mode,
            turn_number=turn_number,
            seat=seat,
            phase=phase,
            game_id=game_id,
            raw_json_path=self._raw_relative_path(path),
        )
        self._debug_api(
            "analysis_turn_state",
            file_name=path.name,
            game_id=game_id,
            round_selector=round_selector,
            turn_mode=turn_mode,
            turn_number=turn_number,
            seat=seat,
            phase=phase,
            result_type=type(result).__name__,
        )
        return self._ok(result)

    async def analysis_player_trace(self):
        return await self._guarded(self._analysis_player_trace)

    async def _analysis_player_trace(self):
        payload, path, raw = await self._analysis_raw_payload()
        round_selector = str(payload.get("round_selector") or "")
        player_selector = str(payload.get("player_selector") or "")
        game_id = self._game_id_from_path(path, raw)
        result = self.paipu_analysis.get_player_round_trace_from_raw(
            raw,
            round_selector=round_selector,
            player_selector=player_selector,
            game_id=game_id,
            raw_json_path=self._raw_relative_path(path),
        )
        self._debug_api(
            "analysis_player_trace",
            file_name=path.name,
            game_id=game_id,
            round_selector=round_selector,
            player_selector=player_selector,
            result_type=type(result).__name__,
        )
        return self._ok(result)

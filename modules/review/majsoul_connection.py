import asyncio
import contextlib
import hashlib
import hmac
import inspect
import json
import random
import re
import uuid
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Awaitable, Callable, Dict, Optional, Union, cast

import aiofiles
import websockets.client
from astrbot.api import logger
from msgspec import ValidationError, convert

from .codec import MajsoulProtoCodec
from .constants import URL_BASE, USER_AGENT
from .lib import lq as liblq
from .model import (
    MjsLog,
    MjsLogItem,
    MajsoulConfig,
    MajsoulDecodedMessage,
    MajsoulLiqiProto,
    MajsoulResInfo,
    MajsoulVersionInfo,
)
from .remote import decode_account_id2, decode_log_id
from .tenhou.parser import MajsoulPaipuParser
from .utils import HTTPX_CLIENT, get_res

WS_OPEN_TIMEOUT_SEC = 12
RPC_TIMEOUT_SEC = 20
CLIENT_TAG = "cn"
DEFAULT_CURRENCY_PLATFORMS = [2]
UNITY_WEB_VERSION_RE = re.compile(r"WebGL-release-([0-9]+(?:\.[0-9]+)+)")
UNITY_PRODUCT_VERSION_RE = re.compile(r"productVersion\s*:\s*[\"']([^\"']+)[\"']")
ProgressCallback = Callable[[str], Optional[Awaitable[None]]]


async def _notify(progress_cb: Optional[ProgressCallback], message: str) -> None:
    logger.info(f"[majsoul-review] {message}")
    if progress_cb is None:
        return
    result = progress_cb(message)
    if inspect.isawaitable(result):
        await result


def _error_summary(error) -> str:
    if error is None:
        return "none"
    return (
        f"code={getattr(error, 'code', 0)} "
        f"u32={list(getattr(error, 'u32_params', []) or [])} "
        f"str={list(getattr(error, 'str_params', []) or [])} "
        f"json={getattr(error, 'json_param', '')!r} "
        f"level={getattr(error, 'level', 0)}"
    )


def _client_device_info() -> dict:
    return {
        "platform": "pc",
        "hardware": "pc",
        "os": "windows",
        "os_version": "win10",
        "is_browser": True,
        "software": "Chrome",
        "sale_platform": "web",
        "screen_width": 1920,
        "screen_height": 1080,
        "user_agent": USER_AGENT,
        "screen_type": 1,
    }


def _legacy_client_version_string(version_info: MajsoulVersionInfo) -> str:
    return "web-" + version_info.version.replace(".w", "")


async def _fetch_login_client_version_string(
    url_base: str,
    version_info: MajsoulVersionInfo,
) -> tuple[str, str]:
    legacy_version = _legacy_client_version_string(version_info)
    index_url = f"{url_base.rstrip('/')}/1/"
    try:
        HTTPX_CLIENT.headers["Referer"] = url_base
        resp = await HTTPX_CLIENT.get(index_url)
        resp.raise_for_status()
        html = resp.text
    except Exception as exc:
        logger.debug(
            "[majsoul-review] web client version fetch failed: "
            f"url={index_url} fallback={legacy_version} error={exc.__class__.__name__}: {exc}"
        )
        return legacy_version, "version_json"

    product_match = UNITY_PRODUCT_VERSION_RE.search(html)
    build_match = UNITY_WEB_VERSION_RE.search(html)
    unity_version = ""
    if product_match and product_match.group(1).strip():
        unity_version = product_match.group(1).strip()
    elif build_match and build_match.group(1).strip():
        unity_version = build_match.group(1).strip()
    if not unity_version:
        logger.debug(
            "[majsoul-review] web client version not found in index: "
            f"url={index_url} fallback={legacy_version}"
        )
        return legacy_version, "version_json"

    return f"web-{unity_version}", "unity_index"


def process_dict(obj):
    if is_dataclass(obj):
        return {k: process_dict(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: process_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [process_dict(i) for i in obj]
    if hasattr(obj, "__dict__"):
        return process_dict(obj.__dict__)
    if isinstance(obj, bytes):
        return str(obj)
    if isinstance(obj, (int, float, str, bool, type(None))):
        return obj
    return str(obj)


class MajsoulConnection:
    def __init__(
        self,
        endpoint: str,
        codec: MajsoulProtoCodec,
        version_info: MajsoulVersionInfo,
        client_version_string: str = "",
    ):
        self._endpoint = endpoint
        self._codec = codec
        self._ws = None
        self._dispatch_task: asyncio.Task | None = None
        self._dispatch_error: Exception | None = None
        self._req_events: dict[int, asyncio.Event] = {}
        self._res: dict[int, MajsoulDecodedMessage] = {}

        self.client_version_string = (
            client_version_string or _legacy_client_version_string(version_info)
        )
        self.client_tag = CLIENT_TAG
        self.currency_platforms = list(DEFAULT_CURRENCY_PLATFORMS)
        self.random_key = str(uuid.uuid4())

        self.account_id = 0
        self.nick_name = ""
        self.access_token = ""

    async def connect(self):
        logger.debug(
            "[majsoul-review] websocket connect meta: "
            f"endpoint={self._endpoint} origin={URL_BASE.rstrip('/')} "
            f"user_agent_set={bool(USER_AGENT)}"
        )
        self._ws = await websockets.client.connect(
            self._endpoint,
            origin=URL_BASE.rstrip("/"),
            user_agent_header=USER_AGENT,
            open_timeout=WS_OPEN_TIMEOUT_SEC,
            close_timeout=5,
        )
        self._dispatch_task = asyncio.create_task(self.dispatch_msg())

    async def close(self):
        if self._dispatch_task:
            self._dispatch_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._dispatch_task
        if self._ws:
            await self._ws.close()

    async def dispatch_msg(self):
        if self._ws is None:
            raise ConnectionError("connection is broken")

        try:
            while True:
                msg = await self._ws.recv()
                if not isinstance(msg, bytes):
                    continue
                data = self._codec.decode_message(msg)
                if data.msg_type != self._codec.RESPONSE:
                    continue
                idx = data.req_index
                if idx not in self._req_events:
                    continue
                self._res[idx] = data
                self._req_events[idx].set()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._dispatch_error = exc
            logger.error(f"majsoul dispatch task failed: {exc}", exc_info=True)
            # 唤醒所有挂起请求，避免rpc_call无限等待
            for evt in list(self._req_events.values()):
                evt.set()
            raise

    async def rpc_call(self, method_name: str, payload: dict):
        if self._ws is None:
            raise ConnectionError("connection is broken")

        idx = self._codec.index
        req = self._codec.encode_request(method_name, payload)

        evt = asyncio.Event()
        self._req_events[idx] = evt
        await self._ws.send(req)
        try:
            await asyncio.wait_for(evt.wait(), timeout=RPC_TIMEOUT_SEC)
        except asyncio.TimeoutError as exc:
            if self._dispatch_error is not None:
                raise ConnectionError(
                    f"rpc failed before response ({method_name}): {self._dispatch_error}"
                ) from self._dispatch_error
            raise TimeoutError(f"rpc timeout: {method_name}") from exc
        finally:
            if idx in self._req_events:
                del self._req_events[idx]

        if idx not in self._res:
            if self._dispatch_error is not None:
                raise ConnectionError(
                    f"rpc aborted ({method_name}): {self._dispatch_error}"
                ) from self._dispatch_error
            raise ConnectionError(f"rpc response missing: {method_name}")

        res = self._res[idx]
        del self._res[idx]
        return res.payload

    @staticmethod
    def encode_password(password: str) -> str:
        return hmac.new(b"lailai", password.encode(), hashlib.sha256).hexdigest()

    async def manual_login(
        self,
        username: str,
        password: str,
        version_info: MajsoulVersionInfo,
    ):
        password_hash = self.encode_password(password)
        logger.debug(
            "[majsoul-review] manual_login request meta: "
            f"client_version_string={self.client_version_string} "
            f"resource={version_info.version} tag={self.client_tag} "
            f"currency_platforms={self.currency_platforms}"
        )
        resp = cast(
            liblq.ResLogin,
            await self.rpc_call(
                ".lq.Lobby.login",
                {
                    "account": username,
                    "password": password_hash,
                    "reconnect": False,
                    "device": _client_device_info(),
                    "random_key": self.random_key,
                    "client_version": {"resource": version_info.version},
                    "currency_platforms": self.currency_platforms,
                    "client_version_string": self.client_version_string,
                    "gen_access_token": True,
                    "type": 0,
                    "tag": self.client_tag,
                },
            ),
        )
        if not resp.account_id:
            logger.debug(
                "[majsoul-review] manual_login failed response: "
                f"{_error_summary(resp.error)}"
            )
            raise ValueError(f"manual login failed: {_error_summary(resp.error)}")
        self.account_id = resp.account_id
        self.nick_name = resp.account.nickname
        self.access_token = resp.access_token
        logger.debug(
            "[majsoul-review] manual_login success: "
            f"account_id={self.account_id} nickname={self.nick_name} "
            f"access_token_len={len(self.access_token or '')}"
        )
        return self.account_id, self.access_token, self.nick_name

    async def access_token_login(
        self,
        version_info: MajsoulVersionInfo,
        access_token: str,
    ):
        resp = cast(
            liblq.ResOauth2Check,
            await self.rpc_call(
                ".lq.Lobby.oauth2Check",
                {"type": 0, "access_token": access_token},
            ),
        )
        logger.debug(
            "[majsoul-review] oauth2Check response: "
            f"has_account={resp.has_account} {_error_summary(resp.error)}"
        )
        if not resp.has_account:
            await asyncio.sleep(1)
            resp = cast(
                liblq.ResOauth2Check,
                await self.rpc_call(
                    ".lq.Lobby.oauth2Check",
                    {"type": 0, "access_token": access_token},
                ),
            )
            logger.debug(
                "[majsoul-review] oauth2Check retry response: "
                f"has_account={resp.has_account} {_error_summary(resp.error)}"
            )
        if not resp.has_account:
            raise ValueError(f"access token invalid: {_error_summary(resp.error)}")

        logger.debug(
            "[majsoul-review] oauth2Login request meta: "
            f"client_version_string={self.client_version_string} "
            f"resource={version_info.version} tag={self.client_tag} "
            f"currency_platforms={self.currency_platforms}"
        )
        resp = cast(
            liblq.ResLogin,
            await self.rpc_call(
                ".lq.Lobby.oauth2Login",
                {
                    "type": 0,
                    "access_token": access_token,
                    "reconnect": False,
                    "device": _client_device_info(),
                    "random_key": self.random_key,
                    "client_version": {"resource": version_info.version},
                    "currency_platforms": self.currency_platforms,
                    "client_version_string": self.client_version_string,
                    "tag": self.client_tag,
                },
            ),
        )
        if not resp.account_id:
            logger.debug(
                "[majsoul-review] oauth2Login failed response: "
                f"{_error_summary(resp.error)}"
            )
            raise ValueError(f"oauth2 login failed: {_error_summary(resp.error)}")
        self.account_id = resp.account_id
        self.nick_name = resp.account.nickname
        logger.debug(
            "[majsoul-review] oauth2Login success: "
            f"account_id={self.account_id} nickname={self.nick_name}"
        )

        beat = cast(
            liblq.ResCommon,
            await self.rpc_call(
                ".lq.Lobby.loginBeat",
                {"contract": "DF2vkXCnfeXp4WoGSBGNcJBufZiMN3UP"},
            ),
        )
        if beat.error.code:
            raise ValueError(f"loginBeat failed: {_error_summary(beat.error)}")

        self.access_token = access_token
        return self.account_id, self.access_token, self.nick_name

    async def fetch_logs(
        self,
        game_id: str,
        paipu_dir: Path,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict:
        paipu_dir.mkdir(parents=True, exist_ok=True)
        raw_path = paipu_dir / f"{game_id} - raw.json"
        if raw_path.exists():
            await _notify(progress_cb, "命中原始牌谱缓存")
            async with aiofiles.open(raw_path, "r", encoding="utf-8") as f:
                return json.loads(await f.read())

        seps = game_id.split("_")
        log_id = seps[0]

        if len(seps) >= 3 and seps[2] == "2":
            log_id = decode_log_id(log_id)

        target_id = None
        if len(seps) >= 2:
            if seps[1].startswith("a"):
                target_id = decode_account_id2(int(seps[1][1:]))
            else:
                try:
                    target_id = int(seps[1])
                except ValueError:
                    target_id = None

        await _notify(progress_cb, f"调用 fetchGameRecord 拉取牌谱: {log_id}")
        logs = cast(
            liblq.ResGameRecord,
            await self.rpc_call(
                ".lq.Lobby.fetchGameRecord",
                {
                    "game_uuid": log_id,
                    "client_version_string": self.client_version_string,
                },
            ),
        )
        if logs.error.code:
            raise ValueError(f"fetchGameRecord failed: {logs.error}")

        detail_records = liblq.Wrapper().parse(logs.data)
        payload = liblq.GameDetailRecords().parse(detail_records.data)

        action_list = []
        if payload.version < 210715 and len(payload.records) > 0:
            for value in payload.records:
                raw = liblq.Wrapper().parse(value)
                name = raw.name.split(".")[2]
                parser_cls = getattr(liblq, name, None)
                if parser_cls is None:
                    logger.warning(f"[majsoul-review] 未知旧版action类型，已跳过: {name}")
                    continue
                msg = parser_cls().parse(raw.data)
                action_list.append(MjsLogItem(name=name, data=msg))
        else:
            for action in payload.actions:
                if action.result and len(action.result) > 0:
                    raw = liblq.Wrapper().parse(action.result)
                    name = raw.name.split(".")[2]
                    parser_cls = getattr(liblq, name, None)
                    if parser_cls is None:
                        logger.warning(f"[majsoul-review] 未知action类型，已跳过: {name}")
                        continue
                    msg = parser_cls().parse(raw.data)
                    action_list.append(MjsLogItem(name=name, data=msg))

        tenhou_log = MajsoulPaipuParser().handle_game_record(
            record=MjsLog(logs.head, action_list)
        )

        tenhou_log["head"] = process_dict(logs.head)
        tenhou_log["game_id"] = game_id
        tenhou_log["log_id"] = log_id
        tenhou_log["target_id"] = target_id

        if target_id is not None:
            for acc in logs.head.accounts:
                if acc.account_id == target_id:
                    tenhou_log["_target_actor"] = acc.seat
                    break
        else:
            if logs.head.accounts:
                tenhou_log["target_id"] = logs.head.accounts[0].account_id
                tenhou_log["_target_actor"] = logs.head.accounts[0].seat
            else:
                tenhou_log["_target_actor"] = 0

        async with aiofiles.open(raw_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(tenhou_log, ensure_ascii=False, indent=2))

        await _notify(progress_cb, "原始牌谱缓存完成")
        return tenhou_log


async def fetch_majsoul_info(
    url_base: str = URL_BASE,
    progress_cb: Optional[ProgressCallback] = None,
):
    await _notify(progress_cb, "正在获取雀魂版本信息")
    version_info = convert(
        await get_res(url_base, "version.json", bust_cache=True),
        MajsoulVersionInfo,
    )
    logger.debug(
        "[majsoul-review] version info: "
        f"version={version_info.version} force_version={version_info.force_version} "
        f"code={version_info.code}"
    )
    client_version_string, client_version_source = (
        await _fetch_login_client_version_string(url_base, version_info)
    )
    logger.debug(
        "[majsoul-review] login client version: "
        f"client_version_string={client_version_string} "
        f"source={client_version_source} "
        f"legacy={_legacy_client_version_string(version_info)}"
    )

    await _notify(progress_cb, "正在获取资源版本信息")
    res_info = convert(
        await get_res(url_base, f"resversion{version_info.version}.json"),
        MajsoulResInfo,
    )

    pb_version = res_info.res["res/proto/liqi.json"].prefix
    config_path = f"{res_info.res['config.json'].prefix}/config.json"
    logger.debug(
        "[majsoul-review] resource info: "
        f"proto_prefix={pb_version} config_path={config_path}"
    )
    await _notify(progress_cb, "正在加载协议定义")
    pb_def = convert(
        await get_res(url_base, f"{pb_version}/res/proto/liqi.json"),
        MajsoulLiqiProto,
    )

    await _notify(progress_cb, "正在获取网关配置")
    config_obj = await get_res(url_base, config_path)
    try:
        config = convert(config_obj, MajsoulConfig)
    except ValidationError as exc:
        raise ValueError(f"config parse failed: {exc}")

    ip_defs = list(config.ip or [])
    if not ip_defs:
        raise ValueError("config.ip is empty")

    ip_def = next((x for x in ip_defs if getattr(x, "name", "") == "player"), ip_defs[0])
    gateways = list(getattr(ip_def, "gateways", []) or [])
    if not gateways:
        raise ValueError("gateway list is empty")

    gateway_url = random.choice(gateways).url
    logger.debug(
        "[majsoul-review] gateway config: "
        f"ip_defs={len(ip_defs)} selected_ip={getattr(ip_def, 'name', '')} "
        f"gateway_count={len(gateways)} selected_url={gateway_url}"
    )
    region_url = gateway_url.replace("https://", "")
    server = f"{region_url}/gateway"

    await _notify(progress_cb, f"网关已选择: {server}")
    return server, pb_def, pb_version, version_info, client_version_string


async def create_connection(
    username: str = "",
    password: str = "",
    access_token: str = "",
    progress_cb: Optional[ProgressCallback] = None,
) -> MajsoulConnection:
    (
        server,
        pb_def,
        pb_version,
        version_info,
        client_version_string,
    ) = await fetch_majsoul_info(
        URL_BASE,
        progress_cb=progress_cb,
    )

    codec = MajsoulProtoCodec(pb_def, pb_version)
    conn = MajsoulConnection(
        f"wss://{server}",
        codec,
        version_info,
        client_version_string=client_version_string,
    )
    try:
        await _notify(progress_cb, "正在建立 WebSocket 连接")
        await conn.connect()

        await _notify(progress_cb, "连接成功，发送心跳")
        _ = await conn.rpc_call(
            ".lq.Route.heartbeat",
            {
                "delay": random.randint(0, 200),
                "no_operation_counter": 0,
                "platform": 11,
                "network_quality": random.randint(0, 100),
            },
        )

        if access_token:
            await _notify(progress_cb, "正在使用 access_token 登录")
            await conn.access_token_login(version_info, access_token)
        else:
            if not username or not password:
                raise ValueError("username or password is empty")
            await _notify(progress_cb, "正在使用账号密码登录")
            await conn.manual_login(username, password, version_info)

        await _notify(progress_cb, f"登录成功: account_id={conn.account_id}")
        return conn
    except Exception:
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await conn.close()
        raise

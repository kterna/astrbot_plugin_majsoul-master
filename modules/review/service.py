import asyncio
import inspect
import json
import random
import re
from pathlib import Path
from typing import Awaitable, Callable, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from astrbot.api import logger

from .account_store import AccountStore
from .majsoul_connection import create_connection

ProgressCallback = Callable[[str], Optional[Awaitable[None]]]


class ReviewService:
    """Raw paipu fetch service."""

    def __init__(self, plugin_root: str | Path, data_root: str | Path, config: Optional[dict] = None):
        self.plugin_root = Path(plugin_root)
        self.data_root = Path(data_root)
        self.config = config or {}

        self.review_data_dir = self.data_root / "review"
        self.paipu_dir = self.review_data_dir / "paipu"
        self.paipu_dir.mkdir(parents=True, exist_ok=True)

        self.store = AccountStore(self.review_data_dir / "accounts.json")

    async def _notify(self, progress_cb: Optional[ProgressCallback], message: str) -> None:
        logger.info(f"[majsoul-review] {message}")
        if progress_cb is None:
            return
        result = progress_cb(message)
        if inspect.isawaitable(result):
            await result

    async def _close_conn(self, conn, timeout_sec: int = 5) -> None:
        if conn is None:
            return
        try:
            await asyncio.wait_for(conn.close(), timeout=timeout_sec)
        except asyncio.CancelledError:
            logger.warning("[majsoul-review] 连接关闭被取消，已忽略并继续流程")
        except asyncio.TimeoutError:
            logger.warning(f"[majsoul-review] 连接关闭超时({timeout_sec}s)，已跳过等待")
        except Exception:
            logger.warning("[majsoul-review] 连接关闭异常，已忽略", exc_info=True)

    @staticmethod
    def parse_game_id(text: str) -> Optional[str]:
        raw = text.strip()
        if not raw:
            return None

        if "paipu=" in raw:
            parsed = urlparse(raw)
            query = parse_qs(parsed.query)
            value = query.get("paipu")
            if value and value[0]:
                return value[0].strip()
            return None

        if raw.startswith("http://") or raw.startswith("https://"):
            parsed = urlparse(raw)
            query = parse_qs(parsed.query)
            value = query.get("paipu")
            if value and value[0]:
                return value[0].strip()
            return None

        return raw

    async def add_cn_account(
        self,
        username: str,
        password: str,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Tuple[bool, str]:
        conn = None
        try:
            await self._notify(progress_cb, "正在连接国服服务器并验证账号")
            conn = await create_connection(
                username=username,
                password=password,
                progress_cb=progress_cb,
            )
            await self.store.add_or_update(
                uid=str(conn.account_id),
                username=username,
                password=password,
                token=conn.access_token,
                nickname=conn.nick_name,
                status="ok",
                error="",
            )
            await self._notify(progress_cb, f"登录成功，账号已入池: {conn.nick_name}({conn.account_id})")
            return True, f"登录成功并已入池: {conn.nick_name}({conn.account_id})"
        except Exception as exc:
            detail = str(exc).strip() or repr(exc) or exc.__class__.__name__
            logger.error(
                f"[majsoul-review] 国服登录失败 username={username}: {exc.__class__.__name__}: {detail}",
                exc_info=True,
            )
            return False, f"登录失败: {exc.__class__.__name__}: {detail}"
        finally:
            if conn is not None:
                await self._close_conn(conn)

    async def list_accounts(self) -> str:
        accounts = await self.store.list_accounts()
        if not accounts:
            return "账号池为空，请先使用：雀魂登录国服 <用户名> <密码>"

        lines = ["【雀魂账号池】"]
        for index, acc in enumerate(accounts, 1):
            token_status = "有" if acc.token else "无"
            lines.append(
                f"{index}. uid={acc.uid} nick={acc.nickname or '-'} user={self.store.masked(acc.username)} token={token_status} status={acc.last_status}"
            )
            if acc.last_error:
                lines.append(f"   最近错误: {acc.last_error[:120]}")
        return "\n".join(lines)

    async def remove_account(self, identifier: str) -> Tuple[bool, str]:
        ok = await self.store.remove(identifier.strip())
        if ok:
            return True, "删除成功"
        return False, "未找到对应账号，请使用序号/uid/用户名"

    async def _read_json(self, path: Path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    async def _fetch_with_accounts(self, game_id: str, progress_cb: Optional[ProgressCallback] = None):
        accounts = await self.store.list_accounts()
        if not accounts:
            raise RuntimeError("未配置账号池，请先执行：雀魂登录国服 <用户名> <密码>")

        random.shuffle(accounts)
        errors: List[str] = []

        for idx, acc in enumerate(accounts, 1):
            conn = None
            try:
                await self._notify(
                    progress_cb,
                    f"正在尝试账号 {idx}/{len(accounts)}: uid={acc.uid}",
                )
                if acc.token:
                    try:
                        await self._notify(progress_cb, "优先使用 token 登录")
                        conn = await create_connection(access_token=acc.token, progress_cb=progress_cb)
                    except Exception:
                        await self._notify(progress_cb, "token 登录失败，回退账号密码登录")
                        conn = await create_connection(
                            username=acc.username,
                            password=acc.password,
                            progress_cb=progress_cb,
                        )
                else:
                    conn = await create_connection(
                        username=acc.username,
                        password=acc.password,
                        progress_cb=progress_cb,
                    )

                await self.store.update_token(acc.uid, conn.access_token, conn.nick_name)
                await self._notify(progress_cb, "登录成功，正在拉取原始牌谱")
                raw = await conn.fetch_logs(game_id, self.paipu_dir, progress_cb=progress_cb)
                await self.store.update_status(acc.uid, "ok", "")
                await self._notify(progress_cb, "原始牌谱拉取完成")
                return raw
            except Exception as exc:
                err = f"{acc.uid}/{acc.username}: {exc}"
                errors.append(err)
                await self.store.update_status(acc.uid, "failed", str(exc))
                logger.error(
                    f"[majsoul-review] 账号尝试失败 uid={acc.uid} user={acc.username}: "
                    f"{exc.__class__.__name__}: {exc}",
                    exc_info=True,
                )
                await self._notify(progress_cb, f"账号尝试失败: {acc.uid} ({exc.__class__.__name__})")
            finally:
                if conn is not None:
                    await self._close_conn(conn)

        raise RuntimeError("全部账号尝试失败:\n" + "\n".join(errors[:5]))

    @staticmethod
    def _round_label(kyoku: int, honba: int) -> str:
        winds = ["东", "南", "西", "北"]
        wind = winds[(kyoku // 4) % 4]
        num = kyoku % 4 + 1
        return f"{wind}{num}局 {honba}本场"

    @staticmethod
    def _seat_name(players: List[str], seat: int) -> str:
        if 0 <= seat < len(players):
            name = str(players[seat]).strip()
            if name:
                return name
        return f"座位{seat}"

    def _format_scores(self, players: List[str], scores: List[int]) -> str:
        parts = []
        for idx, score in enumerate(scores):
            if idx >= len(players):
                continue
            name = self._seat_name(players, idx)
            parts.append(f"{name}:{int(score)}")
        return " / ".join(parts)

    @staticmethod
    def _adjust_point_text_with_honba(point_text: str, honba: int, is_tsumo: bool) -> str:
        if honba <= 0:
            return point_text

        # 子家自摸示例: 1000-2000点
        m = re.search(r"(\\d+)-(\\d+)点", point_text)
        if is_tsumo and m:
            ko = int(m.group(1)) + honba * 100
            oya = int(m.group(2)) + honba * 100
            return point_text.replace(m.group(0), f"{ko}-{oya}点")

        # 庄家自摸示例: 2000点∀
        m = re.search(r"(\\d+)点∀", point_text)
        if is_tsumo and m:
            all_pay = int(m.group(1)) + honba * 100
            return point_text.replace(m.group(0), f"{all_pay}点∀")

        # 荣和示例: 3900点 / 満貫12000点
        m = re.search(r"(\\d+)点", point_text)
        if m:
            ron = int(m.group(1)) + honba * 300
            return point_text.replace(m.group(0), f"{ron}点")

        return point_text

    @staticmethod
    def _to_int_list(value) -> List[int]:
        if not isinstance(value, list):
            return []
        result: List[int] = []
        for item in value:
            if isinstance(item, (int, float)):
                result.append(int(item))
            else:
                try:
                    result.append(int(item))
                except Exception:
                    result.append(0)
        return result

    def _summarize_round(self, players: List[str], kyoku_entry: list) -> List[str]:
        if not isinstance(kyoku_entry, list) or len(kyoku_entry) < 2:
            return ["无法解析该局数据"]

        round_info = kyoku_entry[0] if isinstance(kyoku_entry[0], list) else [0, 0, 0]
        kyoku = int(round_info[0]) if len(round_info) > 0 else 0
        honba = int(round_info[1]) if len(round_info) > 1 else 0

        start_scores = self._to_int_list(kyoku_entry[1])
        if not start_scores:
            start_scores = [0] * len(players)
        if len(start_scores) < len(players):
            start_scores.extend([0] * (len(players) - len(start_scores)))
        current_scores = list(start_scores)

        result = kyoku_entry[-1] if kyoku_entry else []
        lines = [f"{self._round_label(kyoku, honba)}"]
        lines.append(f"  开始点数: {self._format_scores(players, start_scores)}")

        riichi_in_round = 0
        for seat in range(min(4, len(players))):
            disc_idx = 4 + seat * 3 + 2
            if disc_idx >= len(kyoku_entry) - 1:
                continue
            disc = kyoku_entry[disc_idx]
            if isinstance(disc, list):
                riichi_in_round += sum(
                    1 for tile in disc if isinstance(tile, str) and tile.startswith("r")
                )

        if isinstance(result, list) and result:
            result_type = str(result[0])

            if result_type == "和了":
                # 格式: ["和了", delta1, agari1, delta2, agari2, ...]
                for i in range(1, len(result), 2):
                    delta = result[i] if i < len(result) else []
                    agari = result[i + 1] if i + 1 < len(result) else []
                    delta_list = self._to_int_list(delta)
                    if len(delta_list) >= len(current_scores):
                        current_scores = [
                            current_scores[idx] + delta_list[idx] for idx in range(len(current_scores))
                        ]

                    if not isinstance(agari, list) or len(agari) < 4:
                        continue

                    winner = int(agari[0]) if isinstance(agari[0], (int, float)) else -1
                    from_seat = int(agari[1]) if isinstance(agari[1], (int, float)) else -1
                    point_text = str(agari[3])
                    is_tsumo = winner == from_seat
                    point_text_adj = self._adjust_point_text_with_honba(
                        point_text,
                        honba,
                        is_tsumo,
                    )
                    yaku = [str(x) for x in agari[4:] if str(x).strip()]

                    winner_name = self._seat_name(players, winner)
                    if is_tsumo:
                        lines.append(f"  和了: {winner_name} 自摸 {point_text_adj}")
                    else:
                        from_name = self._seat_name(players, from_seat)
                        lines.append(f"  和了: {winner_name} 荣和 {from_name} {point_text_adj}")

                    if yaku:
                        lines.append(f"  役种: {', '.join(yaku)}")

                    if riichi_in_round > 0:
                        lines.append(f"  立直棒: {riichi_in_round}根（已计入结束点数）")

            elif result_type == "流局":
                lines.append("  结果: 流局")
                if len(result) > 1:
                    delta_list = self._to_int_list(result[1])
                    if len(delta_list) >= len(current_scores):
                        current_scores = [
                            current_scores[idx] + delta_list[idx] for idx in range(len(current_scores))
                        ]
            else:
                lines.append(f"  结果: {result_type}")
                if len(result) > 1:
                    delta_list = self._to_int_list(result[1])
                    if len(delta_list) >= len(current_scores):
                        current_scores = [
                            current_scores[idx] + delta_list[idx] for idx in range(len(current_scores))
                        ]
        else:
            lines.append("  结果: 未知")

        lines.append(f"  结束点数: {self._format_scores(players, current_scores)}")
        return lines

    def _build_summary(self, raw: dict) -> str:
        raw_players = raw.get("name") or []
        players: List[str] = []
        for idx, item in enumerate(raw_players):
            name = str(item).strip()
            players.append(name if name else f"座位{idx}")
        rounds = raw.get("log") or []
        if not players:
            players = [f"座位{i}" for i in range(4)]

        lines = [f"共{len(rounds)}局", f"玩家: {' / '.join(players)}", ""]
        for idx, kyoku_entry in enumerate(rounds, 1):
            lines.append(f"[第{idx}局]")
            lines.extend(self._summarize_round(players, kyoku_entry))
            if idx != len(rounds):
                lines.append("")
        return "\n".join(lines)

    async def do_review(
        self,
        text: str,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Tuple[bool, str, List[str]]:
        """Kept for command compatibility. Only fetches raw paipu now."""
        game_id = self.parse_game_id(text)
        if not game_id:
            return False, "请输入有效的牌谱URL或paipu_id", []

        await self._notify(progress_cb, f"已解析牌谱ID: {game_id}")

        raw_path = self.paipu_dir / f"{game_id} - raw.json"

        try:
            if raw_path.exists():
                await self._notify(progress_cb, "命中原始牌谱缓存，跳过拉取")
                raw = await self._read_json(raw_path)
            else:
                await self._notify(progress_cb, "未命中原始牌谱缓存，开始拉取")
                raw = await self._fetch_with_accounts(game_id, progress_cb=progress_cb)
        except Exception as exc:
            return False, f"牌谱拉取失败: {exc}", []

        summary = self._build_summary(raw)
        message = (
            "牌谱拉取成功\n"
            f"game_id: {game_id}\n"
            "缓存状态: 已写入\n"
            f"{summary}"
        )
        return True, message, []

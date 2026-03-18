import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astrbot.api import logger


@dataclass
class ResolvedPaipuSource:
    game_id: str
    raw: dict[str, Any]
    raw_json_path: str


@dataclass
class PlayerReplayResult:
    seat: int
    name: str
    closed_hand: list[int]
    melds: list[str]
    last_draw: str | None
    last_discard: str | None
    riichi_declared: bool
    completed_turns: int
    timeline: list[dict[str, Any]]


class PaipuAnalysisService:
    """Structured raw paipu analysis for LLM tools."""

    _HONORS = {
        1: "東",
        2: "南",
        3: "西",
        4: "北",
        5: "白",
        6: "發",
        7: "中",
    }

    _CALL_PHASE_MAP = {
        "chi": "call",
        "pon": "call",
        "daiminkan": "kan",
        "ankan": "kan",
        "kakan": "kan",
        "kita": "kita",
        "unknown": "call",
    }

    def __init__(self, review_service: Any | None = None, repo_root: str | Path | None = None):
        self.review_service = review_service
        if repo_root is not None:
            self.repo_root = Path(repo_root)
        elif review_service is not None and getattr(review_service, "repo_root", None) is not None:
            self.repo_root = Path(review_service.repo_root)
        else:
            self.repo_root = None

    def _error(self, message: str) -> dict[str, Any]:
        return {
            "status": "error",
            "message": message,
        }

    async def list_rounds(self, paipu_source: str) -> dict[str, Any]:
        ok, message, resolved = await self._resolve_paipu_source(paipu_source)
        if not ok or resolved is None:
            return self._error(message)
        return self.list_rounds_from_raw(
            resolved.raw,
            game_id=resolved.game_id,
            raw_json_path=resolved.raw_json_path,
        )

    async def get_round_result(self, paipu_source: str, round_selector: str) -> dict[str, Any]:
        ok, message, resolved = await self._resolve_paipu_source(paipu_source)
        if not ok or resolved is None:
            return self._error(message)
        return self.get_round_result_from_raw(
            resolved.raw,
            round_selector=round_selector,
            game_id=resolved.game_id,
            raw_json_path=resolved.raw_json_path,
        )

    async def get_round_turn_state(
        self,
        paipu_source: str,
        round_selector: str,
        turn_mode: str,
        turn_number: int,
        seat: int = -1,
        phase: str = "discard",
    ) -> dict[str, Any]:
        ok, message, resolved = await self._resolve_paipu_source(paipu_source)
        if not ok or resolved is None:
            return self._error(message)
        return self.get_round_turn_state_from_raw(
            resolved.raw,
            round_selector=round_selector,
            turn_mode=turn_mode,
            turn_number=turn_number,
            seat=seat,
            phase=phase,
            game_id=resolved.game_id,
            raw_json_path=resolved.raw_json_path,
        )

    async def get_player_round_trace(
        self,
        paipu_source: str,
        round_selector: str,
        player_selector: str,
    ) -> dict[str, Any]:
        ok, message, resolved = await self._resolve_paipu_source(paipu_source)
        if not ok or resolved is None:
            return self._error(message)
        return self.get_player_round_trace_from_raw(
            resolved.raw,
            round_selector=round_selector,
            player_selector=player_selector,
            game_id=resolved.game_id,
            raw_json_path=resolved.raw_json_path,
        )

    async def _resolve_paipu_source(
        self,
        paipu_source: str,
    ) -> tuple[bool, str, ResolvedPaipuSource | None]:
        source = paipu_source.strip()
        if not source:
            return False, "请输入有效的 paipu_source", None

        if self._looks_like_json_path(source):
            raw_path = Path(source)
            if not raw_path.is_absolute():
                if self.repo_root is None:
                    return False, "当前分析服务未配置 repo_root，无法解析相对路径", None
                raw_path = self.repo_root / raw_path
            if not raw_path.exists():
                return False, f"找不到 raw.json 文件: {source}", None
            try:
                with open(raw_path, "r", encoding="utf-8") as file:
                    raw = json.load(file)
            except Exception as exc:
                return False, f"读取 raw.json 失败: {exc}", None
            return True, "", ResolvedPaipuSource(
                game_id=str(raw.get("game_id") or raw_path.stem),
                raw=raw,
                raw_json_path=self._to_relative_path(raw_path),
            )

        if self.review_service is None:
            return False, "当前分析服务未配置牌谱抓取服务，无法自动拉取牌谱", None

        try:
            success, message, fetch_result = await self.review_service.fetch_raw_paipu(source)
        except Exception as exc:
            logger.error(f"[majsoul-analysis] resolve paipu source failed: {exc}", exc_info=True)
            return False, f"牌谱解析失败: {exc}", None

        if not success or fetch_result is None:
            return False, message, None

        return True, "", ResolvedPaipuSource(
            game_id=fetch_result.game_id,
            raw=fetch_result.raw,
            raw_json_path=fetch_result.raw_path_relative,
        )

    def list_rounds_from_raw(
        self,
        raw: dict[str, Any],
        game_id: str | None = None,
        raw_json_path: str = "",
    ) -> dict[str, Any]:
        rounds = raw.get("log") or []
        round_items: list[dict[str, Any]] = []
        for round_index, entry in enumerate(rounds):
            players = self._player_names(raw, entry)
            result_info = self._parse_result(players, entry)
            round_meta = self._round_meta(entry)
            round_items.append(
                {
                    "round_index": round_index,
                    "round_label": round_meta["round_label"],
                    "chang_wind": round_meta["chang_wind"],
                    "kyoku_number": round_meta["kyoku_number"],
                    "honba": round_meta["honba"],
                    "riichi_sticks": round_meta["riichi_sticks"],
                    "start_scores": self._to_int_list(entry[1] if len(entry) > 1 else []),
                    "dora_indicators": self._tiles_to_strings(entry[2] if len(entry) > 2 else []),
                    "ura_indicators": self._tiles_to_strings(entry[3] if len(entry) > 3 else []),
                    "result_type": result_info["result_type"],
                    "winner_seats": [item["winner_seat"] for item in result_info["agari"]],
                    "from_seat": result_info["from_seat"],
                    "point_text": result_info["point_text"],
                    "yakus": result_info["yakus"],
                }
            )

        return {
            "status": "success",
            "game_id": game_id or str(raw.get("game_id") or ""),
            "raw_json_path": raw_json_path,
            "players": self._player_briefs(raw),
            "rounds": round_items,
        }

    def get_round_result_from_raw(
        self,
        raw: dict[str, Any],
        round_selector: str,
        game_id: str | None = None,
        raw_json_path: str = "",
    ) -> dict[str, Any]:
        ok, message, context = self._round_context(raw, round_selector)
        if not ok or context is None:
            return self._error(message)

        result_info = self._parse_result(context["players"], context["entry"])
        return {
            "status": "success",
            "game_id": game_id or str(raw.get("game_id") or ""),
            "raw_json_path": raw_json_path,
            "round_index": context["round_index"],
            "round_label": context["round_label"],
            "start_scores": self._to_int_list(context["entry"][1]),
            "dora_indicators": self._tiles_to_strings(context["entry"][2]),
            "ura_indicators": self._tiles_to_strings(context["entry"][3]),
            "result_type": result_info["result_type"],
            "score_delta": result_info["score_delta"],
            "agari": result_info["agari"],
            "draw_result": result_info["draw_result"],
        }

    def get_round_turn_state_from_raw(
        self,
        raw: dict[str, Any],
        round_selector: str,
        turn_mode: str,
        turn_number: int,
        seat: int = -1,
        phase: str = "discard",
        game_id: str | None = None,
        raw_json_path: str = "",
    ) -> dict[str, Any]:
        if turn_number <= 0:
            return self._error("turn_number 必须大于 0")

        ok, message, context = self._round_context(raw, round_selector)
        if not ok or context is None:
            return self._error(message)

        players = context["players"]
        nplayers = len(players)
        normalized_mode = turn_mode.strip().lower()
        normalized_phase = phase.strip().lower()
        if normalized_phase not in {"draw", "discard"}:
            return self._error("phase 仅支持 draw 或 discard")
        if normalized_mode not in {"global", "seat_local"}:
            return self._error("turn_mode 仅支持 global 或 seat_local")
        if normalized_mode == "seat_local" and not 0 <= seat < nplayers:
            return self._error("seat_local 模式下必须提供有效的 seat")
        if normalized_mode == "global" and seat >= nplayers:
            return self._error("seat 超出玩家数量")

        replays: list[PlayerReplayResult] = []
        if normalized_mode == "global":
            for current_seat in range(nplayers):
                replays.append(
                    self._replay_player_until(
                        context["entry"],
                        players,
                        current_seat,
                        stop_turn=turn_number,
                        stop_phase="discard",
                    )
                )
        else:
            for current_seat in range(nplayers):
                current_phase = normalized_phase if current_seat == seat else "discard"
                replays.append(
                    self._replay_player_until(
                        context["entry"],
                        players,
                        current_seat,
                        stop_turn=turn_number,
                        stop_phase=current_phase,
                    )
                )

        focus_trace: list[dict[str, Any]] = []
        if 0 <= seat < nplayers:
            focus_trace = replays[seat].timeline

        return {
            "status": "success",
            "game_id": game_id or str(raw.get("game_id") or ""),
            "raw_json_path": raw_json_path,
            "round_index": context["round_index"],
            "round_label": context["round_label"],
            "turn_mode": normalized_mode,
            "turn_number": turn_number,
            "phase": normalized_phase if normalized_mode == "seat_local" else "discard",
            "anchor_seat": seat if seat >= 0 else None,
            "snapshot_type": (
                f"seat_local_{normalized_phase}" if normalized_mode == "seat_local" else "global_turn_end"
            ),
            "seat_turns_completed": [replay.completed_turns for replay in replays],
            "truncated": any(replay.completed_turns < turn_number for replay in replays),
            "dora_indicators": self._tiles_to_strings(context["entry"][2]),
            "visible_kan_count": sum(self._kan_count(replay.melds) for replay in replays),
            "players": [self._player_state_payload(replay) for replay in replays],
            "focus_trace": focus_trace,
        }

    def get_player_round_trace_from_raw(
        self,
        raw: dict[str, Any],
        round_selector: str,
        player_selector: str,
        game_id: str | None = None,
        raw_json_path: str = "",
    ) -> dict[str, Any]:
        ok, message, context = self._round_context(raw, round_selector)
        if not ok or context is None:
            return self._error(message)

        seat = self._select_player(context["players"], player_selector)
        if seat < 0:
            return self._error("未找到对应玩家，请使用 seat 或精确昵称")

        replay = self._replay_player_until(context["entry"], context["players"], seat)
        result_info = self._parse_result(context["players"], context["entry"])
        score_delta = result_info["score_delta"]

        return {
            "status": "success",
            "game_id": game_id or str(raw.get("game_id") or ""),
            "raw_json_path": raw_json_path,
            "round_index": context["round_index"],
            "round_label": context["round_label"],
            "player": {
                "seat": seat,
                "name": context["players"][seat],
            },
            "haipai": self._tiles_to_strings(context["seat_data"][seat]["haipai"]),
            "final_state": {
                "closed_hand": self._hand_to_strings(replay.closed_hand),
                "melds": list(replay.melds),
                "riichi_declared": replay.riichi_declared,
                "round_end_status": self._player_round_end_status(result_info, seat),
                "score_delta": score_delta[seat] if seat < len(score_delta) else 0,
            },
            "timeline": replay.timeline,
        }

    def _round_context(
        self,
        raw: dict[str, Any],
        round_selector: str,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        rounds = raw.get("log") or []
        if not rounds:
            return False, "牌谱中没有可分析的局数据", None

        if round_selector.strip().isdigit():
            round_index = int(round_selector.strip())
            if not 0 <= round_index < len(rounds):
                return False, f"round_index 超出范围: {round_index}", None
        else:
            normalized_selector = self._normalize_round_selector(round_selector)
            round_index = -1
            for idx, entry in enumerate(rounds):
                if normalized_selector == self._normalize_round_selector(self._round_label_from_entry(entry)):
                    round_index = idx
                    break
            if round_index < 0:
                return False, f"未找到指定局: {round_selector}", None

        entry = rounds[round_index]
        players = self._player_names(raw, entry)
        return True, "", {
            "round_index": round_index,
            "round_label": self._round_label_from_entry(entry),
            "entry": entry,
            "players": players,
            "seat_data": self._seat_data(entry, players),
        }

    def _player_names(self, raw: dict[str, Any], entry: list[Any]) -> list[str]:
        nplayers = self._entry_nplayers(entry)
        names = list(raw.get("name") or [])
        result = []
        for seat in range(nplayers):
            name = str(names[seat]).strip() if seat < len(names) else ""
            result.append(name or f"Seat{seat}")
        return result

    def _player_briefs(self, raw: dict[str, Any]) -> list[dict[str, Any]]:
        rounds = raw.get("log") or []
        if not rounds:
            return []
        players = self._player_names(raw, rounds[0])
        return [{"seat": seat, "name": name} for seat, name in enumerate(players)]

    def _seat_data(self, entry: list[Any], players: list[str]) -> list[dict[str, Any]]:
        seat_data = []
        for seat in range(len(players)):
            base = 4 + seat * 3
            seat_data.append(
                {
                    "haipai": list(entry[base]),
                    "draws": list(entry[base + 1]),
                    "discards": list(entry[base + 2]),
                }
            )
        return seat_data

    def _round_meta(self, entry: list[Any]) -> dict[str, Any]:
        round_info = entry[0] if entry and isinstance(entry[0], list) else [0, 0, 0]
        kyoku = int(round_info[0]) if len(round_info) > 0 else 0
        honba = int(round_info[1]) if len(round_info) > 1 else 0
        riichi_sticks = int(round_info[2]) if len(round_info) > 2 else 0
        chang_wind = ["东", "南", "西", "北"][(kyoku // 4) % 4]
        kyoku_number = kyoku % 4 + 1
        return {
            "round_label": self._round_label_from_entry(entry),
            "chang_wind": chang_wind,
            "kyoku_number": kyoku_number,
            "honba": honba,
            "riichi_sticks": riichi_sticks,
        }

    def _round_label_from_entry(self, entry: list[Any]) -> str:
        round_info = entry[0] if entry and isinstance(entry[0], list) else [0, 0, 0]
        kyoku = int(round_info[0]) if len(round_info) > 0 else 0
        honba = int(round_info[1]) if len(round_info) > 1 else 0
        wind = ["东", "南", "西", "北"][(kyoku // 4) % 4]
        number = kyoku % 4 + 1
        honba_text = "一本场" if honba == 1 else f"{honba}本场"
        return f"{wind}{number}{honba_text}"

    def _normalize_round_selector(self, selector: str) -> str:
        text = selector.strip()
        text = text.replace("東", "东").replace("場", "场")
        text = re.sub(r"\s+", "", text)
        text = text.replace("局", "")
        text = text.replace("一本场", "1本场")
        match = re.match(r"([东南西北])([1-4])([0-9]+)本场$", text)
        if match:
            return f"{match.group(1)}{match.group(2)}{match.group(3)}本场"
        return text

    def _parse_result(self, players: list[str], entry: list[Any]) -> dict[str, Any]:
        result = entry[-1] if entry else []
        nplayers = len(players)
        payload = {
            "result_type": "未知",
            "score_delta": [0] * nplayers,
            "agari": [],
            "draw_result": None,
            "from_seat": None,
            "point_text": "",
            "yakus": [],
        }
        if not isinstance(result, list) or not result:
            return payload

        result_type = str(result[0])
        payload["result_type"] = result_type
        if result_type == "和了":
            for idx in range(1, len(result), 2):
                delta = self._to_int_list(result[idx] if idx < len(result) else [])
                agari = result[idx + 1] if idx + 1 < len(result) else []
                if len(delta) >= nplayers:
                    payload["score_delta"] = [
                        payload["score_delta"][seat] + delta[seat] for seat in range(nplayers)
                    ]
                if not isinstance(agari, list) or len(agari) < 4:
                    continue

                winner_seat = int(agari[0])
                from_seat = int(agari[1])
                liable_seat = int(agari[2]) if len(agari) > 2 and isinstance(agari[2], (int, float)) else None
                point_text = str(agari[3])
                yakus = [str(item) for item in agari[4:] if str(item).strip()]
                payload["agari"].append(
                    {
                        "winner_seat": winner_seat,
                        "winner_name": players[winner_seat] if 0 <= winner_seat < len(players) else f"Seat{winner_seat}",
                        "from_seat": from_seat,
                        "from_name": players[from_seat] if 0 <= from_seat < len(players) else f"Seat{from_seat}",
                        "liable_seat": liable_seat,
                        "win_type": "tsumo" if winner_seat == from_seat else "ron",
                        "point_text": point_text,
                        "han_summary": self._extract_han_summary(point_text, yakus),
                        "yakus": yakus,
                    }
                )
                payload["from_seat"] = from_seat
                payload["point_text"] = point_text
                payload["yakus"] = yakus
        else:
            delta = self._to_int_list(result[1] if len(result) > 1 else [])
            if len(delta) >= nplayers:
                payload["score_delta"] = delta[:nplayers]
            payload["draw_result"] = {
                "type": result_type,
                "details": result[1:] if len(result) > 1 else [],
            }
        return payload

    def _extract_han_summary(self, point_text: str, yakus: list[str]) -> str:
        match = re.search(r"(\d+符\d+飜)", point_text)
        if match:
            return match.group(1)
        for yaku in yakus:
            match = re.search(r"\(([^)]+)\)", yaku)
            if match:
                return match.group(1)
        return ""

    def _replay_player_until(
        self,
        entry: list[Any],
        players: list[str],
        seat: int,
        stop_turn: int | None = None,
        stop_phase: str = "discard",
    ) -> PlayerReplayResult:
        base = 4 + seat * 3
        haipai = list(entry[base])
        draws = list(entry[base + 1])
        discards = list(entry[base + 2])

        closed = list(haipai)
        melds: list[str] = []
        timeline: list[dict[str, Any]] = []
        last_draw: str | None = None
        last_discard: str | None = None
        riichi_declared = False
        completed_turns = 0

        max_steps = max(len(draws), len(discards))
        for turn_index in range(max_steps):
            if turn_index < len(draws):
                draw_token = draws[turn_index]
                before = self._hand_to_strings(closed)
                if isinstance(draw_token, int):
                    closed.append(draw_token)
                    last_draw = self._tile_to_str(draw_token)
                    timeline.append(
                        {
                            "turn_index": turn_index + 1,
                            "phase": "draw",
                            "tile": last_draw,
                            "tile_from": "self",
                            "tsumogiri": False,
                            "riichi": False,
                            "closed_hand_before": before,
                            "closed_hand_after": self._hand_to_strings(closed),
                            "melds_after": list(melds),
                        }
                    )
                else:
                    call_info = self._parse_call(str(draw_token))
                    call_text = self._call_to_str(call_info)
                    last_draw = call_text
                    self._apply_call(closed, melds, call_info)
                    timeline.append(
                        {
                            "turn_index": turn_index + 1,
                            "phase": self._CALL_PHASE_MAP.get(call_info["type"], "call"),
                            "call_type": call_info["type"],
                            "tile": call_text,
                            "tile_from": "other",
                            "tsumogiri": False,
                            "riichi": False,
                            "closed_hand_before": before,
                            "closed_hand_after": self._hand_to_strings(closed),
                            "melds_after": list(melds),
                        }
                    )
                if stop_turn is not None and turn_index + 1 == stop_turn and stop_phase == "draw":
                    return PlayerReplayResult(
                        seat=seat,
                        name=players[seat],
                        closed_hand=closed,
                        melds=melds,
                        last_draw=last_draw,
                        last_discard=last_discard,
                        riichi_declared=riichi_declared,
                        completed_turns=completed_turns,
                        timeline=timeline,
                    )

            if turn_index < len(discards):
                discard_token = discards[turn_index]
                draw_token = draws[turn_index] if turn_index < len(draws) else None
                before = self._hand_to_strings(closed)
                discard_info = self._parse_discard(discard_token, draw_token)
                if not discard_info["placeholder"] and discard_info["tile_code"] is not None:
                    self._remove_tile(closed, int(discard_info["tile_code"]))
                if discard_info["riichi"]:
                    riichi_declared = True
                last_discard = discard_info["tile"]
                completed_turns = turn_index + 1
                timeline.append(
                    {
                        "turn_index": turn_index + 1,
                        "phase": "discard",
                        "tile": discard_info["tile"],
                        "tile_from": "self",
                        "tsumogiri": discard_info["tsumogiri"],
                        "riichi": discard_info["riichi"],
                        "closed_hand_before": before,
                        "closed_hand_after": self._hand_to_strings(closed),
                        "melds_after": list(melds),
                    }
                )
                if stop_turn is not None and turn_index + 1 == stop_turn and stop_phase == "discard":
                    break

        return PlayerReplayResult(
            seat=seat,
            name=players[seat],
            closed_hand=closed,
            melds=melds,
            last_draw=last_draw,
            last_discard=last_discard,
            riichi_declared=riichi_declared,
            completed_turns=completed_turns,
            timeline=timeline,
        )

    def _player_state_payload(self, replay: PlayerReplayResult) -> dict[str, Any]:
        return {
            "seat": replay.seat,
            "name": replay.name,
            "closed_hand": self._hand_to_strings(replay.closed_hand),
            "melds": list(replay.melds),
            "last_draw": replay.last_draw,
            "last_discard": replay.last_discard,
            "riichi_declared": replay.riichi_declared,
        }

    def _player_round_end_status(self, result_info: dict[str, Any], seat: int) -> str:
        if result_info["result_type"] != "和了":
            return result_info["result_type"]
        for agari in result_info["agari"]:
            if agari["winner_seat"] == seat:
                return "winner"
            if agari["win_type"] == "ron" and agari["from_seat"] == seat:
                return "dealt_in"
        return "other"

    def _select_player(self, players: list[str], player_selector: str) -> int:
        selector = player_selector.strip()
        if selector.isdigit():
            seat = int(selector)
            return seat if 0 <= seat < len(players) else -1
        for seat, name in enumerate(players):
            if name == selector:
                return seat
        return -1

    def _parse_call(self, token: str) -> dict[str, Any]:
        marks = []
        tiles = []
        mark_next = None
        index = 0
        while index < len(token):
            char = token[index]
            if char in "cmpkaf":
                mark_next = char
                index += 1
                continue
            if char.isdigit() and index + 1 < len(token) and token[index + 1].isdigit():
                code = int(token[index:index + 2])
                tiles.append(code)
                marks.append(mark_next)
                mark_next = None
                index += 2
                continue
            index += 1

        if token.startswith("c"):
            call_type = "chi"
        elif "p" in token:
            call_type = "pon"
        elif "m" in token:
            call_type = "daiminkan"
        elif "k" in token:
            call_type = "kakan"
        elif "a" in token:
            call_type = "ankan"
        elif token.startswith("f"):
            call_type = "kita"
        else:
            call_type = "unknown"

        return {
            "type": call_type,
            "tiles": tiles,
            "marks": marks,
        }

    def _apply_call(self, closed: list[int], melds: list[str], call_info: dict[str, Any]) -> None:
        call_type = call_info["type"]
        if call_type == "chi":
            for tile in call_info["tiles"][1:]:
                self._remove_tile(closed, tile)
        elif call_type == "pon":
            for tile, mark in zip(call_info["tiles"], call_info["marks"]):
                if mark != "p":
                    self._remove_tile(closed, tile)
        elif call_type == "daiminkan":
            for tile, mark in zip(call_info["tiles"], call_info["marks"]):
                if mark != "m":
                    self._remove_tile(closed, tile)
        elif call_type == "ankan":
            for tile in call_info["tiles"]:
                self._remove_tile(closed, tile)
        elif call_type == "kakan":
            for tile, mark in zip(call_info["tiles"], call_info["marks"]):
                if mark == "k":
                    self._remove_tile(closed, tile)
        elif call_type == "kita" and call_info["tiles"]:
            self._remove_tile(closed, call_info["tiles"][0])
        melds.append(self._call_to_str(call_info))

    def _parse_discard(self, token: Any, draw_token: Any) -> dict[str, Any]:
        riichi = isinstance(token, str) and token.startswith("r")
        if token in (0, "0", "r0"):
            return {
                "tile": "0",
                "tile_code": None,
                "placeholder": True,
                "tsumogiri": False,
                "riichi": riichi,
            }

        core = token[1:] if riichi and isinstance(token, str) else token
        tsumogiri = core in (60, "60")
        if tsumogiri:
            core = draw_token
        if isinstance(core, str) and core.isdigit():
            core = int(core)
        tile_code = int(core) if isinstance(core, int) else None
        return {
            "tile": self._tile_to_str(core),
            "tile_code": tile_code,
            "placeholder": False,
            "tsumogiri": tsumogiri,
            "riichi": riichi,
        }

    def _remove_tile(self, hand: list[int], tile_code: int) -> bool:
        if tile_code in hand:
            hand.remove(tile_code)
            return True
        alternatives = {
            15: 51,
            25: 52,
            35: 53,
            51: 15,
            52: 25,
            53: 35,
        }
        alternative = alternatives.get(tile_code)
        if alternative is not None and alternative in hand:
            hand.remove(alternative)
            return True
        return False

    def _looks_like_json_path(self, source: str) -> bool:
        if source.startswith(("http://", "https://")) or "paipu=" in source:
            return False
        return source.endswith(".json") or "/" in source or "\\" in source

    def _to_relative_path(self, path: Path) -> str:
        if self.review_service is not None and getattr(self.review_service, "to_repo_relative_path", None):
            return self.review_service.to_repo_relative_path(path)
        if self.repo_root is not None:
            try:
                return path.relative_to(self.repo_root).as_posix()
            except ValueError:
                return path.name
        return path.as_posix()

    def _kan_count(self, melds: list[str]) -> int:
        return sum(1 for meld in melds if meld.startswith(("MINKAN", "ANKAN", "KAKAN")))

    def _entry_nplayers(self, entry: list[Any]) -> int:
        if not isinstance(entry, list):
            return 0
        has_result = bool(entry) and isinstance(entry[-1], list) and bool(entry[-1]) and isinstance(entry[-1][0], str)
        base = 5 if has_result else 4
        return max(0, (len(entry) - base) // 3)

    def _tile_sort_key(self, tile_code: int) -> tuple[int, int]:
        if tile_code == 51:
            return (1, 5)
        if tile_code == 52:
            return (2, 5)
        if tile_code == 53:
            return (3, 5)
        return (tile_code // 10, tile_code % 10)

    def _hand_to_strings(self, hand: list[int]) -> list[str]:
        return [self._tile_to_str(tile) for tile in sorted(hand, key=self._tile_sort_key)]

    def _tiles_to_strings(self, tiles: list[Any]) -> list[str]:
        return [self._tile_to_str(tile) for tile in tiles]

    def _tile_to_str(self, tile: Any) -> str:
        if isinstance(tile, str) and tile.isdigit():
            tile = int(tile)
        if not isinstance(tile, int):
            return str(tile)
        if tile == 60:
            return "??"
        if tile == 51:
            return "0m"
        if tile == 52:
            return "0p"
        if tile == 53:
            return "0s"

        suit = tile // 10
        number = tile % 10
        if suit == 1:
            return f"{number}m"
        if suit == 2:
            return f"{number}p"
        if suit == 3:
            return f"{number}s"
        if suit == 4:
            return self._HONORS.get(number, f"4{number}")
        return str(tile)

    def _call_to_str(self, call_info: dict[str, Any]) -> str:
        tiles = [self._tile_to_str(tile) for tile in call_info["tiles"]]
        if call_info["type"] == "chi":
            return f"CHI({','.join(tiles)})"
        if call_info["type"] == "pon":
            return f"PON({','.join(tiles)})"
        if call_info["type"] == "daiminkan":
            return f"MINKAN({','.join(tiles)})"
        if call_info["type"] == "ankan":
            return f"ANKAN({','.join(tiles)})"
        if call_info["type"] == "kakan":
            return f"KAKAN({','.join(tiles)})"
        if call_info["type"] == "kita":
            return f"KITA({','.join(tiles)})"
        return f"CALL({','.join(tiles)})"

    def _to_int_list(self, value: Any) -> list[int]:
        if not isinstance(value, list):
            return []
        result = []
        for item in value:
            if isinstance(item, (int, float)):
                result.append(int(item))
                continue
            try:
                result.append(int(item))
            except Exception:
                result.append(0)
        return result

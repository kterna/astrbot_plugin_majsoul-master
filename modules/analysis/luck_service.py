import asyncio
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from mahjong.shanten import Shanten
from ..review.constants import ROOM_MODE_MAP

logger = logging.getLogger("astrbot")

shanten_calc = Shanten()

# 日麻数理统计理论基准值配置（源自《科学する麻雀》与海量牌谱拟合）
BASELINES = {
    "4p": {
        "label": "四麻",
        "avg_shanten": 3.36,
        "good_hands": 17.5,
        "bad_hands": 42.0,
        "avg_dora": 0.67,
        "shanten_weight": 80.0,
        "good_weight": 60.0,
        "bad_weight": 40.0,
        "dora_weight": 25.0,
    },
    "3p": {
        "label": "三麻",
        "avg_shanten": 2.92,
        "good_hands": 38.0,
        "bad_hands": 21.5,
        "avg_dora": 1.20,
        "shanten_weight": 80.0,
        "good_weight": 55.0,
        "bad_weight": 45.0,
        "dora_weight": 20.0,
    },
}


def tenhou_to_34(t: int) -> Optional[int]:
    """将天凤/雀魂原始牌ID (11-53) 转换为 0-33 的牌种索引"""
    if t == 51:  # 赤5m
        return 4
    if t == 52:  # 赤5p
        return 13
    if t == 53:  # 赤5s
        return 22
    s, n = t // 10, t % 10
    if s == 1 and 1 <= n <= 9:  # 万子 0-8
        return n - 1
    if s == 2 and 1 <= n <= 9:  # 筒子 9-17
        return 9 + n - 1
    if s == 3 and 1 <= n <= 9:  # 索子 18-26
        return 18 + n - 1
    if s == 4 and 1 <= n <= 7:  # 字牌 27-33 (东南西北白发中)
        return 27 + n - 1
    return None


def is_dora_tile(tile_code: int, dora_indicator: int, is_3p: bool = False) -> bool:
    """判定某张牌是否是宝牌（含赤宝牌、指示牌宝牌，以及三麻特有的拔北宝牌）"""
    if tile_code in (51, 52, 53):
        return True  # 赤宝牌必为宝牌
    if is_3p and tile_code == 44:
        return True  # 三人麻将中北风固定为拔北宝牌

    ind_34 = tenhou_to_34(dora_indicator)
    tile_34 = tenhou_to_34(tile_code)
    if ind_34 is None or tile_34 is None:
        return False

    # 根据宝牌指示牌推算宝牌牌种
    if ind_34 < 9:  # 万
        if is_3p:
            expected = 8 if ind_34 == 0 else (0 if ind_34 == 8 else (ind_34 + 1) % 9)
        else:
            expected = (ind_34 + 1) % 9
    elif ind_34 < 18:  # 筒
        expected = 9 + (ind_34 - 9 + 1) % 9
    elif ind_34 < 27:  # 索
        expected = 18 + (ind_34 - 18 + 1) % 9
    elif ind_34 < 31:  # 风牌 (东->南->西->北->东)
        expected = 27 + (ind_34 - 27 + 1) % 4
    else:  # 三元牌 (白->发->中->白)
        expected = 31 + (ind_34 - 31 + 1) % 3

    return tile_34 == expected


def calculate_starting_ukeire(hand_34: List[int], current_shanten: int) -> Tuple[int, int]:
    """计算 13 张起手手牌的有效进张种类数和剩余有效张数"""
    advancing_tiles = 0
    advancing_types = 0
    for t in range(34):
        if hand_34[t] >= 4:
            continue
        hand_34[t] += 1
        can_advance = False
        for d in range(34):
            if hand_34[d] > 0:
                hand_34[d] -= 1
                if shanten_calc.calculate_shanten(hand_34) < current_shanten:
                    can_advance = True
                hand_34[d] += 1
                if can_advance:
                    break
        hand_34[t] -= 1
        if can_advance:
            advancing_types += 1
            advancing_tiles += (4 - hand_34[t])
    return advancing_types, advancing_tiles


class LuckAnalysisService:
    """雀魂近期牌运诊断分析服务（支持全段位识别与三麻/四麻自适应混合加权）"""

    def __init__(self, review_service):
        self.review_service = review_service

    async def analyze_luck(
        self,
        count: int = 5,
        account_uid: Optional[str] = None,
        target_nickname: Optional[str] = None,
        target_is_3p: Optional[bool] = None,
        target_room: Optional[str] = None,
        target_south: Optional[bool] = None,
        custom_records: Optional[List[Dict]] = None,
    ) -> Tuple[bool, str]:
        """拉取最近 count 场对局，逐局解析起手向听、进张率与运势得分（支持官方网关与牌谱屋双源）"""
        try:
            if not target_nickname and not account_uid and not custom_records:
                return False, "未指定查询昵称。请先发送「雀魂绑定 你的昵称」绑定账号后重试，或直接输入「雀魂牌运 你的昵称」。"

            effective_nickname = target_nickname
            if custom_records is not None:
                records = custom_records
                has_filter = False
            else:
                has_filter = (target_is_3p is not None or target_room is not None or target_south is not None)
                fetch_count = 30 if has_filter else count
                records = await self.review_service.fetch_recent_records(count=fetch_count, account_uid=account_uid)
                if not records:
                    return False, "未能获取到任何对局记录，请先打几把排位再来查询。"

                # 确定要分析的目标昵称
                if not effective_nickname and account_uid:
                    accounts = await self.review_service.store.list_accounts()
                    matched = next((a for a in accounts if a.uid == str(account_uid)), None)
                    if matched:
                        effective_nickname = matched.nickname or ""

            if not effective_nickname:
                return False, "未能确定要分析的玩家昵称，请使用「雀魂绑定 <昵称>」绑定账号后重试。"

            # 若有指定筛选条件，从获取的对局列表中精确定位
            if has_filter:
                filter_tags = []
                if target_is_3p is True:
                    filter_tags.append("三人")
                elif target_is_3p is False:
                    filter_tags.append("四人")
                if target_room:
                    filter_tags.append(target_room)
                if target_south is True:
                    filter_tags.append("南")
                elif target_south is False:
                    filter_tags.append("东")
                filter_desc = "".join(filter_tags)

                filtered_records = []
                for r in records:
                    m_id = r.get("mode_id", 0)
                    m_meta = ROOM_MODE_MAP.get(m_id, {})
                    if target_is_3p is not None and m_meta.get("is_3p") != target_is_3p:
                        continue
                    if target_room is not None and target_room not in m_meta.get("room", ""):
                        continue
                    if target_south is not None:
                        name = m_meta.get("name", "")
                        if target_south and "南" not in name:
                            continue
                        if not target_south and "东" not in name:
                            continue
                    filtered_records.append(r)
                    if len(filtered_records) >= count:
                        break

                if not filtered_records:
                    return False, f"在玩家「{effective_nickname}」最近 {len(records)} 场对局中，未找到符合【{filter_desc}】条件的记录。"
                records = filtered_records

            all_rounds = []
            game_summaries = []

            for idx, r in enumerate(records, 1):
                uuid = r.get("uuid", "")
                if not uuid:
                    continue

                success, msg, fetch_res = await self.review_service.fetch_raw_paipu(uuid)
                if not success or not fetch_res or not fetch_res.raw:
                    logger.warning(f"[majsoul-luck] 拉取牌谱 {uuid} 失败: {msg}")
                    continue
                raw = fetch_res.raw
                names = raw.get("name", [])
                target_seat = -1
                for s_idx, name in enumerate(names):
                    if effective_nickname and name.lower() == effective_nickname.lower():
                        target_seat = s_idx
                        break

                # 若按昵称未匹配到，尝试在 records['players'] 里找
                if target_seat == -1:
                    players = r.get("players", [])
                    matched_p = next(
                        (p for p in players if effective_nickname and p.get("nickname", "").lower() == effective_nickname.lower()),
                        None,
                    )
                    if matched_p:
                        target_seat = matched_p.get("seat", 0)
                    else:
                        continue

                # 解析该局房间模式与人数（从官方元数据 Ground Truth 读取）
                meta = raw.get("head", {}).get("config", {}).get("meta", {})
                mode_id = meta.get("mode_id", 0) or r.get("mode_id", 0)
                room_id = meta.get("room_id", 0)
                contest_uid = meta.get("contest_uid", 0)

                valid_players_count = len([n for n in names if n])
                is_3p_fallback = (valid_players_count == 3)

                if mode_id in ROOM_MODE_MAP:
                    mode_meta = ROOM_MODE_MAP[mode_id]
                    is_3p = mode_meta.get("is_3p", is_3p_fallback)
                    mode_name = mode_meta.get("name", "三人麻将" if is_3p else "四人麻将")
                    room_name = mode_meta.get("room", "")
                elif room_id > 0:
                    is_3p = is_3p_fallback
                    room_name = "友人场"
                    mode_name = "三人友人房" if is_3p else "四人友人房"
                elif contest_uid > 0:
                    is_3p = is_3p_fallback
                    room_name = "赛事场"
                    mode_name = "三人赛事" if is_3p else "四人赛事"
                else:
                    is_3p = is_3p_fallback
                    room_name = "其他"
                    mode_name = "三人麻将" if is_3p else "四人麻将"

                total_deck = 108 if is_3p else 136
                unseen_at_start = total_deck - 13 - 1

                game_rounds = []
                for round_idx, rd in enumerate(raw.get("log", [])):
                    hand_idx = 4 + target_seat * 3
                    if hand_idx >= len(rd):
                        continue
                    hand = rd[hand_idx]
                    dora_ind = rd[2][0] if len(rd) > 2 and len(rd[2]) > 0 else 0

                    t34 = [0] * 34
                    dora_count = 0
                    for t in hand:
                        idx_34 = tenhou_to_34(t)
                        if idx_34 is not None:
                            t34[idx_34] += 1
                        if is_dora_tile(t, dora_ind, is_3p=is_3p):
                            dora_count += 1

                    s = shanten_calc.calculate_shanten(t34)
                    u_types, u_count = calculate_starting_ukeire(t34, s)
                    u_rate = (u_count / unseen_at_start) * 100

                    # 解析单局胜负与得失分
                    last_item = rd[-1]
                    result_type = last_item[0] if isinstance(last_item, list) and last_item else "其他"
                    delta_scores = last_item[1] if len(last_item) > 1 and isinstance(last_item[1], list) else []
                    my_delta = delta_scores[target_seat] if target_seat < len(delta_scores) else 0

                    outcome = "平"
                    if result_type == "和了":
                        details = last_item[2] if len(last_item) > 2 else []
                        winner = details[0] if len(details) > 0 else -1
                        from_seat = details[1] if len(details) > 1 else -1
                        if winner == target_seat:
                            outcome = "和了"
                        elif from_seat == target_seat:
                            outcome = "放铳"
                        elif winner == from_seat:
                            outcome = "被自摸"
                        else:
                            outcome = "横移动"
                    elif result_type == "流局":
                        if my_delta > 0:
                            outcome = "流局听牌"
                        elif my_delta < 0:
                            outcome = "流局未听"
                        else:
                            outcome = "荒牌流局"

                    round_info = {
                        "round_num": round_idx + 1,
                        "shanten": s,
                        "ukeire_types": u_types,
                        "ukeire_count": u_count,
                        "ukeire_rate": u_rate,
                        "dora": dora_count,
                        "outcome": outcome,
                        "delta": my_delta,
                        "is_3p": is_3p,
                    }
                    game_rounds.append(round_info)
                    all_rounds.append(round_info)

                if not game_rounds:
                    continue

                avg_s = sum(x["shanten"] for x in game_rounds) / len(game_rounds)
                avg_d = sum(x["dora"] for x in game_rounds) / len(game_rounds)
                avg_u = sum(x["ukeire_rate"] for x in game_rounds) / len(game_rounds)
                wins = sum(1 for x in game_rounds if x["outcome"] == "和了")
                deal_ins = sum(1 for x in game_rounds if x["outcome"] == "放铳")

                players = r.get("players", [])
                target_p = next((p for p in players if p.get("nickname") == effective_nickname), {})
                sorted_p = sorted(players, key=lambda x: x.get("score", 0), reverse=True)
                my_rank = next((i + 1 for i, p in enumerate(sorted_p) if p.get("nickname") == effective_nickname), 0)

                game_summaries.append({
                    "game_num": idx,
                    "mode_name": mode_name,
                    "room_name": room_name,
                    "is_3p": is_3p,
                    "rank": my_rank,
                    "score": target_p.get("score", 0),
                    "pt": target_p.get("grading_score", 0),
                    "rounds": len(game_rounds),
                    "avg_shanten": avg_s,
                    "avg_dora": avg_d,
                    "avg_ukeire_rate": avg_u,
                    "wins": wins,
                    "deal_ins": deal_ins,
                })

            if not all_rounds:
                return False, "未能成功解析对局中的手牌数据。"

            # 统计对局模式分布
            count_3p = sum(1 for g in game_summaries if g.get("is_3p"))
            count_4p = len(game_summaries) - count_3p
            is_pure_3p = (count_4p == 0)
            is_pure_4p = (count_3p == 0)

            # 总体汇总计算
            total_r = len(all_rounds)
            overall_shanten = sum(x["shanten"] for x in all_rounds) / total_r
            overall_ukeire = sum(x["ukeire_rate"] for x in all_rounds) / total_r
            overall_dora = sum(x["dora"] for x in all_rounds) / total_r
            good_hands = sum(1 for x in all_rounds if x["shanten"] <= 2) / total_r * 100
            bad_hands = sum(1 for x in all_rounds if x["shanten"] >= 4) / total_r * 100
            total_wins = sum(1 for x in all_rounds if x["outcome"] == "和了") / total_r * 100
            total_deal_ins = sum(1 for x in all_rounds if x["outcome"] == "放铳") / total_r * 100

            # 逐局自适应基准偏差计算（支持纯三麻、纯四麻与三四麻混合加权）
            shanten_diffs = []
            good_diffs = []
            bad_diffs = []
            dora_diffs = []
            for r_info in all_rounds:
                bl = BASELINES["3p"] if r_info["is_3p"] else BASELINES["4p"]
                shanten_diffs.append(bl["avg_shanten"] - r_info["shanten"])
                good_diffs.append((1.0 if r_info["shanten"] <= 2 else 0.0) - bl["good_hands"] / 100.0)
                bad_diffs.append((1.0 if r_info["shanten"] >= 4 else 0.0) - bl["bad_hands"] / 100.0)
                dora_diffs.append(r_info["dora"] - bl["avg_dora"])

            avg_shanten_diff = sum(shanten_diffs) / total_r
            avg_good_diff = sum(good_diffs) / total_r
            avg_bad_diff = sum(bad_diffs) / total_r
            avg_dora_diff = sum(dora_diffs) / total_r

            luck_score = (
                50.0
                + avg_shanten_diff * 80.0
                + avg_good_diff * 55.0
                - avg_bad_diff * 45.0
                + avg_dora_diff * 20.0
            )
            luck_score = max(5.0, min(99.0, luck_score))

            rooms = [g.get("room_name") for g in game_summaries if g.get("room_name")]
            predominant_room = max(set(rooms), key=rooms.count) if rooms else ""
            modes = [g.get("mode_name") for g in game_summaries if g.get("mode_name")]
            predominant_mode = max(set(modes), key=modes.count) if modes else ""

            report = self._format_luck_report(
                nickname=effective_nickname or "雀士",
                is_pure_3p=is_pure_3p,
                is_pure_4p=is_pure_4p,
                count_3p=count_3p,
                count_4p=count_4p,
                predominant_mode=predominant_mode,
                room_name=predominant_room,
                sample_games=len(game_summaries),
                sample_rounds=total_r,
                luck_score=luck_score,
                overall_shanten=overall_shanten,
                avg_shanten_diff=avg_shanten_diff,
                good_hands=good_hands,
                avg_good_diff=avg_good_diff,
                bad_hands=bad_hands,
                avg_bad_diff=avg_bad_diff,
                overall_ukeire=overall_ukeire,
                overall_dora=overall_dora,
                avg_dora_diff=avg_dora_diff,
                total_wins=total_wins,
                total_deal_ins=total_deal_ins,
                game_summaries=game_summaries,
            )
            return True, report

        except Exception as e:
            logger.error(f"[majsoul-luck] 牌运分析执行异常: {e}", exc_info=True)
            return False, f"牌运分析计算失败: {str(e)}"

    def _format_luck_report(
        self,
        nickname: str,
        is_pure_3p: bool,
        is_pure_4p: bool,
        count_3p: int,
        count_4p: int,
        predominant_mode: str,
        room_name: str,
        sample_games: int,
        sample_rounds: int,
        luck_score: float,
        overall_shanten: float,
        avg_shanten_diff: float,
        good_hands: float,
        avg_good_diff: float,
        bad_hands: float,
        avg_bad_diff: float,
        overall_ukeire: float,
        overall_dora: float,
        avg_dora_diff: float,
        total_wins: float,
        total_deal_ins: float,
        game_summaries: List[Dict[str, Any]],
    ) -> str:
        """排版格式化牌运诊断输出"""
        if luck_score >= 80:
            tier_title = "欧皇神抽 · 大顺调 🌟"
            advice = "天命所归！起手向听充盈、宝牌在握，请保持积极进攻，果断立直攻擂！"
        elif luck_score >= 65:
            tier_title = "运势偏强 · 小顺调 ✨"
            advice = "配牌扎实平稳，进张节奏流畅。按既定策略稳健推进即可持续上分。"
        elif luck_score >= 45:
            tier_title = "气运平稳 · 常态调 ⚖️"
            advice = "起手与摸调处于大数定理均值区间，胜负关键在于牌效取舍与防守细腻度。"
        elif luck_score >= 30:
            tier_title = "气运受阻 · 偏恶调 🌧️"
            advice = "起手向听较深、优质好型匮乏。切勿因焦躁盲目进攻，多注重兜牌弃和，等待转运。"
        else:
            tier_title = "深渊恶调 · 制裁拉满 ⚡"
            advice = "系统发牌恶意拉满！配牌荒漠且摸调滞后。建议暂停排位修整心态，或以纯防守防跌分！"

        if "玉" in room_name or "王座" in room_name:
            advice += "（玉场环境对手弃和敏锐，深向听时更须绝对弃和防点大铳）"
        elif "金" in room_name:
            advice += "（金场环境进攻较莽，即便恶调只要做好坚决防守，吃他人放铳红利亦能避四）"

        if is_pure_3p:
            mode_header = f"模式：{predominant_mode or '三人麻将'}"
            bl_label = "三麻"
            s_metric = f"均 {overall_shanten:.2f} 向听 (基准 2.92, 偏差 {avg_shanten_diff:+.2f})"
            good_metric = f"{good_hands:.1f}% (基准 38.0%, 偏差 {avg_good_diff * 100:+.1f}%)"
            bad_metric = f"{bad_hands:.1f}% (基准 21.5%, 偏差 {avg_bad_diff * 100:+.1f}%)"
            dora_metric = f"均 {overall_dora:.2f} 张 (基准 1.20 张, 偏差 {avg_dora_diff:+.2f})"
        elif is_pure_4p:
            mode_header = f"模式：{predominant_mode or '四人麻将'}"
            bl_label = "四麻"
            s_metric = f"均 {overall_shanten:.2f} 向听 (基准 3.36, 偏差 {avg_shanten_diff:+.2f})"
            good_metric = f"{good_hands:.1f}% (基准 17.5%, 偏差 {avg_good_diff * 100:+.1f}%)"
            bad_metric = f"{bad_hands:.1f}% (基准 42.0%, 偏差 {avg_bad_diff * 100:+.1f}%)"
            dora_metric = f"均 {overall_dora:.2f} 张 (基准 0.67 张, 偏差 {avg_dora_diff:+.2f})"
        else:
            mode_header = f"模式：三麻/四麻混合 (三麻 {count_3p} 场 / 四麻 {count_4p} 场)"
            bl_label = "三/四麻自适应加权"
            s_metric = f"均 {overall_shanten:.2f} 向听 (逐局加权净偏差 {avg_shanten_diff:+.2f})"
            good_metric = f"{good_hands:.1f}% (综合预期超额 {avg_good_diff * 100:+.1f}%)"
            bad_metric = f"{bad_hands:.1f}% (综合预期超额 {avg_bad_diff * 100:+.1f}%)"
            dora_metric = f"均 {overall_dora:.2f} 张 (综合期望净偏差 {avg_dora_diff:+.2f})"

        lines = [
            f"🀄【雀魂近期牌运诊断报告】",
            f"👤 玩家：{nickname} | {mode_header} | 样本量：最近 {sample_games} 场 (共 {sample_rounds} 局)",
            f"📊 综合牌运评分：{luck_score:.1f} / 100 【{tier_title}】",
            "",
            f"📈 核心运势指标（对比{bl_label}数理基准）：",
            f"• 起手向听：{s_metric}",
            f"• 优质配牌(≤2向听)：{good_metric}",
            f"• 恶劣配牌(≥4向听)：{bad_metric}",
            f"• 首巡进张率：均 {overall_ukeire:.1f}% (首巡摸进有效牌概率)",
            f"• 起手宝牌：{dora_metric}",
            f"• 战绩表现：局和率 {total_wins:.1f}% | 局铳率 {total_deal_ins:.1f}%",
            "",
            "🎲 近期各场走势：",
        ]

        for g in game_summaries:
            g_is_3p = g.get("is_3p", False)
            g_bl = BASELINES["3p"] if g_is_3p else BASELINES["4p"]
            g_diff = g_bl["avg_shanten"] - g["avg_shanten"]
            icon = "🌟" if g_diff > 0.30 else ("✨" if g_diff > 0.08 else ("⚖️" if g_diff >= -0.08 else ("🌧️" if g_diff >= -0.30 else "⚡")))
            score_str = f"{g['pt']:+d}pt" if g["pt"] != 0 else f"{g['score']:+d}"
            lines.append(
                f"{g['game_num']}. {g['rank']}位({score_str}) | 【{g['mode_name']}】 | {g['rounds']}局 | 均向听 {g['avg_shanten']:.2f} {icon} | 和{g['wins']} 铳{g['deal_ins']}"
            )

        lines.extend([
            "",
            f"💡 牌仙诊断建议：",
            f"{advice}",
        ])

        return "\n".join(lines)

from typing import Dict, Any, List

class MajsoulFormatter:
    """雀魂数据格式化工具类"""
    
    @staticmethod
    def format_query_result(player_data: Dict[str, Any], mode: str = "4") -> str:
        """格式化雀魂查询结果
        
        Args:
            player_data: 玩家数据
            mode: 游戏模式，3为三麻，4为四麻
        
        Returns:
            格式化后的查询结果文本
        """
        # 提取基本信息
        nickname = player_data.get("nickname", "未知")
        level = player_data.get("level", {}).get("id", 0)
        level_name = player_data.get("level", {}).get("name", "未知")
        
        # 计算胜率
        count_games = player_data.get("count_games", 0)
        count_win = player_data.get("count_win", 0)
        win_rate = round(count_win / count_games * 100, 2) if count_games > 0 else 0
        
        # 获取段位数据
        level3 = player_data.get("level3", {})
        level4 = player_data.get("level4", {})
        
        current_level = level3 if mode == "3" else level4
        level_id = current_level.get("id", 0)
        level_score = current_level.get("score", 0)
        max_level_id = current_level.get("max_id", 0)
        max_level_name = current_level.get("max_name", "未知")
        
        # 构建结果文本
        result = []
        result.append(f"【{nickname}】的雀魂{'' if mode == '4' else '三麻'}战绩")
        result.append(f"段位: {level_name}")
        result.append(f"当前PT: {level_score}")
        result.append(f"最高段位: {max_level_name}")
        result.append(f"总对局数: {count_games}")
        result.append(f"总胜局数: {count_win}")
        result.append(f"胜率: {win_rate}%")
        
        # 添加更多统计信息
        if "platform_statistics" in player_data:
            stats = player_data["platform_statistics"]
            result.append("\n【更多统计】")
            
            # 添加平均顺位
            avg_rank = stats.get("avg_rank", 0)
            if avg_rank:
                result.append(f"平均顺位: {avg_rank:.2f}")
            
            # 添加役满信息
            yakuman_count = stats.get("yakuman_count", 0)
            if yakuman_count:
                result.append(f"役满次数: {yakuman_count}")
            
            # 添加连对率等高级统计
            continue_win_max = stats.get("continue_win_max", 0)
            if continue_win_max:
                result.append(f"最大连庄: {continue_win_max}")
            
            fly_count = stats.get("fly_count", 0)
            if fly_count:
                result.append(f"飞人次数: {fly_count}")
        
        return "\n".join(result)
    
    @staticmethod
    def format_records_result(records_data: Dict[str, Any], mode: str = "4") -> str:
        """格式化牌谱查询结果
        
        Args:
            records_data: 牌谱数据
            mode: 游戏模式，3为三麻，4为四麻
        
        Returns:
            格式化后的牌谱查询结果文本
        """
        if not records_data or "list" not in records_data:
            return "未找到牌谱记录"
        
        records = records_data["list"]
        if not records:
            return "未找到牌谱记录"
        
        result = []
        result.append(f"【最近{len(records)}场{'' if mode == '4' else '三麻'}对局】")
        
        for i, record in enumerate(records):
            # 对局时间
            start_time = record.get("start_time", "未知时间")
            start_time_formatted = start_time.replace("T", " ").split("+")[0] if isinstance(start_time, str) else "未知时间"
            
            # 对局模式和场次
            room_type = "三麻" if mode == "3" else "四麻"
            room_level = ""
            if "config" in record and "meta" in record["config"]:
                meta = record["config"]["meta"]
                if "mode_id" in meta:
                    mode_id = meta["mode_id"]
                    if mode_id == 1:
                        room_level = "金之间"
                    elif mode_id == 2:
                        room_level = "玉之间"
                    elif mode_id == 3:
                        room_level = "王座之间"
            
            # 对局结果
            result.append(f"\n[{i+1}] {start_time_formatted} {room_type}{room_level}")
            
            if "accounts" in record:
                accounts = record["accounts"]
                for j, account in enumerate(accounts):
                    nickname = account.get("nickname", "未知")
                    score = account.get("score", 0)
                    result.append(f"{j+1}位: {nickname} ({score:+})")
            
        return "\n".join(result)
    
    @staticmethod
    def format_detailed_stats(player_data: Dict[str, Any], mode: str = "4", room_level: str = "0") -> str:
        """格式化详细统计数据
        
        Args:
            player_data: 玩家数据
            mode: 游戏模式，3为三麻，4为四麻
            room_level: 房间等级，0为全部，1为金之间，2为玉之间，3为王座之间
        
        Returns:
            格式化后的详细统计数据文本
        """
        nickname = player_data.get("nickname", "未知")
        
        # 获取特定场次的统计数据
        room_stats = {}
        if "extended_stats" in player_data:
            extended_stats = player_data["extended_stats"]
            
            # 根据模式和房间等级获取相应数据
            key = f"mode{mode}_level{room_level}" if room_level != "0" else f"mode{mode}"
            if key in extended_stats:
                room_stats = extended_stats[key]
        
        # 如果没有找到特定场次的数据，返回基本信息
        if not room_stats:
            return f"未找到{nickname}在{'三麻' if mode == '3' else '四麻'}{MajsoulFormatter._get_room_name(room_level)}的详细数据"
        
        # 构建结果文本
        result = []
        result.append(f"【{nickname}】在{'三麻' if mode == '3' else '四麻'}{MajsoulFormatter._get_room_name(room_level)}的详细战绩")
        
        # 对局数和胜率
        count_games = room_stats.get("count_games", 0)
        count_win = room_stats.get("count_win", 0)
        win_rate = round(count_win / count_games * 100, 2) if count_games > 0 else 0
        
        result.append(f"对局数: {count_games}")
        result.append(f"胜局数: {count_win}")
        result.append(f"胜率: {win_rate}%")
        
        # 各个位次的数量
        rank_counts = {}
        for i in range(1, 5 if mode == "4" else 4):
            rank_key = f"rank{i}"
            rank_counts[i] = room_stats.get(rank_key, 0)
        
        result.append("\n【位次分布】")
        for rank, count in rank_counts.items():
            percentage = round(count / count_games * 100, 2) if count_games > 0 else 0
            result.append(f"{rank}位: {count}次 ({percentage}%)")
        
        # 平均得点
        avg_score = room_stats.get("avg_score", 0)
        if avg_score:
            result.append(f"\n平均得点: {avg_score:.1f}")
        
        # 最高得点
        max_score = room_stats.get("max_score", 0)
        if max_score:
            result.append(f"最高得点: {max_score}")
        
        # 役满和累计PT
        yakuman_count = room_stats.get("yakuman_count", 0)
        if yakuman_count:
            result.append(f"役满次数: {yakuman_count}")
        
        total_pt_gain = room_stats.get("total_pt_gain", 0)
        if total_pt_gain:
            result.append(f"累计PT收益: {total_pt_gain:+}")
        
        return "\n".join(result)
    
    @staticmethod
    def _get_room_name(room_level: str) -> str:
        """获取房间名称
        
        Args:
            room_level: 房间等级，0为全部，1为金之间，2为玉之间，3为王座之间
        
        Returns:
            房间名称
        """
        if room_level == "1":
            return "金之间"
        elif room_level == "2":
            return "玉之间" 
        elif room_level == "3":
            return "王座之间"
        else:
            return "" 

class MahjongFormatter:
    """麻将分析结果格式化工具类"""
    
    @staticmethod
    def format_hand_analysis(analysis_result: Dict) -> str:
        """格式化完整的手牌分析结果
        
        Args:
            analysis_result: 手牌分析结果字典
        
        Returns:
            格式化后的分析结果文本
        """
        if not analysis_result.get("success", True):
            return f"分析失败: {analysis_result.get('error', '未知错误')}"
        
        hand_str = analysis_result.get("hand_str", "")
        total_tiles = analysis_result.get("total_tiles", 0)
        
        result = [f"手牌: {hand_str}", f"手牌数: {total_tiles}张"]
        
        # 向听数信息
        shanten = analysis_result.get("shanten", {})
        if shanten:
            shanten_num = shanten.get("shanten", 0)
            if shanten_num == -1:
                result.append("和牌")
            elif shanten_num == 0:
                result.append("听牌")
            else:
                result.append(f"向听数: {shanten_num}")
        
        # 和牌信息
        hand_value = analysis_result.get("hand_value", {})
        if hand_value and hand_value.get("success", False):
            result.append(MahjongFormatter.format_hand_value(hand_value))
        
        # 打牌建议
        ukeire = analysis_result.get("ukeire", {})
        if ukeire and ukeire.get("success", False):
            result.append(MahjongFormatter.format_ukeire(ukeire))
        
        # 听牌/待摸分析
        waiting_tiles = analysis_result.get("waiting_tiles", [])
        if waiting_tiles and total_tiles == 13:
            if shanten.get("shanten", -1) == 0:
                result.append(MahjongFormatter.format_waiting_tiles(waiting_tiles, "听牌"))
            else:
                result.append(MahjongFormatter.format_waiting_tiles(waiting_tiles, "进张"))
        
        return "\n".join(result)
    
    @staticmethod
    def format_hand_value(hand_value: Dict) -> str:
        """格式化和牌分析结果
        
        Args:
            hand_value: 和牌分析结果字典
        
        Returns:
            格式化后的和牌分析文本
        """
        if not hand_value.get("success", True):
            return "无役，不能和牌"
        
        han = hand_value.get("han", 0)
        fu = hand_value.get("fu", 0)
        cost = hand_value.get("cost", {}).get("main", 0)
        is_yakuman = hand_value.get("is_yakuman", False)
        
        result = ["和牌分析:"]
        if is_yakuman:
            result.append("役满")
        else:
            result.append(f"番数: {han}, 符数: {fu}")
        
        result.append(f"点数: {cost}")
        
        # 添加役种信息
        yaku_list = hand_value.get("yaku", [])
        if yaku_list:
            result.append("役种:")
            for yaku in yaku_list:
                han_display = f"{yaku.get('han', 0)}番"
                result.append(f"- {yaku.get('chinese_name', '未知')} ({han_display})")
        
        return "\n".join(result)
    
    @staticmethod
    def format_ukeire(ukeire: Dict) -> str:
        """格式化进张分析结果
        
        Args:
            ukeire: 进张分析结果字典
        
        Returns:
            格式化后的进张分析文本
        """
        if not ukeire.get("success", True):
            return "进张分析失败"
        
        result = ["打牌建议:"]
        
        options = ukeire.get("options", [])
        for i, option in enumerate(options, 1):
            discard = option.get("tile_to_discard", "")
            ukeire_count = option.get("ukeire", 0)
            waiting_str = option.get("waiting_tiles_str", "")
            
            result.append(f"{i}. 打{discard}: 进张数={ukeire_count}")
            result.append(f"   待张：{waiting_str}")
        
        return "\n".join(result)
    
    @staticmethod
    def format_waiting_tiles(waiting_tiles: List[Dict], tile_type: str = "听牌") -> str:
        """格式化待张信息
        
        Args:
            waiting_tiles: 待张列表
            tile_type: 类型描述，如"听牌"或"进张"
        
        Returns:
            格式化后的待张文本
        """
        if not waiting_tiles:
            return f"无{tile_type}"
        
        # 计算总数
        total_count = sum(tile.get("count", 0) for tile in waiting_tiles)
        
        result = []
        if tile_type == "听牌":
            result.append(f"听牌！共{total_count}张铳牌")
            result.append(f"听牌张：{MahjongFormatter._format_tile_list(waiting_tiles)}")
        else:
            result.append(f"进张数：{total_count}张")
            result.append(f"进张：{MahjongFormatter._format_tile_list(waiting_tiles)}")
        
        return "\n".join(result)
    
    @staticmethod
    def _format_tile_list(tiles: List[Dict]) -> str:
        """格式化牌列表
        
        Args:
            tiles: 牌列表
        
        Returns:
            格式化后的牌列表文本
        """
        tiles_str = []
        for tile in tiles:
            tile_str = tile.get("tile_str", "")
            count = tile.get("count", 0)
            tiles_str.append(f"{tile_str}:{count}张")
        return "、".join(tiles_str) 
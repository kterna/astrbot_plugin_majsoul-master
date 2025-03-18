from typing import Dict, Any

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
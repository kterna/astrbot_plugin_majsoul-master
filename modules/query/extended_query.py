from typing import Dict, List, Optional, Tuple, Union, Any, Literal
import asyncio
import re
import aiohttp
import json
import urllib.parse
from datetime import datetime
from functools import wraps

# 类型别名
GameMode = Literal["3", "4"]
RoomLevel = Literal["0", "1", "2", "3"]
JsonDict = Dict[str, Any]

# 常量定义
START_TIME = 1262304000000 
DEFAULT_TIMEOUT = 10  # 请求超时时间
DEFAULT_LIMIT = 5    # 默认查询记录数
DEFAULT_MODE = "4"   # 默认四人麻将
DEFAULT_ROOM = "1"   # 默认金之间
DEFAULT_DIRECTION = True  # 默认南场

# 错误信息
ERROR_MESSAGES = {
                -1: "未找到玩家",
                -2: "查询超时，请稍后再试",
                -3: "API服务器错误",
    -4: "参数错误",
    -404: "网络连接错误",
    -500: "服务器内部错误"
}

# 房间名称
ROOM_NAMES = {
    "0": "全部场次",
    "1": "金之间",
    "2": "玉之间",
    "3": "王座之间"
}

# 游戏模式映射
GAME_MODES = {
    # 四人南
    ("1", True, "4"): "9",   # 金南
    ("2", True, "4"): "12",  # 玉南
    ("3", True, "4"): "16",  # 王座南
    # 四人东
    ("1", False, "4"): "8",  # 金东
    ("2", False, "4"): "11", # 玉东
    ("3", False, "4"): "15", # 王座东
    # 三人南
    ("1", True, "3"): "22",  # 金南
    ("2", True, "3"): "24",  # 玉南
    ("3", True, "3"): "26",  # 王座南
    # 三人东
    ("1", False, "3"): "21", # 金东
    ("2", False, "3"): "23", # 玉东
    ("3", False, "3"): "25"  # 王座东
}

class APIError(Exception):
    """API错误"""
    def __init__(self, code: int, message: str = None):
        self.code = code
        self.message = message or ERROR_MESSAGES.get(code, f"未知错误: {code}")
        super().__init__(self.message)

def handle_api_error(func):
    """处理API错误的装饰器"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            result = await func(*args, **kwargs)
            return True, result
        except APIError as e:
            return False, e.message
        except Exception as e:
            return False, f"未知错误: {str(e)}"
    return wrapper

class MajsoulAPI:
    """雀魂API客户端"""
    
    def __init__(self, base_url: str = "https://5-data.amae-koromo.com/api/v2"):
        """初始化API客户端"""
        self.base_url = base_url.rstrip('/')
        self.pl4_url = f"{self.base_url}/pl4"
        self.pl3_url = f"{self.base_url}/pl3"
        self.session: Optional[aiohttp.ClientSession] = None
        self.default_headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36",
            "Accept": "application/json"
        }
        
    async def ensure_session(self) -> None:
        """确保会话已创建"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(headers=self.default_headers)
            
    async def close(self) -> None:
        """关闭会话"""
        if self.session and not self.session.closed:
            await self.session.close()
        self.session = None
        
    async def request(self, url: str) -> JsonDict:
        """发送HTTP请求并返回JSON数据"""
        await self.ensure_session()
        try:
            async with self.session.get(url, timeout=DEFAULT_TIMEOUT) as response:
                if response.status != 200:
                    raise APIError(-404)
                
                try:
                    return await response.json()
                except json.JSONDecodeError as e:
                    raise APIError(-3)
        except asyncio.TimeoutError:
            raise APIError(-2)
        except APIError:
            raise
        except Exception as e:
            raise APIError(-404)

    def _get_api_url(self, mode: GameMode) -> str:
        """获取API基础URL"""
        return self.pl4_url if mode == "4" else self.pl3_url

    def _get_game_mode(self, room_level: RoomLevel, is_south: bool, mode: GameMode = DEFAULT_MODE) -> str:
        """获取游戏模式代码
        
        Args:
            room_level: 房间等级 ("1"=金, "2"=玉, "3"=王座)
            is_south: 是否为南场
            mode: 游戏模式 ("3"=三麻, "4"=四麻)
            
        Returns:
            str: 游戏模式代码
        """
        key = (room_level, is_south, mode)
        default_key = ("1", True, mode)  # 默认为对应模式的金之间南场
        return GAME_MODES.get(key, GAME_MODES[default_key])

    async def get_player_info(self, nickname: str, mode: GameMode) -> JsonDict:
        """获取玩家信息"""
        encoded_nickname = urllib.parse.quote(nickname)
        url = f"{self._get_api_url(mode)}/search_player/{encoded_nickname}"
        result = await self.request(url)
        if not result or not isinstance(result, list) or not result[0].get("id"):
            raise APIError(-1)
        return result[0]

    @handle_api_error
    async def query_stats(self, nickname: str, mode: GameMode = DEFAULT_MODE, 
                         room_level: RoomLevel = DEFAULT_ROOM, is_south: bool = DEFAULT_DIRECTION) -> str:
        """查询玩家战绩统计"""
        player = await self.get_player_info(nickname, mode)
        game_mode = self._get_game_mode(room_level, is_south, mode)
        current_timestamp = int(datetime.now().timestamp())
        
        url = f"{self._get_api_url(mode)}/player_stats/{player['id']}/{START_TIME}/{current_timestamp}?mode={game_mode}"
        stats = await self.request(url)
        
        return self.format_stats(stats, room_level, mode, nickname)

    @handle_api_error
    async def query_records(self, nickname: str, mode: GameMode = DEFAULT_MODE, limit: int = DEFAULT_LIMIT, is_south: bool = DEFAULT_DIRECTION) -> str:
        """查询玩家对局记录"""
        player = await self.get_player_info(nickname, mode)
        current_timestamp = int(datetime.now().timestamp())
        game_mode = self._get_game_mode("1", is_south, mode)  # 使用传入的场风参数
        
        url = f"{self._get_api_url(mode)}/player_records/{player['id']}/{START_TIME}/{current_timestamp}?limit={limit}&mode={game_mode}"
        records = await self.request(url)
        
        if not records or not isinstance(records, list):
            raise APIError(-1)
            
        return self.format_records(records, mode)

    @handle_api_error
    async def query_extended_stats(self, nickname: str, mode: GameMode, room_level: RoomLevel, is_south: bool) -> str:
        """查询玩家详细战绩统计"""
        player = await self.get_player_info(nickname, mode)
        game_mode = self._get_game_mode(room_level, is_south, mode)
        current_timestamp = int(datetime.now().timestamp())
        
        url = f"{self._get_api_url(mode)}/player_extended_stats/{player['id']}/1262304000000/{current_timestamp}?mode={game_mode}"
        data = await self.request(url)
        
        room_name = ROOM_NAMES.get(room_level, "全部场次")
        mode_name = "四麻" if mode == "4" else "三麻"
        stats_text = [
            f"【{room_name} {mode_name}详细统计】",
            f"玩家：{nickname}",
            "",
            self.format_extended_stats(data)
        ]
        
        return "\n".join(stats_text)

    def format_stats(self, stats: Dict, room_level: str, mode: str, nickname: str) -> str:
        """格式化统计数据"""
        try:
            if not stats:
                return "数据不完整"
                
            room_name = ROOM_NAMES.get(room_level, "全部场次")
            rank_rates = stats.get("rank_rates", [])
            rank_avg_score = stats.get("rank_avg_score", [])
            
            # 基础信息
            lines = [
                f"【{room_name} {'四麻' if mode == '4' else '三麻'}统计】",
                f"玩家: {nickname}",
                f"总场次: {stats.get('count', 0)}",
                f"平均顺位: {stats.get('avg_rank', 0):.2f}",
                f"飞人率: {stats.get('negative_rate', 0) * 100:.1f}%",
                "顺位分布:"
            ]
            
            # 根据模式添加顺位分布
            if mode == "4":
                for i in range(4):
                    rate = rank_rates[i] if i < len(rank_rates) else 0
                    score = rank_avg_score[i] if i < len(rank_avg_score) else 0
                    lines.append(f"  {i+1}位: {rate*100:.1f}% (平均得点: {score})")
            else:  # 三麻模式
                for i in range(3):
                    rate = rank_rates[i] if i < len(rank_rates) else 0
                    score = rank_avg_score[i] if i < len(rank_avg_score) else 0
                    lines.append(f"  {i+1}位: {rate*100:.1f}% (平均得点: {score})")
            
            # 如果有段位信息
            if "level" in stats:
                level = stats["level"]
                max_level = stats.get("max_level", {})
                lines.extend([
                    "",
                    "【段位信息】",
                    f"当前段位分数: {level.get('score', 0)}",
                    f"最近变化: {level.get('delta', 0)}",
                    f"最高段位分数: {max_level.get('score', 0)}"
                ])
            
            return "\n".join(lines)
            
        except Exception as e:
            return "格式化数据失败"
            
    def format_records(self, records: List[Dict], mode: str) -> str:
        """格式化对局记录
        
        Args:
            records: 对局记录列表
            mode: 游戏模式 ("3"=三麻, "4"=四麻)
            
        Returns:
            str: 格式化后的对局记录
        """
        try:
            if not records:
                return "暂无对局记录"
                
            lines = [f"【最近{'四麻' if mode == '4' else '三麻'}对局记录】"]
            
            for record in records:
                # 获取基本信息
                time_str = datetime.fromtimestamp(record.get("startTime", 0)).strftime("%Y-%m-%d %H:%M:%S")
                players = record.get("players", [])
                
                if not players:
                    continue
                
                # 按分数排序
                players.sort(key=lambda x: x.get("score", 0), reverse=True)
                
                # 生成对局信息
                lines.extend([
                    f"时间：{time_str}",
                    "对局玩家："
                ])
                
                # 显示玩家信息
                for i, player in enumerate(players, 1):
                    level_str = f"(Lv.{player['level']//100:d})" if "level" in player else ""
                    score_str = f"{player.get('score', 0):+d}"
                    lines.append(f"  {i}位 {player['nickname']}{level_str} {score_str}")
                
                lines.append("---")
                
            return "\n".join(lines)
            
        except Exception as e:
            return "格式化记录失败"
    
    def format_extended_stats(self, data: JsonDict) -> str:
        """格式化详细统计数据
        
        Args:
            data: API返回的详细统计数据
            
        Returns:
            str: 格式化后的统计信息
        """
        if not data:
            return "未找到统计数据"
            
        # 基础统计
        basic_stats = [
            f"总对局数：{data.get('count', 0)}局",
            f"和牌率：{data.get('和牌率', 0):.1%}",
            f"放铳率：{data.get('放铳率', 0):.1%}",
            f"流局率：{data.get('流局率', 0):.1%}",
            f"副露率：{data.get('副露率', 0):.1%}",
            f"立直率：{data.get('立直率', 0):.1%}",
            f"默听率：{data.get('默听率', 0):.1%}",
        ]
        
        # 和牌相关
        win_stats = [
            f"平均打点：{data.get('平均打点', 0)}",
            f"自摸率：{data.get('自摸率', 0):.1%}",
            f"一发率：{data.get('一发率', 0):.1%}",
            f"里宝率：{data.get('里宝率', 0):.1%}",
            f"最大连庄：{data.get('最大连庄', 0)}",
            f"和了巡数：{data.get('和了巡数', 0):.1f}",
        ]
        
        # 立直相关
        riichi_stats = [
            f"立直和了率：{data.get('立直后和牌率', 0):.1%}",
            f"立直收支：{data.get('立直收支', 0)}",
            f"立直好型率：{data.get('立直好型', 0):.1%}",
            f"立直多面率：{data.get('立直多面', 0):.1%}",
            f"振听立直率：{data.get('振听立直率', 0):.1%}",
            f"先制率：{data.get('先制率', 0):.1%}",
            f"追立率：{data.get('追立率', 0):.1%}",
            f"被追率：{data.get('被追率', 0):.1%}",
        ]
        
        # 防守相关
        defense_stats = [
            f"平均铳点：{data.get('平均铳点', 0)}",
            f"放铳时立直率：{data.get('放铳时立直率', 0):.1%}",
            f"放铳时副露率：{data.get('放铳时副露率', 0):.1%}",
            f"立直后放铳率：{data.get('立直后放铳率', 0):.1%}",
            f"副露后放铳率：{data.get('副露后放铳率', 0):.1%}",
            f"被炸率：{data.get('被炸率', 0):.1%}",
            f"平均被炸点数：{data.get('平均被炸点数', 0)}",
        ]
        
        # 效率相关
        efficiency_stats = [
            f"打点效率：{data.get('打点效率', 0)}",
            f"铳点损失：{data.get('铳点损失', 0)}",
            f"净打点效率：{data.get('净打点效率', 0)}",
            f"平均起手向听：{data.get('平均起手向听', 0):.1f}",
        ]
        
        # 特殊记录
        special_stats = []
        if data.get('役满', 0) > 0:
            special_stats.append(f"役满：{data['役满']}次")
        if data.get('累计役满', 0) > 0:
            special_stats.append(f"累计役满：{data['累计役满']}次")
        if data.get('W立直', 0) > 0:
            special_stats.append(f"W立直：{data['W立直']}次")
        if data.get('最大累计番数', 0) > 0:
            special_stats.append(f"最大累计番数：{data['最大累计番数']}")
            
        # 最近大铳
        recent_deal_in = ""
        if data.get('最近大铳'):
            deal_in = data['最近大铳']
            fans = [f"{fan['label']}({fan['count']})" for fan in deal_in.get('fans', [])]
            if fans:
                recent_deal_in = f"\n最近大铳：{' '.join(fans)}"
        
        # 组合所有统计数据
        sections = [
            ("基础统计", basic_stats),
            ("和牌统计", win_stats),
            ("立直统计", riichi_stats),
            ("防守统计", defense_stats),
            ("效率统计", efficiency_stats),
        ]
        
        result = []
        for title, stats in sections:
            if stats:
                result.append(f"【{title}】")
                result.extend(stats)
                result.append("")
                
        if special_stats:
            result.append("【特殊记录】")
            result.extend(special_stats)
            result.append("")
            
        if recent_deal_in:
            result.append(recent_deal_in)
            
        return "\n".join(result).strip()

class MajsoulQuery:
    """雀魂查询功能"""
    
    def __init__(self, api_url: str = "https://5-data.amae-koromo.com/api/v2"):
        """初始化查询功能"""
        self.api = MajsoulAPI(api_url)
        
    async def close(self) -> None:
        """关闭API连接"""
        await self.api.close()
        
    async def query_stats(self, nickname: str, mode: GameMode = DEFAULT_MODE,
                         room_level: RoomLevel = DEFAULT_ROOM, is_south: bool = DEFAULT_DIRECTION) -> Tuple[bool, str]:
        """查询玩家战绩统计"""
        return await self.api.query_stats(nickname, mode, room_level, is_south)
        
    async def query_records(self, nickname: str, mode: GameMode = DEFAULT_MODE,
                          limit: int = DEFAULT_LIMIT) -> Tuple[bool, str]:
        """查询玩家对局记录"""
        try:
            # 从命令中解析参数
            _, room_level, is_south, game_mode = self.parse_command_args(nickname)
            return await self.api.query_records(nickname, game_mode, limit, is_south)
        except Exception as e:
            return False, f"查询失败: {str(e)}"

    async def query_extended_stats(self, nickname: str, mode: GameMode, room_level: RoomLevel, is_south: bool) -> Tuple[bool, str]:
        """查询玩家详细战绩统计"""
        return await self.api.query_extended_stats(nickname, mode, room_level, is_south)
        
    def parse_command_args(self, args: str) -> tuple[str, RoomLevel, bool, GameMode]:
        """解析命令参数
        
        Args:
            args: 命令参数字符串（如"kterna 三人金东"）
            
        Returns:
            tuple: (昵称, 房间等级, 是否南场, 游戏模式)
            
        示例:
            - "kterna 三人金东" -> ("kterna", "1", False, "3")
            - "kterna 三人玉南" -> ("kterna", "2", True, "3")
            - "kterna 金南" -> ("kterna", "1", True, "4")
            - "kterna" -> ("kterna", "1", True, "4")
        """
        parts = args.strip().split()
        if not parts:
            raise ValueError("请输入昵称")
            
        nickname = parts[0]
        mode: GameMode = "4"  # 默认四麻
        room_level: RoomLevel = "1"  # 默认金之间
        is_south = True  # 默认南场
        
        if len(parts) > 1:
            room_str = parts[1]
            if room_str.startswith("三人"):
                mode = "3"
                room_str = room_str[2:]  # 去掉"三人"前缀
                
            # 解析房间等级
            if room_str.startswith(("金", "玉", "王")):
                room_level = {"金": "1", "玉": "2", "王": "3"}[room_str[0]]
                room_str = room_str[1:]  # 去掉房间等级
                
            # 解析场风
            if room_str:
                is_south = room_str == "南"
                
        return nickname, room_level, is_south, mode
        
    async def execute_command(self, command: str) -> Tuple[bool, str]:
        """执行查询命令
        
        Args:
            command: 完整的命令字符串（如"雀魂查询 kterna 金南"）
            
        Returns:
            Tuple[bool, str]: (是否成功, 查询结果或错误信息)
            
        示例命令:
            - "雀魂查询 kterna 金南"
            - "雀魂牌谱 kterna 三人金东"
            - "雀魂详细 kterna 玉南"
        """
        try:
            # 去除命令前缀（如"雀魂牌谱"）
            command = re.sub(r'^(雀魂|三麻)(查询|牌谱|详细)\s*', '', command.strip())
            if not command:
                return False, "请输入要查询的昵称"
            
            # 解析参数
            nickname, room_level, is_south, mode = self.parse_command_args(command)
            
            # 根据原始命令类型执行不同的查询
            if "牌谱" in command:
                return await self.api.query_records(nickname, mode, DEFAULT_LIMIT, is_south)
            elif "详细" in command:
                return await self.api.query_extended_stats(nickname, mode, room_level, is_south)
            else:
                return await self.api.query_stats(nickname, mode, room_level, is_south)
                
        except ValueError as e:
            return False, str(e)
        except Exception as e:
            return False, f"解析命令出错: {str(e)}" 
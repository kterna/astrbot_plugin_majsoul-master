import os
import re
from typing import Dict, List, Tuple, Optional, Any
from .data_loader import MahjongDataLoader
from .image_generator import MahjongImageGenerator
from ..analysis.mahjong_utils import MahjongHelper

class MahjongWordle:
    """麻将Wordle游戏"""
    
    def __init__(self, plugin_dir: str, max_attempts: int = 6):
        """初始化游戏
        
        Args:
            plugin_dir: 插件目录路径
            max_attempts: 最大猜测次数，默认为6
        """
        self.plugin_dir = plugin_dir
        self.data_dir = os.path.join(plugin_dir, "data")
        self.resources_dir = os.path.join(self.data_dir, "resources", "Regular")
        self.output_dir = os.path.join(plugin_dir, "cache", "wordle")
        self.max_attempts = max_attempts
        
        # 创建输出目录
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 初始化数据加载器和图像生成器
        self.data_loader = MahjongDataLoader(self.data_dir)
        self.image_generator = MahjongImageGenerator(self.resources_dir, max_attempts=max_attempts)
        
        # 游戏状态
        self.current_games = {}  # 游戏ID -> 游戏状态
    
    def _get_game_key(self, user_id: str, group_id: Optional[str] = None) -> str:
        """获取游戏键值
        
        Args:
            user_id: 用户ID
            group_id: 群聊ID，如果是私聊则为None
            
        Returns:
            游戏键值
        """
        if group_id:
            return f"group_{group_id}"  # 群聊中所有用户共享同一个游戏
        else:
            return f"private_{user_id}"  # 私聊中用户独立游戏
    
    def start_game(self, user_id: str, group_id: Optional[str] = None) -> Dict[str, Any]:
        """开始新游戏
        
        Args:
            user_id: 用户ID
            group_id: 群聊ID，如果是私聊则为None
            
        Returns:
            游戏状态
        """
        # 获取游戏键值
        game_key = self._get_game_key(user_id, group_id)
        
        # 检查是否已有游戏
        if game_key in self.current_games:
            raise Exception("该群聊已有进行中的游戏")
        
        # 获取随机牌谱
        hand_data = self.data_loader.get_random_hand()
        if not hand_data:
            raise Exception("无法获取牌谱数据")
        
        # 解析手牌
        hand_str = hand_data.get("hand", "")
        parsed_hand = self._parse_hand_tiles(hand_str)
        
        # 创建游戏状态
        game_state = {
            "hand_data": hand_data,
            "target_tiles": parsed_hand,
            "guesses": [],
            "max_attempts": self.max_attempts,
            "completed": False,
            "win": False,
            "started_by": user_id,  # 记录游戏发起者
        }
        
        # 保存游戏状态
        self.current_games[game_key] = game_state
        
        return game_state
    
    def _parse_hand_tiles(self, hand_str: str) -> List[str]:
        """解析手牌字符串为牌列表
        
        Args:
            hand_str: 手牌字符串，如 "123456789m123p1s"
            
        Returns:
            牌列表，如 ["1m", "2m", "3m", ...]
        """
        result = []
        current_type = None
        current_numbers = ""
        
        for char in hand_str:
            if char in "mpsz":
                current_type = char
                for num in current_numbers:
                    result.append(num + current_type)
                current_numbers = ""
            else:
                current_numbers += char
                
        return result
    
    def _parse_guess(self, guess_str: str) -> List[str]:
        """解析用户猜测
        
        Args:
            guess_str: 用户猜测字符串
            
        Returns:
            解析后的牌列表
        """
        # 清理输入
        guess_str = re.sub(r'\s+', '', guess_str)
        
        return self._parse_hand_tiles(guess_str)
    
    def check_guess(self, user_id: str, guess_str: str, group_id: Optional[str] = None) -> Dict[str, Any]:
        """检查用户猜测
        
        Args:
            user_id: 用户ID
            guess_str: 用户猜测字符串
            group_id: 群聊ID，如果是私聊则为None
            
        Returns:
            检查结果
        """
        # 获取游戏状态
        game_key = self._get_game_key(user_id, group_id)
        game_state = self.current_games.get(game_key)
        if not game_state:
            raise Exception("没有进行中的游戏")
        
        if game_state["completed"]:
            # 游戏已结束，清理游戏状态
            del self.current_games[game_key]
            raise Exception("游戏已结束")
        
        # 解析猜测
        try:
            guess_tiles = self._parse_guess(guess_str)
        except Exception as e:
            raise Exception(f"解析猜测失败: {e}")
        
        # 获取目标牌
        target_tiles = game_state["target_tiles"]
        
        # 检查猜测长度
        if len(guess_tiles) != len(target_tiles):
            raise Exception(f"猜测的牌数不正确，应为{len(target_tiles)}张")
            
        # 检查是否是胡牌形状（向听数为0）
        helper = MahjongHelper()
        
        # 将猜测的牌转换为手牌字符串格式
        man = pin = sou = honors = ""
        current_type = None
        current_numbers = ""
        
        for tile in guess_tiles:
            num = tile[0]
            tile_type = tile[1]
            
            if current_type != tile_type:
                if current_type:
                    if current_type == 'm':
                        man += current_numbers
                    elif current_type == 'p':
                        pin += current_numbers
                    elif current_type == 's':
                        sou += current_numbers
                    elif current_type == 'z':
                        honors += current_numbers
                current_type = tile_type
                current_numbers = num
            else:
                current_numbers += num
                
        if current_type:
            if current_type == 'm':
                man += current_numbers
            elif current_type == 'p':
                pin += current_numbers
            elif current_type == 's':
                sou += current_numbers
            elif current_type == 'z':
                honors += current_numbers
            
        # 计算向听数
        shanten_result = helper.calculate_shanten(man=man, pin=pin, sou=sou, honors=honors)
        if shanten_result.shanten != 0:
            raise Exception("这不是一个有效的胡牌形状")
        
        # 检查每张牌
        result_tiles = []
        target_copy = target_tiles.copy()  # 用于标记已匹配的牌
        
        # 第一次遍历：标记完全匹配的牌
        for i, tile in enumerate(guess_tiles):
            if i < len(target_tiles) and tile == target_tiles[i]:
                result_tiles.append({"code": tile, "status": "correct"})
                target_copy[i] = None  # 标记已匹配
            else:
                result_tiles.append({"code": tile, "status": "unknown"})
        
        # 第二次遍历：检查部分匹配的牌
        for i, tile_info in enumerate(result_tiles):
            if tile_info["status"] == "unknown":
                tile = tile_info["code"]
                if tile in target_copy:
                    # 牌存在但位置不对
                    tile_info["status"] = "exists"
                    target_copy[target_copy.index(tile)] = None  # 标记已匹配
                else:
                    # 牌不存在
                    tile_info["status"] = "wrong"
        
        # 记录猜测
        guess_record = {
            "tiles": result_tiles,
            "correct": all(tile["status"] == "correct" for tile in result_tiles),
            "user_id": user_id  # 记录猜测的用户
        }
        game_state["guesses"].append(guess_record)
        
        # 检查是否完成
        if guess_record["correct"] or len(game_state["guesses"]) >= game_state["max_attempts"]:
            game_state["completed"] = True
            game_state["win"] = guess_record["correct"]
            # 游戏结束时，先返回结果，然后在调用方处理游戏状态
            return {
                "guess_record": guess_record,
                "game_state": game_state,
                "should_cleanup": True
            }
        
        return {
            "guess_record": guess_record,
            "game_state": game_state,
            "should_cleanup": False
        }
    
    def generate_image(self, user_id: str, group_id: Optional[str] = None) -> str:
        """生成游戏图像
        
        Args:
            user_id: 用户ID
            group_id: 群聊ID，如果是私聊则为None
            
        Returns:
            图像文件路径
        """
        # 获取游戏状态
        game_key = self._get_game_key(user_id, group_id)
        game_state = self.current_games.get(game_key)
        if not game_state:
            raise Exception("没有进行中的游戏")
        
        # 获取牌谱信息
        hand_data = game_state["hand_data"]
        round_wind = hand_data.get("round_wind_str", "")
        player_wind = hand_data.get("player_wind_str", "")
        han = hand_data.get("han", 0)
        fu = hand_data.get("fu", 0)
        
        # 生成图像
        image = self.image_generator.create_wordle_image(
            game_state["guesses"],
            round_wind,
            player_wind,
            han,
            fu
        )
        
        # 保存图像
        output_path = os.path.join(self.output_dir, f"wordle_{game_key}.png")
        self.image_generator.save_image(image, output_path)
        
        return output_path
    
    def get_game_info(self, user_id: str, group_id: Optional[str] = None) -> Dict[str, Any]:
        """获取游戏信息
        
        Args:
            user_id: 用户ID
            group_id: 群聊ID，如果是私聊则为None
            
        Returns:
            游戏信息
        """
        game_key = self._get_game_key(user_id, group_id)
        game_state = self.current_games.get(game_key)
        if not game_state:
            return None
        
        hand_data = game_state["hand_data"]
        
        return {
            "attempts": len(game_state["guesses"]),
            "max_attempts": game_state["max_attempts"],
            "completed": game_state["completed"],
            "win": game_state["win"],
            "round_wind": hand_data.get("round_wind_str", ""),
            "player_wind": hand_data.get("player_wind_str", ""),
            "han": hand_data.get("han", 0),
            "fu": hand_data.get("fu", 0),
            "yaku": [y.get("chinese_name", y.get("name", "")) for y in hand_data.get("yaku", [])],
            "started_by": game_state["started_by"],
        } 
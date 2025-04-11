import os
from typing import Dict, List, Tuple, Optional, Any
from PIL import Image
from .mahjong_wordle import MahjongWordle
from .data_loader import MahjongDataLoader
from .image_generator import MahjongImageGenerator

class MultiMahjongWordle:
    """麻将多牌谱Wordle游戏"""
    
    def __init__(self, plugin_dir: str, num_games: int = 4, max_attempts: int = 10):
        """初始化多牌谱游戏
        
        Args:
            plugin_dir: 插件目录路径
            num_games: 牌谱数量，默认4个
            max_attempts: 最大猜测次数，默认10次
        """
        self.plugin_dir = plugin_dir
        self.num_games = num_games
        self.max_attempts = max_attempts
        self.data_dir = os.path.join(plugin_dir, "data")
        self.resources_dir = os.path.join(self.data_dir, "resources", "Regular")
        self.output_dir = os.path.join(plugin_dir, "cache", "wordle")
        
        # 创建输出目录
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 初始化单牌谱游戏实例，传递正确的max_attempts参数
        self.games = [MahjongWordle(plugin_dir, max_attempts=max_attempts) for _ in range(num_games)]
        
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
    
    def start_games(self, user_id: str, group_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """开始新的多牌谱游戏
        
        Args:
            user_id: 用户ID
            group_id: 群聊ID，如果是私聊则为None
            
        Returns:
            游戏状态列表
        """
        # 获取游戏键值
        game_key = self._get_game_key(user_id, group_id)
        
        # 检查是否已有游戏
        if game_key in self.current_games:
            raise Exception("该群聊已有进行中的游戏")
        
        # 使用第一个游戏实例的数据加载器获取不重复的牌谱
        data_loader = self.games[0].data_loader
        
        # 获取足够的不同牌谱
        used_hands = set()  # 用于记录已使用的牌谱手牌字符串
        hands_data = []
        
        # 最多尝试20次，防止无限循环
        max_tries = 20
        tries = 0
        
        while len(hands_data) < self.num_games and tries < max_tries:
            tries += 1
            hand_data = data_loader.get_random_hand()
            if not hand_data:
                raise Exception("无法获取牌谱数据")
            
            # 使用手牌字符串作为唯一标识
            hand_str = hand_data.get("hand", "")
            if hand_str not in used_hands:
                used_hands.add(hand_str)
                hands_data.append(hand_data)
        
        # 如果获取的牌谱数量不足，抛出异常
        if len(hands_data) < self.num_games:
            raise Exception(f"无法获取足够的不同牌谱，只获取了{len(hands_data)}个")
        
        # 为每个游戏实例启动独立游戏
        game_states = []
        for i, game in enumerate(self.games):
            # 启动单个游戏，但不调用原始的start_game方法
            # 而是手动设置游戏状态，使用已获取的不同牌谱
            try:
                # 获取游戏键值
                inner_game_key = game._get_game_key(user_id, group_id)
                
                # 获取牌谱数据
                hand_data = hands_data[i]
                
                # 解析手牌
                hand_str = hand_data.get("hand", "")
                parsed_hand = game._parse_hand_tiles(hand_str)
                
                # 创建游戏状态
                game_state = {
                    "hand_data": hand_data,
                    "target_tiles": parsed_hand,
                    "guesses": [],
                    "max_attempts": self.max_attempts,
                    "completed": False,
                    "win": False,
                    "started_by": user_id,
                    "last_guess_by": None
                }
                
                # 保存游戏状态
                game.current_games[inner_game_key] = game_state
                game_states.append(game_state)
                
            except Exception as e:
                # 如果某个游戏启动失败，清理已启动的游戏
                for g in self.games:
                    key = g._get_game_key(user_id, group_id)
                    if key in g.current_games:
                        del g.current_games[key]
                raise Exception(f"启动游戏失败: {e}")
        
        # 创建多牌谱游戏状态
        multi_game_state = {
            "game_states": game_states,
            "guesses": [],
            "max_attempts": self.max_attempts,
            "completed": False,
            "win_count": 0,
            "started_by": user_id,
            "last_guess_by": None
        }
        
        # 保存多牌谱游戏状态
        self.current_games[game_key] = multi_game_state
        
        return game_states
    
    def check_guess(self, user_id: str, guess_str: str, group_id: Optional[str] = None) -> Dict[str, Any]:
        """检查用户猜测（对所有牌谱）
        
        Args:
            user_id: 用户ID
            guess_str: 用户猜测字符串
            group_id: 群聊ID，如果是私聊则为None
            
        Returns:
            检查结果
        """
        # 获取游戏状态
        game_key = self._get_game_key(user_id, group_id)
        multi_game_state = self.current_games.get(game_key)
        if not multi_game_state:
            raise Exception("没有进行中的游戏")
        
        if multi_game_state["completed"]:
            # 游戏已结束，清理游戏状态
            del self.current_games[game_key]
            for game in self.games:
                key = game._get_game_key(user_id, group_id)
                if key in game.current_games:
                    del game.current_games[key]
            raise Exception("游戏已结束")
        
        # 检查猜测次数是否已达上限
        if len(multi_game_state["guesses"]) >= multi_game_state["max_attempts"]:
            multi_game_state["completed"] = True
            raise Exception(f"已达到最大猜测次数({self.max_attempts}次)")
        
        # 对每个游戏实例进行猜测
        results = []
        correct_count = 0
        
        for i, game in enumerate(self.games):
            game_key = game._get_game_key(user_id, group_id)
            game_state = game.current_games.get(game_key)
            
            # 如果该牌谱已经猜对，则跳过
            if game_state and any(guess.get("correct", False) for guess in game_state["guesses"]):
                correct_count += 1
                results.append({"already_correct": True, "index": i})
                continue
                
            try:
                # 调用单个游戏的check_guess方法
                result = game.check_guess(user_id, guess_str, group_id)
                results.append(result)
                
                # 检查是否猜对了这个牌谱
                if result["guess_record"]["correct"]:
                    correct_count += 1
            except Exception as e:
                results.append({"error": str(e), "index": i})
        
        # 记录猜测
        multi_game_state["guesses"].append({
            "guess_str": guess_str,
            "results": results,
            "user_id": user_id
        })
        multi_game_state["last_guess_by"] = user_id
        multi_game_state["win_count"] = correct_count
        
        # 检查是否完成
        if correct_count == self.num_games or len(multi_game_state["guesses"]) >= multi_game_state["max_attempts"]:
            multi_game_state["completed"] = True
        
        return {
            "results": results,
            "multi_game_state": multi_game_state,
            "win_count": correct_count,
            "total_games": self.num_games,
            "current_attempt": len(multi_game_state["guesses"]),
            "max_attempts": self.max_attempts,
            "completed": multi_game_state["completed"]
        }
    
    def generate_composite_image(self, user_id: str, group_id: Optional[str] = None) -> str:
        """生成2×2复合图像
        
        Args:
            user_id: 用户ID
            group_id: 群聊ID，如果是私聊则为None
            
        Returns:
            合成图像文件路径
        """
        # 获取游戏状态
        game_key = self._get_game_key(user_id, group_id)
        multi_game_state = self.current_games.get(game_key)
        if not multi_game_state:
            raise Exception("没有进行中的游戏")
        
        # 生成每个游戏的图像
        image_paths = []
        
        # 创建临时目录用于存储各个牌谱的图片
        temp_dir = os.path.join(self.output_dir, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        for i, game in enumerate(self.games):
            try:
                # 获取游戏状态
                game_key_i = game._get_game_key(user_id, group_id)
                game_state = game.current_games.get(game_key_i)
                
                if not game_state:
                    raise Exception(f"游戏实例 {i} 不存在游戏状态")
                
                # 获取牌谱信息
                hand_data = game_state["hand_data"]
                round_wind = hand_data.get("round_wind_str", "")
                player_wind = hand_data.get("player_wind_str", "")
                han = hand_data.get("han", 0)
                fu = hand_data.get("fu", 0)
                
                # 生成图像
                image = game.image_generator.create_wordle_image(
                    game_state["guesses"],
                    round_wind,
                    player_wind,
                    han,
                    fu
                )
                
                # 保存图像到临时目录，使用唯一的文件名
                temp_path = os.path.join(temp_dir, f"wordle_{game_key}_{i}.png")
                game.image_generator.save_image(image, temp_path)
                
                image_paths.append(temp_path)
                
            except Exception as e:
                raise Exception(f"生成图像失败: {e}")
        
        # 读取所有图片
        images = [Image.open(path) for path in image_paths]
        
        # 获取单张图片尺寸
        width, height = images[0].size
        
        # 创建新的大图
        composite = Image.new('RGB', (width*2, height*2))
        
        # 按2×2排列粘贴图片
        positions = [(0, 0), (width, 0), (0, height), (width, height)]
        for i, img in enumerate(images):
            if i < len(positions):
                composite.paste(img, positions[i])
        
        # 保存合成图片
        output_path = os.path.join(self.output_dir, f"multi_wordle_{game_key}.png")
        composite.save(output_path)
        
        return output_path
    
    def get_multi_game_info(self, user_id: str, group_id: Optional[str] = None) -> Dict[str, Any]:
        """获取多牌谱游戏信息
        
        Args:
            user_id: 用户ID
            group_id: 群聊ID，如果是私聊则为None
            
        Returns:
            多牌谱游戏信息
        """
        # 获取游戏状态
        game_key = self._get_game_key(user_id, group_id)
        multi_game_state = self.current_games.get(game_key)
        if not multi_game_state:
            raise Exception("没有进行中的游戏")
        
        # 获取每个单独游戏的信息
        game_infos = []
        for i, game in enumerate(self.games):
            try:
                game_info = game.get_game_info(user_id, group_id)
                game_infos.append(game_info)
            except Exception as e:
                game_infos.append({"error": str(e), "index": i})
        
        return {
            "game_infos": game_infos,
            "win_count": multi_game_state["win_count"],
            "total_games": self.num_games,
            "current_attempt": len(multi_game_state["guesses"]),
            "max_attempts": self.max_attempts,
            "completed": multi_game_state["completed"]
        } 
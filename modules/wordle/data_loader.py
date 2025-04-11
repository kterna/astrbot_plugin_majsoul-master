import json
import os
import random
from typing import Dict, List, Any, Optional

class MahjongDataLoader:
    """麻将牌谱数据加载器"""
    
    def __init__(self, data_dir: str):
        """初始化数据加载器
        
        Args:
            data_dir: 数据目录路径
        """
        self.data_dir = data_dir
        self.hands_file = os.path.join(data_dir, "generated_hands", "valid_hands.json")
        self.hands_data = self._load_hands()
        
    def _load_hands(self) -> List[Dict[str, Any]]:
        """加载牌谱数据
        
        Returns:
            牌谱数据列表
        """
        try:
            if os.path.exists(self.hands_file):
                with open(self.hands_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if not data:
                        print(f"牌谱数据文件为空: {self.hands_file}")
                    return data
            else:
                print(f"找不到牌谱数据文件: {self.hands_file}")
                return []
        except Exception as e:
            print(f"加载牌谱数据失败: {e}")
            return []
    
    def get_random_hand(self) -> Optional[Dict[str, Any]]:
        """随机获取一个牌谱
        
        Returns:
            随机牌谱数据
        """
        if not self.hands_data:
            return None
        return random.choice(self.hands_data)
    
    def get_hand_info(self, hand_data: Dict[str, Any]) -> Dict[str, Any]:
        """获取牌谱信息
        
        Args:
            hand_data: 牌谱数据
            
        Returns:
            牌谱信息
        """
        return {
            "hand": hand_data.get("hand", ""),
            "win_tile": hand_data.get("win_tile", ""),
            "round_wind_str": hand_data.get("round_wind_str", ""),
            "player_wind_str": hand_data.get("player_wind_str", ""),
            "han": hand_data.get("han", 0),
            "fu": hand_data.get("fu", 0),
            "yaku": hand_data.get("yaku", [])
        }
    
    def parse_hand_string(self, hand_str: str) -> Dict[str, List[str]]:
        """解析手牌字符串
        
        Args:
            hand_str: 手牌字符串，如 "123456789m123p1s"
            
        Returns:
            按照类型分类的手牌列表
        """
        result = {"m": [], "p": [], "s": [], "z": []}
        current_type = None
        current_numbers = ""
        
        for char in hand_str:
            if char in "mpsz":
                current_type = char
                for num in current_numbers:
                    result[current_type].append(num + current_type)
                current_numbers = ""
            else:
                current_numbers += char
                
        return result 
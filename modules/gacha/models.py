from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
import json
import os
import logging
import random
import re

logger = logging.getLogger(__name__)

@dataclass
class Card:
    name: str
    type: str    # "character", "decoration", "gift", "jades"
    pool: str    # 所属卡池名称
    pool_type: str = "standard"  # 卡池类型：standard/contract/limited/collab

    def _find_image_by_pattern(self, char_dir: str, pattern: str) -> Optional[str]:
        """使用正则表达式查找匹配的图片
        
        Args:
            char_dir: 角色目录路径
            pattern: 正则表达式模式
            
        Returns:
            Optional[str]: 匹配的图片路径，如果没找到则返回None
        """
        try:
            regex = re.compile(pattern)
            for file in os.listdir(char_dir):
                if not file.endswith(('.jpg', '.png')):
                    continue
                if regex.search(file):
                    return os.path.join(char_dir, file)
        except Exception as e:
            logger.error(f"正则匹配出错: {e}")
        return None

    def get_border_color(self) -> Tuple[int, int, int]:
        """获取边框颜色"""
        if self.type == "character":
            return (255, 105, 180)  # 角色卡使用粉色边框
        elif self.type == "decoration":
            return (255, 215, 0)    # 装饰品使用金色边框
        elif self.type == "gift":
            return (255, 165, 0)    # 礼物使用橙色边框
        else:
            return (255, 255, 255)  # 其他物品白色边框

    def get_image_path(self, resources_dir: str) -> Optional[str]:
        """获取卡片图片路径"""
        try:
            if self.type == "character":
                sub_dir = "person"
                char_dir = os.path.join(resources_dir, sub_dir, self.name)
                if not os.path.exists(char_dir) or not os.path.isdir(char_dir):
                    default_dir = os.path.join(resources_dir, sub_dir, "默认角色")
                    if os.path.exists(default_dir) and os.path.isdir(default_dir):
                        char_dir = default_dir
                    else:
                        return None

                keywords = {
                    "standard": "初始形象",
                    "contract": "缔结契约后获得",
                    "limited": "活动限定",
                    "collab": "联动"
                }
                
                keyword = keywords.get(self.pool_type, "初始形象")
                
                matching_images = []
                for file in os.listdir(char_dir):
                    if not file.endswith('.png') and not file.endswith('.jpg'):
                        continue
                    if keyword in file:
                        matching_images.append(file)
                
                if matching_images:
                    if self.pool_type == "limited":
                        selected_image = random.choice(matching_images)
                    else:
                        selected_image = matching_images[0]
                    
                    return os.path.join(char_dir, selected_image)
                
                if keyword != "初始形象":
                    for file in os.listdir(char_dir):
                        if not file.endswith('.png') and not file.endswith('.jpg'):
                            continue
                        if "初始形象" in file:
                            image_path = os.path.join(char_dir, file)
                            return image_path
                
                return None
                
            else:
                sub_dir = self.type
                base_path = os.path.join(resources_dir, sub_dir, self.name)
                
                for ext in ['.jpg', '.png']:
                    path = base_path + ext
                    if os.path.exists(path):
                        return path
                
                default_path = os.path.join(resources_dir, sub_dir, "默认" + self.type)
                for ext in ['.jpg', '.png']:
                    path = default_path + ext
                    if os.path.exists(path):
                        return path
                
                return None
                
        except Exception:
            return None

@dataclass
class GachaPool:
    name: str
    description: str
    cards: List[Card]
    up_cards: List[Card]
    pool_type: str = "standard"
    type_rates: Dict[str, float] = None
    up_rate_boost: float = 0.5
    display_name: str = None
    
    def __post_init__(self):
        if self.display_name is None:
            self.display_name = self.name
        
        if self.type_rates is None:
            self.type_rates = {
                "character": 0.01,
                "decoration": 0.09,
                "gift": 0.60,
                "jades": 0.30
            }
        else:
            self.type_rates = {str(k): v for k, v in self.type_rates.items()}
            
        for card in self.cards:
            card.pool_type = self.pool_type
        for card in self.up_cards:
            card.pool_type = self.pool_type

@dataclass
class GachaResult:
    cards: List[Card]
    pool_name: str
    pool_description: str 
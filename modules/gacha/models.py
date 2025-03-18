from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import json
import os
import logging
import random

logger = logging.getLogger(__name__)

@dataclass
class Card:
    name: str
    rarity: str  # "UR", "SSR", "SR", "R"
    type: str    # "character", "decoration", "gift", "jades"
    pool: str    # 所属卡池

    def get_border_color(self) -> Tuple[int, int, int]:
        """获取边框颜色"""
        if self.type == "character":
            return {
                "UR": (255, 0, 0),      # 红色
                "SSR": (148, 0, 211),   # 紫色
                "SR": (255, 215, 0),    # 金色
                "R": (192, 192, 192),   # 银色
            }.get(self.rarity, (255, 255, 255))
        elif self.type == "decoration":
            return (255, 215, 0)  # 装饰品统一金色边框
        else:
            return (255, 255, 255)  # 其他物品白色边框

    def get_image_path(self, resources_dir: str) -> Optional[str]:
        """获取卡片图片路径
        
        Args:
            resources_dir: 资源目录
            
        Returns:
            Optional[str]: 图片路径，如果不存在则返回None
        """
        try:
            # 根据卡片类型确定子目录
            if self.type == "character":
                sub_dir = "person"
            else:
                sub_dir = self.type
            
            # 构建图片路径
            base_path = os.path.join(resources_dir, sub_dir, self.name)
            logger.debug(f"尝试查找图片: {base_path}.[jpg/png]")
            
            # 检查jpg和png格式
            for ext in ['.jpg', '.png']:
                path = base_path + ext
                if os.path.exists(path):
                    logger.debug(f"找到图片: {path}")
                    return path
            
            # 如果找不到图片，记录警告
            logger.warning(f"找不到图片: {base_path}.[jpg/png]")
            
            # 尝试查找同类型的默认图片
            default_path = os.path.join(resources_dir, sub_dir, "默认" + self.type)
            for ext in ['.jpg', '.png']:
                path = default_path + ext
                if os.path.exists(path):
                    logger.info(f"使用默认图片: {path}")
                    return path
                    
            return None
        except Exception as e:
            logger.error(f"获取图片路径时出错: {e}")
            return None

@dataclass
class GachaPool:
    name: str
    description: str
    cards: List[Card]
    up_cards: List[Card]
    
    # 总体类型概率
    type_rates: Dict[str, float] = None
    
    # 角色稀有度概率
    character_rates: Dict[str, float] = None
    
    # UP角色概率提升
    up_rate_boost: float = 0.5  # UP卡在同稀有度中占50%概率
    
    # 显示名称
    display_name: str = None
    
    def __post_init__(self):
        if self.display_name is None:
            self.display_name = self.name
        
        if self.type_rates is None:
            self.type_rates = {
                "character": 0.01,  # 角色 1%
                "decoration": 0.09, # 装饰品 9%
                "gift": 0.60,      # 礼物 60%
                "jades": 0.30      # 玉石 30%
            }
        else:
            # 确保type_rates中的键都是字符串类型
            self.type_rates = {str(k): v for k, v in self.type_rates.items()}
        
        if self.character_rates is None:
            self.character_rates = {
                "UR": 0.01,  # 1%
                "SSR": 0.04, # 4%
                "SR": 0.15,  # 15%
                "R": 0.80    # 80%
            }

@dataclass
class GachaResult:
    cards: List[Card]
    pool_name: str
    pool_description: str 
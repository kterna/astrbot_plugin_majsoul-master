from typing import Dict, List, Optional
import os
import json
import logging
from .models import Card, GachaPool
import random
import time

logger = logging.getLogger(__name__)

class ResourceManager:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        # 统一使用data/resources作为资源目录
        self.resources_dir = os.path.join(data_dir, "resources")
        self.pools_config_path = os.path.join(data_dir, "modules", "gacha", "pools.json")
        self.group_pools_path = os.path.join(data_dir, "modules", "gacha", "group_pools.json")
        self._temp_dir = os.path.join(os.path.dirname(self.resources_dir), "temp")
        
        # 初始化所有必要目录
        self._init_directories()
        
        # 清理旧的临时文件
        self.clean_temp_files()
        
        # 加载配置
        self.pools_config = self._load_pools_config()
        self.group_pools = self._load_group_pools()
        self.available_resources = self._load_available_resources()

    def _init_directories(self) -> None:
        """初始化所有必要的目录"""
        # 基础目录
        self._ensure_directory(self.resources_dir, "资源")
        self._ensure_directory(self._temp_dir, "临时")
        
        # 资源子目录
        resource_dirs = {
            "person": "角色",
            "decoration": "装饰",
            "gift": "礼物",
            "jades": "玉石",
            "background": "背景"
        }
        
        for dir_name, description in resource_dirs.items():
            self._ensure_directory(os.path.join(self.resources_dir, dir_name), description)

    def _ensure_directory(self, dir_path: str, dir_description: str = None) -> None:
        """确保目录存在
        Args:
            dir_path: 目录路径
            dir_description: 目录描述（用于日志）
        """
        try:
            os.makedirs(dir_path, exist_ok=True)
            if dir_description:
                logger.debug(f"确保{dir_description}目录存在: {dir_path}")
        except Exception as e:
            logger.error(f"创建目录失败: {dir_path}, 错误: {e}")

    def _get_pool_internal(self, pool_id: str = "standard", group_id: str = None) -> GachaPool:
        """内部获取卡池方法
        Args:
            pool_id: 卡池ID，如果提供group_id则忽略此参数
            group_id: 群组ID，如果提供则获取该群组的卡池
        """
        if group_id is not None:
            pool_id = self.group_pools.get(str(group_id), "standard")
        
        if pool_id not in self.pools_config:
            logger.warning(f"卡池 {pool_id} 不存在，使用默认卡池")
            pool_id = "standard"
        
        return self.create_pool(pool_id, self.pools_config[pool_id])

    # 保持原有接口不变
    def get_pool(self, pool_id: str) -> GachaPool:
        """获取指定ID的卡池（保持原有接口）"""
        return self._get_pool_internal(pool_id)

    def get_group_pool(self, group_id: str) -> GachaPool:
        """获取群组当前使用的卡池（保持原有接口）"""
        return self._get_pool_internal(group_id=group_id)

    def get_available_pools(self) -> Dict[str, Dict]:
        """获取所有可用卡池信息（保持原有接口）"""
        return self.pools_config

    def get_temp_dir(self) -> str:
        """获取临时目录路径（保持原有接口）"""
        return self._temp_dir

    def _ensure_resource_directories(self, dir_names) -> None:
        """确保资源目录存在（保持向后兼容）"""
        for dir_name in dir_names:
            self._ensure_directory(os.path.join(self.resources_dir, dir_name))

    def _load_pools_config(self) -> dict:
        """加载卡池配置文件"""
        try:
            config_path = self.pools_config_path
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            else:
                # 如果配置文件不存在，尝试使用相对路径
                fallback_path = os.path.join(os.path.dirname(__file__), "pools.json")
                if os.path.exists(fallback_path):
                    with open(fallback_path, "r", encoding="utf-8") as f:
                        return json.load(f)
        except Exception as e:
            logger.error(f"加载卡池配置失败: {e}")
        
        # 返回默认配置
        return {
            "standard": {
                "name": "标准池",
                "description": "常驻角色池",
                "rates": {
                    "character": 0.01,
                    "decoration": 0.09,
                    "gift": 0.60,
                    "jades": 0.30
                }
            }
        }

    def _load_available_resources(self) -> dict:
        """加载可用资源（装饰品、礼物、玉石）"""
        resources = {
            "decoration": [],
            "gift": [],
            "jades": []
        }
        
        # 定义资源类型和对应的目录名
        resource_dirs = {
            "decoration": "decoration",
            "gift": "gift",
            "jades": "jades"
        }
        
        # 统一处理各类型资源
        for resource_type, dir_name in resource_dirs.items():
            dir_path = os.path.join(self.resources_dir, dir_name)
            if os.path.exists(dir_path):
                # 使用文件名（不含扩展名）作为资源名
                for file in os.listdir(dir_path):
                    if file.endswith(('.jpg', '.png')):
                        name = os.path.splitext(file)[0]
                        resources[resource_type].append(name)
        
        # 打印资源统计
        logger.info(f"资源统计: 装饰={len(resources['decoration'])}, 礼物={len(resources['gift'])}, 玉石={len(resources['jades'])}")
        
        # 如果没有资源，添加默认资源
        for resource_type in resources.keys():
            if not resources[resource_type]:
                resources[resource_type] = [f"默认{resource_type}"]
                logger.warning(f"未找到{resource_type}资源，使用默认{resource_type}")
        
        return resources

    def _load_group_pools(self) -> dict:
        """加载群组卡池设置"""
        try:
            if os.path.exists(self.group_pools_path):
                with open(self.group_pools_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"加载群组卡池设置失败: {e}")
        return {}

    def _save_group_pools(self) -> bool:
        """保存群组卡池设置"""
        try:
            os.makedirs(os.path.dirname(self.group_pools_path), exist_ok=True)
            with open(self.group_pools_path, "w", encoding="utf-8") as f:
                json.dump(self.group_pools, f, ensure_ascii=False, indent=4)
            logger.info(f"群组卡池设置已保存到: {self.group_pools_path}")
            return True
        except Exception as e:
            logger.error(f"保存群组卡池设置失败: {e}")
            return False

    def set_group_pool(self, group_id: str, pool_id: str) -> bool:
        """设置群组使用的卡池"""
        if pool_id not in self.pools_config:
            logger.warning(f"尝试设置不存在的卡池: {pool_id}")
            return False
        
        self.group_pools[str(group_id)] = pool_id
        return self._save_group_pools()

    def create_pool(self, pool_id: str, pool_data: dict) -> GachaPool:
        """从配置创建卡池对象"""
        name = pool_data.get("name", pool_id)
        description = pool_data.get("description", "")
        
        # 获取卡池类型
        pool_type = pool_data.get("type", "standard")
        if pool_type not in ["standard", "contract", "limited", "collab"]:
            logger.warning(f"未知的卡池类型 {pool_type}，使用standard")
            pool_type = "standard"
        
        # 获取概率配置
        type_rates = {str(k): v for k, v in pool_data.get("rates", {}).items()}
        
        # 创建卡牌列表
        cards = []
        for card_data in pool_data.get("cards", []):
            cards.append(Card(
                name=card_data["name"],
                type=card_data["type"],
                pool=name,
                pool_type=pool_type
            ))
        
        # 创建UP卡牌列表
        up_cards = []
        for card_data in pool_data.get("up_cards", []):
            up_cards.append(Card(
                name=card_data["name"],
                type=card_data.get("type", "character"),
                pool=name,
                pool_type=pool_type
            ))
        
        # 创建卡池对象
        pool = GachaPool(
            name=name,
            description=description,
            cards=cards,
            up_cards=up_cards,
            type_rates=type_rates,
            pool_type=pool_type
        )
        
        # 设置UP概率提升
        if "up_rates" in pool_data:
            pool.up_rate_boost = sum(pool_data["up_rates"].values())
        
        return pool

    def get_random_background(self) -> Optional[str]:
        """获取随机背景图片路径"""
        bg_paths = self.get_all_backgrounds()
        
        if not bg_paths:
            logger.warning("背景图片目录为空")
            default_bg = os.path.join(self.resources_dir, "default_background.jpg")
            return default_bg if os.path.exists(default_bg) else None
        
        selected_bg = random.choice(bg_paths)
        logger.debug(f"随机选择背景图片: {selected_bg}")
        return selected_bg

    def get_all_backgrounds(self) -> List[str]:
        """获取所有背景图片的路径列表
        
        Returns:
            List[str]: 背景图片路径列表
        """
        bg_dir = os.path.join(self.resources_dir, "background")
        if not os.path.exists(bg_dir):
            logger.warning(f"背景图片目录不存在: {bg_dir}")
            return []
            
        try:
            bg_files = []
            for file in os.listdir(bg_dir):
                if file.lower().endswith(('.jpg', '.png', '.jpeg', '.gif')):
                    full_path = os.path.join(bg_dir, file)
                    if os.path.isfile(full_path):
                        bg_files.append(full_path)
            
            if not bg_files:
                logger.warning("未找到任何背景图片")
            else:
                logger.debug(f"找到{len(bg_files)}张背景图片")
            
            return bg_files
            
        except Exception as e:
            logger.error(f"获取背景图片列表时出错: {e}")
            return []

    def clean_temp_files(self, max_age: int = 3600) -> None:
        """清理临时文件
        
        Args:
            max_age: 文件最大保留时间（秒），默认1小时
        """
        try:
            current_time = time.time()
            temp_dir = self.get_temp_dir()
            
            if not os.path.exists(temp_dir):
                return
                
            for file in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, file)
                try:
                    if os.path.isfile(file_path):
                        # 获取文件修改时间
                        file_time = os.path.getmtime(file_path)
                        if current_time - file_time > max_age:
                            os.remove(file_path)
                            logger.debug(f"已删除过期临时文件: {file}")
                except Exception as e:
                    logger.warning(f"删除临时文件失败: {file}, 错误: {e}")
                    
        except Exception as e:
            logger.error(f"清理临时文件时出错: {e}") 
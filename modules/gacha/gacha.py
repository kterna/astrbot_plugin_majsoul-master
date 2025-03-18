from __future__ import annotations
from typing import Dict, List, Tuple, Optional, Union, Any
import random
import json
import os
import re
import logging
import asyncio
from pathlib import Path
from astrbot.api.message_components import Plain, Image
from astrbot.api.event import AstrMessageEvent, MessageEventResult

from .models import Card, GachaPool, GachaResult
from .resources import ResourceManager
from .presenter import GachaPresenter

logger = logging.getLogger(__name__)

class GachaSystem:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "cache")
        self.pools_file = os.path.join(os.path.dirname(__file__), "pools.json")
        self.resource_manager = ResourceManager(data_dir)
        self.presenter = GachaPresenter(self.resource_manager)
        self.pools = self._load_pools()
        self.current_pool = "standard"  # 默认卡池
        
        # 确保缓存目录存在
        os.makedirs(self.cache_dir, exist_ok=True)

    def _load_pools(self) -> Dict[str, GachaPool]:
        """加载所有卡池配置"""
        try:
            with open(self.pools_file, 'r', encoding='utf-8') as f:
                pools_data = json.load(f)
            
            pools = {}
            for pool_name, pool_data in pools_data.items():
                # 处理卡牌列表
                cards = []
                cards_data = pool_data.get("cards", {})
                for rarity, card_list in cards_data.items():
                    for card_data in card_list:
                        cards.append(Card(
                            name=card_data.get("name", "未知角色"),
                            rarity=rarity,
                            type=card_data.get("type", "character"),
                            pool=pool_name
                        ))
                
                # 处理UP卡牌
                up_cards = []
                up_cards_data = pool_data.get("up_cards", [])
                for card_data in up_cards_data:
                    up_cards.append(Card(
                        name=card_data.get("name", "未知角色"),
                        rarity=str(card_data.get("rarity", "UR")),
                        type=card_data.get("type", "character"),
                        pool=pool_name
                    ))
                
                # 创建卡池对象
                pools[pool_name] = GachaPool(
                    name=pool_name,
                    description=pool_data.get("description", ""),
                    cards=cards,
                    up_cards=up_cards,
                    type_rates=pool_data.get("rates"),
                    character_rates=pool_data.get("character_rates"),
                    display_name=pool_data.get("display_name", pool_name)
                )
            return pools
        except Exception as e:
            logger.error(f"加载卡池配置失败: {e}")
            # 创建默认卡池
            default_cards = [Card(name="默认角色", rarity="R", type="character", pool="standard")]
            return {"standard": GachaPool(
                name="standard", 
                description="标准卡池",
                cards=default_cards,
                up_cards=[],
                display_name="标准卡池"
            )}
    
    async def handle_command(self, event: AstrMessageEvent) -> MessageEventResult:
        """处理抽卡相关命令"""
        message = event.message_str.strip()
        group_id = str(event.message_obj.group_id)
        
        if message == "雀魂十连":
            return await self._handle_gacha_ten(event, group_id)
        elif message == "查看雀魂卡池":
            return await self._handle_view_pool(event, group_id)
        elif message.startswith("切换雀魂卡池"):
            return await self._handle_switch_pool(event, group_id)
        
        # 默认返回
        result = event.make_result()
        result.chain = [Plain("未知的抽卡命令")]
        return result
    
    async def perform_gacha(self, count: int = 10) -> Union[str, Dict[str, Any]]:
        """执行抽卡并返回结果，可以由新的命令处理函数调用"""
        try:
            if count <= 0 or count > 100:
                return "抽卡次数必须在1-100之间"
            
            # 获取当前卡池
            pool = self.pools.get(self.current_pool)
            if not pool:
                return "当前卡池不存在，请先切换到有效卡池"
            
            # 生成结果
            if count == 1:
                card = self.gacha_once(pool)
                return f"抽卡结果: {card.name} ({card.rarity}星)"
            else:
                result = self.gacha_ten(pool) if count == 10 else GachaResult([self.gacha_once(pool) for _ in range(count)])
                
                # 生成图片
                image_path = self.presenter.create_gacha_result_image(result)
                return {
                    "text": f"【{pool.display_name}】{count}连抽卡结果:",
                    "image_path": image_path
                }
        except Exception as e:
            logger.error(f"执行抽卡出错: {e}")
            return f"抽卡出错: {str(e)}"
    
    def switch_pool(self, pool_name: str) -> Tuple[bool, str]:
        """切换卡池，返回(是否成功, 消息)"""
        if pool_name not in self.pools:
            return False, f"卡池 {pool_name} 不存在，可用卡池: {', '.join(self.pools.keys())}"
        
        self.current_pool = pool_name
        pool = self.pools[pool_name]
        return True, f"已切换到【{pool.display_name}】卡池: {pool.description}"
    
    def get_available_pools(self) -> List[str]:
        """获取所有可用的卡池名称"""
        return [f"{name} - {pool.display_name}" for name, pool in self.pools.items()]
    
    async def update_gacha_data(self) -> None:
        """更新抽卡数据，作为异步任务调用"""
        try:
            # 这里可以添加从远程更新卡池数据的逻辑
            # 例如从网络API获取最新卡池信息
            # 目前仅重新加载本地数据
            self.pools = self._load_pools()
            logger.info("已更新抽卡数据")
        except Exception as e:
            logger.error(f"更新抽卡数据出错: {e}")
    
    def gacha_once(self, pool: GachaPool) -> Card:
        """进行一次抽卡"""
        try:
            # 首先确定抽到的是什么类型
            selected_type = self._select_random_type(pool.type_rates)
            
            # 如果是角色，需要进一步确定稀有度
            if selected_type == "character":
                return self._create_character_card(pool)
            else:
                # 如果是其他类型，直接从对应类型中随机选择
                return self._create_item_card(selected_type, pool.name)
        
        except Exception as e:
            logger.error(f"抽卡过程中发生错误: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # 返回一个默认卡牌
            return Card(
                name="系统错误",
                rarity="R",
                type="gift",
                pool=pool.name
            )

    def gacha_ten(self, pool: GachaPool) -> GachaResult:
        """十连抽 - 无保底版本"""
        results = []
        
        # 进行十次抽取，不设置保底
        for i in range(10):
            card = self.gacha_once(pool)
            results.append(card)
        
        return GachaResult(
            cards=results,
            pool_name=pool.name,
            pool_description=pool.description
        )

    def _select_random_type(self, type_rates: Dict[str, float]) -> str:
        """根据概率随机选择一个类型"""
        type_rand = random.random()
        cumulative_prob = 0
        
        for type_name, prob in type_rates.items():
            cumulative_prob += prob
            if type_rand < cumulative_prob:
                return str(type_name)
        
        # 如果没有选中类型（概率总和小于1），默认选择礼物
        logger.warning(f"未选中任何类型，默认选择礼物。当前概率总和: {cumulative_prob}")
        return "gift"
    
    def _create_character_card(self, pool: GachaPool) -> Card:
        """创建角色卡片"""
        # 确定稀有度
        rarity_rand = random.random()
        cumulative_prob = 0
        selected_rarity = None
        
        for rarity, prob in pool.character_rates.items():
            cumulative_prob += prob
            if rarity_rand < cumulative_prob:
                selected_rarity = rarity
                break
        
        # 如果没有选中稀有度（概率总和小于1），默认选择R
        if selected_rarity is None:
            selected_rarity = "R"
            logger.warning(f"未选中任何稀有度，默认选择R。当前概率总和: {cumulative_prob}")
        
        # 检查是否有UP角色
        up_cards_of_rarity = [card for card in pool.up_cards if card.rarity == selected_rarity]
        
        if up_cards_of_rarity and random.random() < pool.up_rate_boost:
            # 从UP角色中随机选择一个
            return random.choice(up_cards_of_rarity)
        else:
            # 从普通角色中随机选择一个
            cards_of_rarity = [card for card in pool.cards if card.rarity == selected_rarity and card.type == "character"]
            if cards_of_rarity:
                return random.choice(cards_of_rarity)
            else:
                # 如果没有对应稀有度的角色，从可用资源中随机选择
                return self._create_random_card("character", pool.name, selected_rarity)
    
    def _create_item_card(self, item_type: str, pool_name: str) -> Card:
        """创建物品卡片"""
        return self._create_random_card(item_type, pool_name)
    
    def _create_random_card(self, card_type: str, pool_name: str, rarity: str = "") -> Card:
        """从可用资源中创建随机卡片"""
        available_resources = self.resource_manager.available_resources.get(card_type, [])
        
        if not available_resources:
            # 如果没有对应类型的资源，创建一个默认资源
            logger.warning(f"没有找到{card_type}类型的资源，创建默认资源")
            return Card(
                name=f"默认{card_type}",
                rarity=rarity,
                type=card_type,
                pool=pool_name
            )
        
        # 随机选择一个资源
        selected_name = random.choice(available_resources)
        logger.info(f"从可用资源中选择{card_type}: {selected_name}")
        
        return Card(
            name=selected_name,
            rarity=rarity,
            type=card_type,
            pool=pool_name
        )

    async def _handle_gacha_ten(self, event: AstrMessageEvent, group_id: str) -> MessageEventResult:
        """处理十连抽命令"""
        # 获取当前群组的卡池
        pool = self.resource_manager.get_group_pool(group_id)
        
        # 执行十连抽
        result = self.gacha_ten(pool)
        
        # 生成抽卡结果图片
        image_path = self.presenter.create_gacha_result_image(result)
        
        # 准备结果消息
        message_result = event.make_result()
        
        # 构建结果文本
        text = f"🎴 雀魂十连抽 - {result.pool_name} 🎴\n\n"
        
        message_result.chain = [Plain(text)]
        
        # 如果有图片，添加到结果中
        if image_path and os.path.exists(image_path):
            message_result.chain.append(Image(file=image_path))
        
        return message_result

    async def _handle_view_pool(self, event: AstrMessageEvent, group_id: str) -> MessageEventResult:
        """处理查看卡池命令"""
        # 获取当前群组的卡池
        pool = self.resource_manager.get_group_pool(group_id)
        
        # 准备结果消息
        result = event.make_result()
        
        # 使用presenter格式化卡池信息
        text = self.presenter.format_all_pools(pool.name)
        
        result.chain = [Plain(text)]
        return result

    async def _handle_switch_pool(self, event: AstrMessageEvent, group_id: str) -> MessageEventResult:
        """处理切换卡池命令"""
        message = event.message_str.strip()
        
        # 提取卡池ID
        match = re.search(r"切换雀魂卡池\s+(.+)", message)
        if not match:
            result = event.make_result()
            result.chain = [Plain("请指定要切换的卡池ID，例如：切换雀魂卡池 standard")]
            return result
        
        pool_id = match.group(1).strip()
        
        # 尝试切换卡池
        success, message = self.switch_pool(pool_id)
        
        result = event.make_result()
        result.chain = [Plain(message)]
        return result 
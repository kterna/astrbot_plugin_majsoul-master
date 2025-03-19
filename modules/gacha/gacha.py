from __future__ import annotations
from typing import Dict, List, Tuple, Optional, Union, Any
import random
import json
import os
import re
import time
from pathlib import Path
from astrbot.api.message_components import Plain, Image
from astrbot.api.event import AstrMessageEvent, MessageEventResult

from .models import Card, GachaPool, GachaResult
from .resources import ResourceManager
from .presenter import GachaPresenter

class GachaSystem:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "cache")
        self.pools_file = os.path.join(os.path.dirname(__file__), "pools.json")
        self.resource_manager = ResourceManager(data_dir)
        self.presenter = GachaPresenter(self.resource_manager)
        self.pools = self._load_pools()
        self.current_pool = "standard"
        os.makedirs(self.cache_dir, exist_ok=True)

    def _load_pools(self) -> Dict[str, GachaPool]:
        try:
            with open(self.pools_file, 'r', encoding='utf-8') as f:
                pools_data = json.load(f)
            
            pools = {}
            for pool_name, pool_data in pools_data.items():
                cards = []
                for card_data in pool_data.get("cards", []):
                    cards.append(Card(
                        name=card_data.get("name", "未知角色"),
                        type=card_data.get("type", "character"),
                        pool=pool_name,
                        pool_type=pool_data.get("type", "standard")
                    ))
                
                up_cards = []
                for card_data in pool_data.get("up_cards", []):
                    up_cards.append(Card(
                        name=card_data.get("name", "未知角色"),
                        type=card_data.get("type", "character"),
                        pool=pool_name,
                        pool_type=pool_data.get("type", "standard")
                    ))
                
                pools[pool_name] = GachaPool(
                    name=pool_name,
                    description=pool_data.get("description", ""),
                    cards=cards,
                    up_cards=up_cards,
                    type_rates=pool_data.get("rates"),
                    display_name=pool_data.get("display_name", pool_name),
                    pool_type=pool_data.get("type", "standard")
                )
            return pools
        except Exception:
            default_cards = [Card(name="默认角色", type="character", pool="standard")]
            return {"standard": GachaPool(
                name="standard", 
                description="标准卡池",
                cards=default_cards,
                up_cards=[],
                display_name="标准卡池"
            )}
    
    async def handle_command(self, event: AstrMessageEvent) -> MessageEventResult:
        message = event.message_str.strip()
        group_id = str(event.message_obj.group_id)
        
        if message == "雀魂十连":
            return await self._handle_gacha_ten(event, group_id)
        elif message == "查看雀魂卡池":
            return await self._handle_view_pool(event, group_id)
        elif message.startswith("切换雀魂卡池"):
            return await self._handle_switch_pool(event, group_id)
        
        result = event.make_result()
        result.chain = [Plain("未知的抽卡命令")]
        return result
    
    def switch_pool(self, pool_name: str) -> Tuple[bool, str]:
        if pool_name not in self.pools:
            return False, f"卡池 {pool_name} 不存在，可用卡池: {', '.join(self.pools.keys())}"
        
        self.current_pool = pool_name
        pool = self.pools[pool_name]
        return True, f"已切换到【{pool.display_name}】卡池: {pool.description}"
    
    def gacha_once(self, pool: GachaPool) -> Card:
        try:
            selected_type = self._select_random_type(pool.type_rates)
            
            if selected_type == "character":
                if pool.up_cards and random.random() < pool.up_rate_boost:
                    card = random.choice(pool.up_cards)
                else:
                    character_cards = [card for card in pool.cards if card.type == "character"]
                    if character_cards:
                        card = random.choice(character_cards)
                    else:
                        card = Card(
                            name="默认角色",
                            type="character",
                            pool=pool.name,
                            pool_type=pool.pool_type
                        )
            else:
                card = self._create_item_card(selected_type, pool.name, pool.pool_type)
            return card
        except Exception:
            return Card(
                name="系统错误",
                type="gift",
                pool=pool.name,
                pool_type=pool.pool_type
            )

    def gacha_ten(self, pool: GachaPool) -> GachaResult:
        results = []
        for _ in range(10):
            card = self.gacha_once(pool)
            results.append(card)
        
        return GachaResult(
            cards=results,
            pool_name=pool.name,
            pool_description=pool.description
        )

    def _select_random_type(self, type_rates: Dict[str, float]) -> str:
        type_rand = random.random()
        cumulative_prob = 0
        
        for type_name, prob in type_rates.items():
            cumulative_prob += prob
            if type_rand < cumulative_prob:
                return str(type_name)
        
        return "gift"
    
    def _create_item_card(self, item_type: str, pool_name: str, pool_type: str) -> Card:
        try:
            available_items = self.resource_manager.available_resources.get(item_type, [])
            
            if not available_items:
                return Card(
                    name=f"默认{item_type}",
                    type=item_type,
                    pool=pool_name,
                    pool_type=pool_type
                )
            
            selected_name = random.choice(available_items)
            return Card(
                name=selected_name,
                type=item_type,
                pool=pool_name,
                pool_type=pool_type
            )
        except Exception:
            return Card(
                name=f"默认{item_type}",
                type=item_type,
                pool=pool_name,
                pool_type=pool_type
            )

    async def _handle_gacha_ten(self, event: AstrMessageEvent, group_id: str) -> MessageEventResult:
        pool = self.pools.get(self.current_pool)
        if not pool:
            pool = self.pools["standard"]
        
        result = self.gacha_ten(pool)
        image_path = self.presenter.create_gacha_result_image(result)
        
        message_result = event.make_result()
        message_result.chain = [Plain(f"【{pool.display_name}】十连抽卡结果:")]
        
        if image_path and os.path.exists(image_path):
            message_result.chain.append(Image(file=image_path))
        
        return message_result

    async def _handle_view_pool(self, event: AstrMessageEvent, group_id: str) -> MessageEventResult:
        pool = self.pools.get(self.current_pool)
        if not pool:
            pool = self.pools["standard"]
        
        result = event.make_result()
        text = self.presenter.format_all_pools(pool.name)
        result.chain = [Plain(text)]
        return result

    async def _handle_switch_pool(self, event: AstrMessageEvent, group_id: str) -> MessageEventResult:
        message = event.message_str.strip()
        
        match = re.search(r"切换雀魂卡池\s+(.+)", message)
        if not match:
            result = event.make_result()
            result.chain = [Plain("请指定要切换的卡池ID，例如：切换雀魂卡池 standard")]
            return result
        
        pool_id = match.group(1).strip()
        success, message = self.switch_pool(pool_id)
        
        result = event.make_result()
        result.chain = [Plain(message)]
        return result
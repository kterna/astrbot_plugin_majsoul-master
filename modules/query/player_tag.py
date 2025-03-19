from typing import Dict, List, Union, Any

class PlayerTagAnalyzer:
    """玩家风格标签分析器"""
    
    def __init__(self):
        # 标签阈值配置
        self.thresholds = {
            # 基础行为类
            "对局狂魔": {
                "count": 2000
            },
            "流局策略家": {
                "流局率": 0.18,
                "平均起手向听": {"value": 3.5, "compare": "le"}  # le表示小于等于
            },
            
            # 进攻风格类
            "和牌达人": {
                "和牌率": 0.30,
                "平均打点": 8000,
                "自摸率": 0.40
            },
            "速攻型选手": {
                "和了巡数": {"value": 9.0, "compare": "le"},
                "默听率": 0.60
            },
            "副露进攻型": {
                "副露率": 0.45,
                "放铳时副露率": {"value": 0.15, "compare": "le"}
            },
            "役满成就者": {
                "役满": {"value": 3, "or": "累计役满", "or_value": 5}
            },
            "一发天才": {
                "一发率": 0.12,
                "里宝率": 0.25
            },
            
            # 立直专项类
            "立直专家": {
                "立直率": 0.25,
                "立直后和牌率": 0.45,
                "立直收支": 5000
            },
            "先制立直者": {
                "先制率": 0.70,
                "立直好型": 0.80
            },
            "追立敢死队": {
                "追立率": 0.30,
                "立直多面": 0.60
            },
            "振听冒险家": {
                "振听立直率": 0.15
            },
            
            # 防守专项类
            "防守大师": {
                "放铳率": {"value": 0.12, "compare": "le"},
                "平均铳点": {"value": 4500, "compare": "le"},
                "被炸率": {"value": 0.08, "compare": "le"}
            },
            "铳点控制者": {
                "平均铳点": {"value": 4000, "compare": "le"},
                "铳点损失": {"value": -3000, "compare": "le"}
            },
            "炸庄收割机": {
                "被炸率": 0.15,
                "平均被炸点数": 12000
            },
            "被追立直受害者": {
                "被追率": 0.40
            },
            
            # 效率与策略类
            "高效牌效": {
                "打点效率": 1.2,
                "净打点效率": 0.8
            },
            "攻守平衡型": {
                "和铳比": 2.5,
                "净打点效率": 0.5
            },
            "高风险激进流": {
                "和牌率": 0.30,
                "放铳率": 0.18,
                "平均打点": 8500
            }
        }
        
        # 标签权重配置
        self.weights = {
            # 将在收到具体tag分类后添加
        }
    
    def _check_condition(self, data: Dict[str, Any], key: str, condition: Union[float, Dict]) -> bool:
        """检查单个条件是否满足
        
        Args:
            data: 统计数据
            key: 条件键名
            condition: 条件值或条件配置
            
        Returns:
            bool: 是否满足条件
        """
        if isinstance(condition, dict):
            if "or" in condition:
                # 处理OR条件
                value1 = data.get(key)
                value2 = data.get(condition["or"])
                # 如果两个值都不存在，跳过这个条件
                if value1 is None and value2 is None:
                    return True
                # 如果其中一个值存在且满足条件，返回True
                if (value1 is not None and value1 >= condition["value"]) or \
                   (value2 is not None and value2 >= condition["or_value"]):
                    return True
                return False
            
            # 处理比较条件
            value = data.get(key)
            # 如果值不存在，跳过这个条件
            if value is None:
                return True
            if condition["compare"] == "le":
                return value <= condition["value"]
            return value >= condition["value"]
        
        # 普通大于等于条件
        value = data.get(key)
        # 如果值不存在，跳过这个条件
        if value is None:
            return True
        return value >= condition
    
    def analyze_stats(self, data: Dict[str, Any]) -> List[str]:
        """分析玩家统计数据，返回符合的标签列表"""
        try:
            tags = []
            
            # 基础数据验证
            if not data or not isinstance(data, dict):
                return ["数据异常"]
            
            # 检查对局数
            if data.get('count', 0) < 10:
                return ["数据不足"]
            
            # 计算和铳比（仅当两个值都存在时才计算）
            win_rate = data.get('和牌率')
            deal_in_rate = data.get('放铳率')
            if win_rate is not None and deal_in_rate is not None and deal_in_rate > 0:
                data['和铳比'] = win_rate / deal_in_rate
            
            # 检查所有标签
            for tag, conditions in self.thresholds.items():
                # 跳过特殊名场面标签（需要特殊处理）
                if tag in ["大铳名场面", "连庄王"]:
                    continue
                    
                # 检查该标签的所有条件
                if all(self._check_condition(data, key, condition) 
                      for key, condition in conditions.items()):
                    tags.append(tag)
            
            # 特殊处理大铳名场面
            recent_deal_in = data.get('最近大铳', {})
            if recent_deal_in and recent_deal_in.get('fans'):
                max_fan = max((fan.get('count', 0) for fan in recent_deal_in['fans']), default=0)
                if max_fan >= 13:  # 役满或以上
                    tags.append("大铳名场面")
            
            # 特殊处理连庄王
            max_streak = data.get('最大连庄')
            if max_streak is not None and max_streak >= 6:
                tags.append("连庄王")
            
            return tags if tags else ["普通型"]
            
        except Exception as e:
            return ["分析失败"]
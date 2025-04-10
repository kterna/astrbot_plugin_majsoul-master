from typing import Dict, List, Optional, Tuple, Union
from mahjong.hand_calculating.hand import HandCalculator
from mahjong.shanten import Shanten
from mahjong.tile import TilesConverter

# 役种中文映射
YAKU_NAME_MAP = {
    # 一般役
    "Tsumo": "自摸",
    "Riichi": "立直",
    "Ippatsu": "一发",
    "Chankan": "枪杠",
    "Rinshan": "岭上开花",
    "Haitei": "海底捞月",
    "Houtei": "河底捞鱼",
    "Pinfu": "平和",
    "Tanyao": "断幺九",
    "Iipeiko": "一杯口",
    "Haku": "白",
    "Hatsu": "发",
    "Chun": "中",
    "Yakuhai (wind of place)": "自风",
    "Yakuhai (wind of round)": "场风",
    "YakuhaiEast": "东",
    "YakuhaiSouth": "南",
    "YakuhaiWest": "西",
    "YakuhaiNorth": "北",
    "Sanshoku": "三色同顺",
    "Ittsu": "一气通贯",
    "Chiitoitsu": "七对子",
    "Toitoi": "对对和",
    "Sanankou": "三暗刻",
    "SanKantsu": "三杠子",
    "Sanshoku Doukou": "三色同刻",
    "Honitsu": "混一色",
    "Junchan": "纯全带幺九",
    "Ryanpeikou": "两杯口",
    "Chinitsu": "清一色",
    "Renhou": "人和",
    "Dora": "宝牌",
    "Aka Dora": "赤宝牌",
    "Honroto": "混老头",
    "Shosangen": "小三元",
    "Open Riichi": "开立直",
    "Daburu Riichi": "双立直",
    "Daburu Open Riichi": "开双立直",
    "Nagashi Mangan": "流局满贯",
    "Chantai": "混全带幺九",

    # 役满
    "Tenhou": "天和",
    "Chiihou": "地和",
    "Dai Suushii": "大四喜",
    "Shousuushii": "小四喜",
    "Daisangen": "大三元",
    "Suu Ankou": "四暗刻",
    "Suu Ankou Tanki": "四暗刻单骑",
    "Suu Kantsu": "四杠子",
    "Ryuuiisou": "绿一色",
    "Chinroutou": "清老头",
    "Chuuren Poutou": "九莲宝灯",
    "Daburu Chuuren Poutou": "纯正九莲宝灯",
    "Kokush Musou": "国士无双",
    "Kokushi Musou Juusanmen Matchi": "国士无双十三面",
    "Tsuu Iisou": "字一色",
    "Daichisei": "大七星",
    "Daisharin": "大车轮",
    "Daisuurin": "大数邻",
    "Daichikurin": "大竹林",
    "Paarenchan": "八连庄",
    "Renhou (yakuman)": "人和役满",
    "Sashikomi": "捨て込み"
}

# 结构化数据类
class MahjongResult:
    """麻将计算结果基类"""
    
    def __init__(self, success: bool = True, error: str = None):
        self.success = success
        self.error = error
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        result = {"success": self.success}
        if not self.success:
            result["error"] = self.error
        return result

class HandComponents:
    """手牌组成部分"""
    
    def __init__(self, man: str = '', pin: str = '', sou: str = '', honors: str = ''):
        self.man = man
        self.pin = pin
        self.sou = sou
        self.honors = honors
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "man": self.man,
            "pin": self.pin,
            "sou": self.sou,
            "honors": self.honors
        }

class ShantenResult(MahjongResult):
    """向听数计算结果"""
    
    def __init__(self, shanten: int, success: bool = True, error: str = None):
        super().__init__(success, error)
        self.shanten = shanten
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        result = super().to_dict()
        if self.success:
            result["shanten"] = self.shanten
        return result

class WaitingTile:
    """待张"""
    
    def __init__(self, tile_index: int, count: int):
        self.tile_index = tile_index
        self.count = count
        # 计算可读字符串
        tile_type = ['m', 'p', 's', 'z'][tile_index // 9]
        tile_number = tile_index % 9 + 1
        self.tile_str = f"{tile_number}{tile_type}"
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "tile_index": self.tile_index,
            "count": self.count,
            "tile_str": self.tile_str
        }

class UkeireOption:
    """打牌选择"""
    
    def __init__(self, tile_to_discard: str, tile_index: int, 
                ukeire: int, waiting_tiles: List[Tuple[int, int]]):
        self.tile_to_discard = tile_to_discard
        self.tile_index = tile_index
        self.ukeire = ukeire
        
        # 处理待张信息
        self.waiting = []
        waiting_str_parts = []
        for tile_idx, count in waiting_tiles:
            waiting_tile = WaitingTile(tile_idx, count)
            self.waiting.append(waiting_tile)
            waiting_str_parts.append(f"{waiting_tile.tile_str}:{count}张")
        
        self.waiting_tiles_str = "、".join(waiting_str_parts)
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "tile_to_discard": self.tile_to_discard,
            "tile_index": self.tile_index,
            "ukeire": self.ukeire,
            "waiting": [w.to_dict() for w in self.waiting],
            "waiting_tiles_str": self.waiting_tiles_str
        }

class UkeireResult(MahjongResult):
    """进张分析结果"""
    
    def __init__(self, options: List[UkeireOption] = None, 
                current_shanten: int = 0, success: bool = True, error: str = None):
        super().__init__(success, error)
        self.options = options or []
        self.current_shanten = current_shanten
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        result = super().to_dict()
        if self.success:
            result["current_shanten"] = self.current_shanten
            result["options"] = [option.to_dict() for option in self.options]
        return result

class YakuItem:
    """役种项"""
    
    def __init__(self, name: str, han: int):
        self.name = name
        self.han = han
        self.chinese_name = YAKU_NAME_MAP.get(name, name)
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "name": self.name,
            "han": self.han,
            "chinese_name": self.chinese_name
        }

class HandValueResult(MahjongResult):
    """和牌分析结果"""
    
    def __init__(self, han: int = 0, fu: int = 0, cost: Dict = None, 
                yaku: List[YakuItem] = None, is_yakuman: bool = False,
                success: bool = True, error: str = None):
        super().__init__(success, error)
        self.han = han
        self.fu = fu
        self.cost = cost or {}
        self.yaku = yaku or []
        self.is_yakuman = is_yakuman
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        result = super().to_dict()
        if self.success:
            result.update({
                "han": self.han,
                "fu": self.fu,
                "cost": self.cost,
                "yaku": [y.to_dict() for y in self.yaku],
                "is_yakuman": self.is_yakuman
            })
        return result

class HandAnalysisResult(MahjongResult):
    """手牌分析结果"""
    
    def __init__(self, hand_str: str, total_tiles: int,
                hand_components: HandComponents = None, 
                shanten: ShantenResult = None,
                hand_value: HandValueResult = None,
                ukeire: UkeireResult = None,
                waiting_tiles: List[WaitingTile] = None,
                success: bool = True, error: str = None):
        super().__init__(success, error)
        self.hand_str = hand_str
        self.total_tiles = total_tiles
        self.hand_components = hand_components
        self.shanten = shanten
        self.hand_value = hand_value
        self.ukeire = ukeire
        self.waiting_tiles = waiting_tiles or []
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        result = super().to_dict()
        if self.success:
            result.update({
                "hand_str": self.hand_str,
                "total_tiles": self.total_tiles,
                "hand_components": self.hand_components.to_dict() if self.hand_components else None,
                "shanten": self.shanten.to_dict() if self.shanten else None,
                "hand_value": self.hand_value.to_dict() if self.hand_value else None,
                "ukeire": self.ukeire.to_dict() if self.ukeire else None,
                "waiting_tiles": [w.to_dict() for w in self.waiting_tiles]
            })
        return result

class MahjongHelper:
    """日本麻将基础计算工具类"""
    
    def __init__(self):
        self.calculator = HandCalculator()
        self.shanten = Shanten()
    
    def convert_tiles(self, man='', pin='', sou='', honors='', to_136=True):
        """转换字符串表示的牌为数组格式"""
        if to_136:
            return TilesConverter.string_to_136_array(man=man, pin=pin, sou=sou, honors=honors)
        else:
            return TilesConverter.string_to_34_array(man=man, pin=pin, sou=sou, honors=honors)
    
    def calculate_shanten(self, tiles_34=None, man='', pin='', sou='', honors='') -> ShantenResult:
        """计算向听数"""
        try:
            if tiles_34 is not None:
                shanten = self.shanten.calculate_shanten(tiles_34)
            else:
                tiles = self.convert_tiles(man, pin, sou, honors, to_136=False)
                shanten = self.shanten.calculate_shanten(tiles)
            
            return ShantenResult(shanten=shanten)
        except Exception as e:
            return ShantenResult(shanten=0, success=False, error=str(e))
    
    def calculate_ukeire(self, tiles_136) -> UkeireResult:
        """计算14张牌的打牌选择和进张"""
        try:
            tiles_34 = TilesConverter.to_34_array(tiles_136)
            current_shanten = self.shanten.calculate_shanten(tiles_34)
            ukeire_results = []
            
            for discard_pos in range(len(tiles_34)):
                if not tiles_34[discard_pos]:
                    continue
                    
                tiles_34[discard_pos] -= 1
                ukeire = 0
                waiting_tiles = []
                
                for try_tile in range(len(tiles_34)):
                    if tiles_34[try_tile] >= 4:
                        continue
                        
                    tiles_34[try_tile] += 1
                    new_shanten = self.shanten.calculate_shanten(tiles_34)
                    
                    if new_shanten < current_shanten:
                        original_count = tiles_34[try_tile] - 1
                        if try_tile == discard_pos:
                            original_count += 1
                        remaining = 4 - original_count
                        if remaining > 0:
                            ukeire += remaining
                            waiting_tiles.append((try_tile, remaining))
                        
                    tiles_34[try_tile] -= 1
                
                tiles_34[discard_pos] += 1
                
                if ukeire > 0:
                    tile_type = ['m', 'p', 's', 'z'][discard_pos // 9]
                    tile_number = discard_pos % 9 + 1
                    tile_to_discard = f"{tile_number}{tile_type}"
                    
                    option = UkeireOption(
                        tile_to_discard=tile_to_discard,
                        tile_index=discard_pos,
                        ukeire=ukeire,
                        waiting_tiles=waiting_tiles
                    )
                    
                    ukeire_results.append(option)
            
            # 按进张数降序，牌索引升序排序
            ukeire_results.sort(key=lambda x: (-x.ukeire, x.tile_index))
            
            return UkeireResult(options=ukeire_results, current_shanten=current_shanten)
            
        except Exception as e:
            return UkeireResult(success=False, error=str(e))
    
    def estimate_hand_value(self, tiles_man='', tiles_pin='', tiles_sou='', tiles_honors='',
                           win_tile_type='', win_tile_value='') -> HandValueResult:
        """估算门清荣和手牌价值"""
        try:
            tiles = self.convert_tiles(tiles_man, tiles_pin, tiles_sou, tiles_honors)
            win_tile_dict = {win_tile_type: win_tile_value}
            win_tile = self.convert_tiles(**win_tile_dict)[0]
            
            result = self.calculator.estimate_hand_value(tiles, win_tile)
            
            if result.error:
                return HandValueResult(success=False, error=result.error)
            
            # 转换役种
            yaku_items = []
            if result.yaku:
                for yaku in result.yaku:
                    yaku_name = str(yaku)
                    han = yaku.han_closed if not result.is_open_hand else yaku.han_open
                    yaku_items.append(YakuItem(name=yaku_name, han=han))
            
            # 判断是否役满
            is_yakuman = False
            if result.han >= 13:
                is_yakuman = True
            
            return HandValueResult(
                han=result.han,
                fu=result.fu,
                cost=result.cost,
                yaku=yaku_items,
                is_yakuman=is_yakuman
            )
            
        except Exception as e:
            return HandValueResult(success=False, error=str(e))

class PaiAnalyzer:
    """麻将牌理分析器"""
    
    def __init__(self):
        self.helper = MahjongHelper()
    
    def parse_hand(self, hand_str: str) -> HandComponents:
        """解析手牌字符串，返回万、筒、索、字牌的分类"""
        man = pin = sou = honors = ''
        current_numbers = ''
        
        for char in hand_str:
            if char.isdigit():
                current_numbers += char
            elif char in 'mMpPsS':
                if char.lower() == 'm':
                    man += current_numbers
                elif char.lower() == 'p':
                    pin += current_numbers
                elif char.lower() == 's':
                    sou += current_numbers
                current_numbers = ''
            elif char in 'zZ':
                honors += current_numbers
                current_numbers = ''
        
        return HandComponents(man=man, pin=pin, sou=sou, honors=honors)
    
    def analyze_hand(self, hand_str: str) -> HandAnalysisResult:
        """分析手牌，返回结构化的分析结果"""
        try:
            # 解析手牌
            hand_components = self.parse_hand(hand_str)
            
            # 转换为tiles格式
            tiles_136 = self.helper.convert_tiles(
                hand_components.man, 
                hand_components.pin, 
                hand_components.sou, 
                hand_components.honors
            )
            
            tiles_34 = TilesConverter.to_34_array(tiles_136)
            total_tiles = sum(tiles_34)
            
            # 向听数计算
            shanten_result = self.helper.calculate_shanten(
                man=hand_components.man,
                pin=hand_components.pin,
                sou=hand_components.sou,
                honors=hand_components.honors
            )
            
            # 初始化结果
            result = HandAnalysisResult(
                hand_str=hand_str,
                total_tiles=total_tiles,
                hand_components=hand_components,
                shanten=shanten_result
            )
            
            # 根据手牌数量和向听数进行不同分析
            if total_tiles == 14:
                if shanten_result.shanten == -1:
                    # 和牌分析
                    if hand_components.man:
                        win_tile_type, win_tile_value = 'man', hand_components.man[-1]
                    elif hand_components.pin:
                        win_tile_type, win_tile_value = 'pin', hand_components.pin[-1]
                    elif hand_components.sou:
                        win_tile_type, win_tile_value = 'sou', hand_components.sou[-1]
                    elif hand_components.honors:
                        win_tile_type, win_tile_value = 'honors', hand_components.honors[-1]
                    
                    hand_value = self.helper.estimate_hand_value(
                        tiles_man=hand_components.man, 
                        tiles_pin=hand_components.pin, 
                        tiles_sou=hand_components.sou, 
                        tiles_honors=hand_components.honors,
                        win_tile_type=win_tile_type, 
                        win_tile_value=win_tile_value
                    )
                    
                    result.hand_value = hand_value
                    
                else:
                    # 打牌分析
                    ukeire_result = self.helper.calculate_ukeire(tiles_136)
                    result.ukeire = ukeire_result
            
            elif total_tiles == 13:
                if shanten_result.shanten == 0:
                    # 听牌分析
                    waiting_tiles = []
                    original_tiles_34 = tiles_34.copy()
                    
                    for try_tile in range(34):
                        if original_tiles_34[try_tile] >= 4:
                            continue
                            
                        tiles_34[try_tile] += 1
                        if self.helper.calculate_shanten(tiles_34=tiles_34).shanten == -1:
                            remaining = 4 - original_tiles_34[try_tile]
                            if remaining > 0:
                                waiting_tile = WaitingTile(try_tile, remaining)
                                waiting_tiles.append(waiting_tile)
                        tiles_34[try_tile] -= 1
                    
                    result.waiting_tiles = waiting_tiles
                
                else:
                    # 向听分析
                    best_tiles = []
                    best_shanten = shanten_result.shanten
                    original_tiles_34 = tiles_34.copy()

                    for try_tile in range(34):
                        if original_tiles_34[try_tile] >= 4:
                            continue
                        
                        tiles_34[try_tile] += 1
                        new_shanten = self.helper.calculate_shanten(tiles_34=tiles_34).shanten
                        if new_shanten < best_shanten:
                            remaining = 4 - original_tiles_34[try_tile]
                            if remaining > 0:
                                best_tiles = [WaitingTile(try_tile, remaining)]
                            best_shanten = new_shanten
                        elif new_shanten == best_shanten:
                            remaining = 4 - original_tiles_34[try_tile]
                            if remaining > 0:
                                best_tiles.append(WaitingTile(try_tile, remaining))
                        tiles_34[try_tile] -= 1
                    
                    result.waiting_tiles = best_tiles
            
            else:
                result.success = False
                result.error = f"手牌数量（{total_tiles}）不正确，应为13或14张"
            
            return result
            
        except Exception as e:
            return HandAnalysisResult(
                hand_str=hand_str,
                total_tiles=0,
                success=False, 
                error=f"分析失败: {str(e)}"
            )
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
    
    def calculate_shanten(self, tiles_34=None, man='', pin='', sou='', honors=''):
        """计算向听数"""
        if tiles_34 is not None:
            return self.shanten.calculate_shanten(tiles_34)
        else:
            tiles = self.convert_tiles(man, pin, sou, honors, to_136=False)
            return self.shanten.calculate_shanten(tiles)
    
    def calculate_ukeire(self, tiles_136, print_progress=False):
        """计算14张牌的打牌选择和进张"""
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
                
                result = {
                    'tile_to_discard': f"{tile_number}{tile_type}",
                    'tile_index': discard_pos,
                    'ukeire': ukeire,
                    'waiting': waiting_tiles,
                    'waiting_tiles_str': self._convert_tiles_to_str(waiting_tiles)
                }
                
                ukeire_results.append(result)
                
                if print_progress:
                    print(f"打{tile_number}{tile_type}: 进张数={ukeire}, "
                          f"待张={result['waiting_tiles_str']}")
        
        return sorted(ukeire_results, key=lambda x: (-x['ukeire'], x['tile_index']))

    def _convert_tiles_to_str(self, tiles_34_with_count):
        """将34格式的牌数组转换为可读字符串"""
        result = []
        for tile, count in tiles_34_with_count:
            tile_type = ['m', 'p', 's', 'z'][tile // 9]
            tile_number = tile % 9 + 1
            result.append(f"{tile_number}{tile_type}:{count}张")
        return "、".join(result)
    
    def estimate_hand_value(self, tiles_man='', tiles_pin='', tiles_sou='', tiles_honors='',
                           win_tile_type='', win_tile_value=''):
        """估算门清荣和手牌价值"""
        tiles = self.convert_tiles(tiles_man, tiles_pin, tiles_sou, tiles_honors)
        win_tile_dict = {win_tile_type: win_tile_value}
        win_tile = self.convert_tiles(**win_tile_dict)[0]
        return self.calculator.estimate_hand_value(tiles, win_tile)


class PaiAnalyzer:
    """麻将牌理分析器"""
    
    def __init__(self):
        self.helper = MahjongHelper()
    
    def parse_hand(self, hand_str):
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
        
        return man, pin, sou, honors
    
    def analyze_hand(self, hand_str):
        """分析手牌，返回向听数、进张、和牌信息等"""
        try:
            man, pin, sou, honors = self.parse_hand(hand_str)
            tiles_136 = self.helper.convert_tiles(man, pin, sou, honors)
            tiles_34 = TilesConverter.to_34_array(tiles_136)
            total_tiles = sum(tiles_34)
            shanten = self.helper.calculate_shanten(tiles_34=tiles_34)
            result = f"手牌: {hand_str}\n"
            
            if total_tiles == 14:
                result += "手牌数: 14张\n"
                if shanten == -1:
                    if man:
                        win_tile_type, win_tile_value = 'man', man[-1]
                    elif pin:
                        win_tile_type, win_tile_value = 'pin', pin[-1]
                    elif sou:
                        win_tile_type, win_tile_value = 'sou', sou[-1]
                    elif honors:
                        win_tile_type, win_tile_value = 'honors', honors[-1]
                    
                    hand_result = self.helper.estimate_hand_value(
                        tiles_man=man, tiles_pin=pin, 
                        tiles_sou=sou, tiles_honors=honors,
                        win_tile_type=win_tile_type, win_tile_value=win_tile_value
                    )
                    
                    if hand_result.yaku is None or hand_result.han == 0:
                        result += "无役，不能和牌\n"
                    else:
                        result += f"和牌分析:\n番数: {hand_result.han}, 符数: {hand_result.fu}\n"
                        result += f"点数: {hand_result.cost['main']}\n"
                        result += "役种:\n"
                        for yaku in hand_result.yaku:
                            yaku_name = str(yaku)
                            chinese_name = YAKU_NAME_MAP.get(yaku_name, yaku_name)
                            result += f"- {chinese_name}\n"
                else:
                    result += f"向听数: {shanten}\n\n打牌建议:\n"
                    ukeire_results = self.helper.calculate_ukeire(tiles_136)
                    
                    for i, ukeire in enumerate(ukeire_results, 1):
                        result += f"{i}. 打{ukeire['tile_to_discard']}: 进张数={ukeire['ukeire']}\n"
                        tiles_after = tiles_34.copy()
                        tiles_after[ukeire['tile_index']] -= 1
                        shanten_after = self.helper.calculate_shanten(tiles_34=tiles_after)
                        
                        if shanten_after == 0:
                            result += f"   打出后听牌，待张：{ukeire['waiting_tiles_str']}\n"
                        else:
                            result += f"   待张：{ukeire['waiting_tiles_str']}\n"
            
            elif total_tiles == 13:
                result += "手牌数: 13张\n"
                if shanten == 0:
                    waiting_tiles = []
                    waiting_count = 0
                    original_tiles_34 = tiles_34.copy()
                    
                    for try_tile in range(34):
                        if original_tiles_34[try_tile] >= 4:
                            continue
                            
                        tiles_34[try_tile] += 1
                        if self.helper.calculate_shanten(tiles_34=tiles_34) == -1:
                            remaining = 4 - original_tiles_34[try_tile]
                            if remaining > 0:
                                waiting_tiles.append((try_tile, remaining))
                                waiting_count += remaining
                        tiles_34[try_tile] -= 1
                    
                    result += "听牌！\n"
                    result += f"共{waiting_count}张铳牌\n"
                    result += "听牌张："
                    waiting_str = []
                    for tile, count in waiting_tiles:
                        tile_type = ['m', 'p', 's', 'z'][tile // 9]
                        tile_number = tile % 9 + 1
                        waiting_str.append(f"{tile_number}{tile_type}:{count}张")
                    result += "、".join(waiting_str) + "\n"
                else:
                    result += f"向听数: {shanten}\n"
                    best_tiles = []
                    best_shanten = shanten
                    original_tiles_34 = tiles_34.copy()

                    for try_tile in range(34):
                        if original_tiles_34[try_tile] >= 4:
                            continue
                        
                        tiles_34[try_tile] += 1
                        new_shanten = self.helper.calculate_shanten(tiles_34=tiles_34)
                        if new_shanten < best_shanten:
                            remaining = 4 - original_tiles_34[try_tile]
                            if remaining > 0:
                                best_tiles = [(try_tile, remaining)]
                            best_shanten = new_shanten
                        elif new_shanten == best_shanten:
                            remaining = 4 - original_tiles_34[try_tile]
                            if remaining > 0:
                                best_tiles.append((try_tile, remaining))
                        tiles_34[try_tile] -= 1
                    
                    total_tiles = sum(count for _, count in best_tiles)
                    result += f"进张数：{total_tiles}张\n进张："
                    
                    tiles_str = []
                    for tile, count in best_tiles:
                        tile_type = ['m', 'p', 's', 'z'][tile // 9]
                        tile_number = tile % 9 + 1
                        tiles_str.append(f"{tile_number}{tile_type}:{count}张")
                    result += "、".join(tiles_str)
            
            else:
                result += f"错误：手牌数量（{total_tiles}）不正确，应为13或14张\n"
            
            return result
            
        except Exception as e:
            return f"分析失败: {str(e)}"
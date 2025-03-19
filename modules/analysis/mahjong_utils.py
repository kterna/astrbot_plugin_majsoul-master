# mahjong_helper.py

from mahjong.hand_calculating.hand import HandCalculator
from mahjong.hand_calculating.hand_config import HandConfig
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
    """日本麻将助手：提供简化的麻将计算接口"""
    
    def __init__(self):
        """初始化麻将助手"""
        self.calculator = HandCalculator()
        self.shanten = Shanten()
    
    def convert_tiles(self, man='', pin='', sou='', honors='', to_136=True):
        """转换字符串表示的牌为数组格式"""
        if to_136:
            return TilesConverter.string_to_136_array(man=man, pin=pin, sou=sou, honors=honors)
        else:
            return TilesConverter.string_to_34_array(man=man, pin=pin, sou=sou, honors=honors)
    
    def calculate_shanten(self, man='', pin='', sou='', honors=''):
        """计算向听数"""
        tiles = self.convert_tiles(man, pin, sou, honors, to_136=False)
        return self.shanten.calculate_shanten(tiles)
    
    def estimate_hand_value(self, tiles_man='', tiles_pin='', tiles_sou='', tiles_honors='',
                           win_tile_type='', win_tile_value=''):
        """估算门清荣和手牌价值"""
        # 转换手牌
        tiles = self.convert_tiles(tiles_man, tiles_pin, tiles_sou, tiles_honors)
        
        # 转换和牌
        win_tile_dict = {win_tile_type: win_tile_value}
        win_tile = self.convert_tiles(**win_tile_dict)[0]
        
        # 估算手牌价值
        return self.calculator.estimate_hand_value(tiles, win_tile)
    


class PaiAnalyzer:
    """麻将牌理分析器，解析手牌并计算向听数和得点"""
    
    def __init__(self):
        self.helper = MahjongHelper()
    
    def parse_hand(self, hand_str):
        """解析手牌字符串，返回万、筒、索、字牌的分类"""
        # 初始化空字符串
        man = pin = sou = honors = ''
        
        # 提取数字和类型
        current_numbers = ''
        for char in hand_str:
            if char.isdigit():
                current_numbers += char
            elif char in 'mMpPsS':  # 万、筒、索
                if char.lower() == 'm':
                    man += current_numbers
                elif char.lower() == 'p':
                    pin += current_numbers
                elif char.lower() == 's':
                    sou += current_numbers
                current_numbers = ''
            elif char in 'zZ':  # 字牌
                honors += current_numbers
                current_numbers = ''
        
        return man, pin, sou, honors
    
    def analyze_hand(self, hand_str):
        """分析手牌，计算向听数"""
        try:
            # 解析手牌
            man, pin, sou, honors = self.parse_hand(hand_str)
            
            # 计算向听数
            shanten = self.helper.calculate_shanten(man, pin, sou, honors)
            
            # 生成分析结果
            result = f"手牌: {hand_str}\n向听数: {shanten}\n"
            
            if shanten == 0:
                result += "听牌: [待实现]\n"
            elif shanten == -1:
                # 和了，计算得点
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
            
            return result
        
        except Exception as e:
            return f"分析失败: {str(e)}"
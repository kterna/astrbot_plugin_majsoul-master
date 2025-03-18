# mahjong_helper.py

from mahjong.hand_calculating.hand import HandCalculator
from mahjong.hand_calculating.hand_config import HandConfig
from mahjong.shanten import Shanten
from mahjong.tile import TilesConverter

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
    
    def print_result(self, result):
        """打印手牌结果"""
        if not result.yaku and not result.han:
            print("无效和牌")
            return
        
        print(f"番数: {result.han}, 符数: {result.fu}")
        print(f"点数: {result.cost['main']}")
        print("役种:")
        for yaku in result.yaku:
            print(f"- {str(yaku)}")
        
        if result.fu_details:
            print("符数明细:")
            for fu_item in result.fu_details:
                print(f"- {fu_item}")
        print()


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
                # 这里简化处理，假设最后一张牌是自摸/荣和
                # 实际应用中可能需要更复杂的处理
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
                        result += f"- {str(yaku)}\n"
            
            return result
        
        except Exception as e:
            return f"分析失败: {str(e)}"

# 使用示例
if __name__ == "__main__":
    helper = MahjongHelper()
    
    # 示例1: 断幺九役
    print("示例1: 断幺九")
    result = helper.estimate_hand_value(
        tiles_man='22444', tiles_pin='333567', tiles_sou='444',
        win_tile_type='sou', win_tile_value='4'
    )
    helper.print_result(result)
    
    # 示例2: 向听数计算
    print("示例2: 向听数计算")
    shanten = helper.calculate_shanten(man='13569', pin='123459', sou='443')
    print(f"向听数: {shanten}\n")
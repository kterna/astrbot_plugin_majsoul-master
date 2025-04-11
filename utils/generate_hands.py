import random
import os
from typing import Dict, List, Tuple
import sys
import json

# 添加项目根目录到路径，以便导入模块
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '..'))
sys.path.append(project_root)

from modules.analysis.mahjong_utils import PaiAnalyzer

# 定义风和牌型
ROUND_WINDS = {1: "东", 2: "南"}  # 场风
PLAYER_WINDS = {1: "东", 2: "南", 3: "西", 4: "北"}  # 自风
SUIT_TYPES = ['m', 'p', 's']  # 万、筒、索
HONOR_TYPE = 'z'  # 字牌

def count_tiles(hand_str: str) -> Dict[str, int]:
    """统计手牌中各种牌的数量"""
    tile_counts = {}
    current_numbers = ""
    
    for char in hand_str:
        if char.isdigit():
            current_numbers += char
        elif char in 'mpsz':
            for number in current_numbers:
                tile_key = f"{number}{char}"
                tile_counts[tile_key] = tile_counts.get(tile_key, 0) + 1
            current_numbers = ""
    
    return tile_counts

def generate_mentsu_based_hand() -> str:
    """
    按照4面子+1雀头的方式生成手牌：
    1. 随机分组4个面子+1个雀头到万、饼、索、字
    2. 面子分为顺子和刻子，顺子从1-7随机取一个数字生成，刻子从1-9随机取一个数字生成。字牌只有刻子1-7
    3. 生成完毕后将其组合起来，按照数字顺序和mpsz顺序组合成字符串
    """
    # 初始化存储不同花色的牌
    parts = {'m': [], 'p': [], 's': [], 'z': []}
    
    # 1. 生成雀头(对子)
    # 随机选择花色
    head_suit = random.choice(['m', 'p', 's', 'z'])
    # 随机选择数字
    if head_suit == 'z':  # 字牌1-7
        head_number = random.randint(1, 7)
    else:  # 数牌1-9
        head_number = random.randint(1, 9)
    # 添加雀头
    parts[head_suit].extend([head_number, head_number])
    
    # 2. 生成4个面子(每个面子3张牌)
    for _ in range(4):
        # 随机选择花色
        mentsu_suit = random.choice(['m', 'p', 's', 'z'])
        
        # 字牌只能做刻子
        if mentsu_suit == 'z':
            # 字牌刻子(1-7)
            number = random.randint(1, 7)
            # 添加刻子
            parts[mentsu_suit].extend([number, number, number])
        else:
            # 万、筒、索可以做顺子或刻子
            # 随机决定是顺子还是刻子
            is_shuntsu = random.random() < 0.8  # 80%概率生成顺子
            
            if is_shuntsu:
                # 顺子(1-7起始)
                start = random.randint(1, 7)
                # 添加顺子
                parts[mentsu_suit].extend([start, start+1, start+2])
            else:
                # 刻子(1-9)
                number = random.randint(1, 9)
                # 添加刻子
                parts[mentsu_suit].extend([number, number, number])
    
    # 3. 按照数字顺序和花色顺序(mpsz)组合成字符串
    hand_str = ""
    for suit in ['m', 'p', 's', 'z']:
        if parts[suit]:
            # 对每种花色的牌按数字排序
            parts[suit].sort()
            # 转换为字符串并添加花色
            hand_str += ''.join(map(str, parts[suit])) + suit
    
    return hand_str

def generate_valid_hands(limit: int, output_file: str) -> str:
    """生成有效的麻将胡牌并保存到文件"""
    pai_analyzer = PaiAnalyzer()
    valid_hands = []
    attempts = 0
    max_attempts = 1000000  # 最大尝试次数
    
    while len(valid_hands) < limit and attempts < max_attempts:
        attempts += 1
        
        try:
            # 1. 随机分组4面子+1雀头到万、饼、索、字中
            hand_str = generate_mentsu_based_hand()

            # 2. 从手牌中随机选择一张作为胡牌
            # 正确解析手牌中的每种牌，处理多位数字
            hand_tiles = []
            current_suit = None
            
            # 逐字符解析手牌
            i = 0
            while i < len(hand_str):
                if hand_str[i].isdigit():
                    # 收集连续的数字
                    num_start = i
                    while i < len(hand_str) and hand_str[i].isdigit():
                        i += 1
                    # 数字全部收集完毕
                    if i < len(hand_str) and hand_str[i] in 'mpsz':
                        # 找到花色
                        current_suit = hand_str[i]
                        # 将每个数字与花色组合
                        for num in hand_str[num_start:i]:
                            hand_tiles.append(f"{num}{current_suit}")
                        i += 1
                else:
                    # 跳过非数字非花色字符
                    i += 1
                
            if not hand_tiles:
                continue
                
            win_tile_str = random.choice(hand_tiles)
            
            # 4. 使用analysis模块分析是否有役种
            full_hand_str = hand_str + win_tile_str[0]
            
            # 3. 随机生成场风和自风
            round_wind = random.randint(1, 2)
            player_wind = random.randint(1, 4)
            
            analysis_result = pai_analyzer.analyze_hand(full_hand_str, round_wind=round_wind, player_wind=player_wind)
            
            # 5. 检查是否有役种并成功和牌
            if (analysis_result.success and 
                analysis_result.hand_value and 
                analysis_result.hand_value.success and 
                len(analysis_result.hand_value.yaku) > 0):
                
                # 有效手牌，保存结果
                valid_hand = {
                    "hand": hand_str,
                    "win_tile": win_tile_str,
                    "round_wind_str": ROUND_WINDS[round_wind],
                    "player_wind_str": PLAYER_WINDS[player_wind],
                    "han": analysis_result.hand_value.han,
                    "fu": analysis_result.hand_value.fu,
                    "yaku": [yaku.to_dict() for yaku in analysis_result.hand_value.yaku]
                }
                
                valid_hands.append(valid_hand)
                
                # 重要：每次生成成功后，重置attempts确保下一轮循环会生成新的手牌
                attempts = 0
            else:
                error_msg = ""
                if not analysis_result.success:
                    error_msg = f"分析失败: {analysis_result.error}"
                elif not analysis_result.hand_value:
                    error_msg = "没有有效役种值"
                elif not analysis_result.hand_value.success:
                    error_msg = f"手牌值分析失败: {analysis_result.hand_value.error}"
                else:
                    error_msg = "没有有效役种"
                
        except Exception as e:
            continue
    
    if not valid_hands:
        return "生成失败：未能生成任何有效手牌"
        
    # 保存到文件
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(valid_hands, f, ensure_ascii=False, indent=2)
        return f"生成成功{len(valid_hands)}条"
    except Exception as e:
        return f"保存文件失败: {str(e)}"

if __name__ == "__main__":
    output_dir = os.path.join(project_root, "data", "generated_hands")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "valid_hands.json")
    
    # 可通过命令行参数指定生成数量
    try:
        num_hands = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    except ValueError:
        num_hands = 10
    
    # 生成有效手牌
    generate_valid_hands(num_hands, output_file) 
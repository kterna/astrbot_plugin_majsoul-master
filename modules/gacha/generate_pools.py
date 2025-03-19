import os
import json
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

def load_character_resources(person_dir: str) -> Dict[str, List[str]]:
    """加载角色资源目录下的所有角色名称和分类信息
    
    通过读取文件名来确定角色所属的卡池：
    - 包含"初始形象"的进入标准池
    - 包含"限定"的进入限定池
    - 包含"契约"的进入契约池
    - 包含"联名"的进入联名池
    """
    pools = {
        "standard": set(),
        "contract": set(),
        "limited": set(),
        "collab": set()
    }
    
    try:
        # 遍历角色目录
        for character_dir in os.listdir(person_dir):
            dir_path = os.path.join(person_dir, character_dir)
            if not os.path.isdir(dir_path):
                continue
                
            # 读取角色目录下的所有文件
            character_files = os.listdir(dir_path)
            
            # 根据文件名分类角色
            for file_name in character_files:
                if "初始形象" in file_name:
                    pools["standard"].add(character_dir)
                elif "活动限定" in file_name:
                    pools["limited"].add(character_dir)
                elif "契约" in file_name:
                    pools["contract"].add(character_dir)
                elif "联动" in file_name:
                    pools["collab"].add(character_dir)
        
        # 转换set为排序后的list
        return {
            pool_name: sorted(list(chars))
            for pool_name, chars in pools.items()
        }
        
    except Exception as e:
        logger.error(f"加载角色资源失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {pool_name: [] for pool_name in pools}

def create_pool_template() -> Dict[str, Any]:
    """创建基础卡池模板"""
    return {
        "standard": {
            "display_name": "标准池",
            "description": "常驻角色池",
            "rates": {
                "character": 0.01,
                "decoration": 0.09,
                "gift": 0.60,
                "jades": 0.30
            },
            "cards": [],
            "up_cards": []
        },
        "contract": {
            "display_name": "契约池",
            "description": "契约限定角色池",
            "rates": {
                "character": 0.02,
                "decoration": 0.08,
                "gift": 0.60,
                "jades": 0.30
            },
            "cards": [],
            "up_cards": []
        },
        "limited": {
            "display_name": "限定池",
            "description": "限时限定角色池",
            "rates": {
                "character": 0.02,
                "decoration": 0.08,
                "gift": 0.60,
                "jades": 0.30
            },
            "cards": [],
            "up_cards": []
        },
        "collab": {
            "display_name": "联名池",
            "description": "联名合作角色池",
            "rates": {
                "character": 0.02,
                "decoration": 0.08,
                "gift": 0.60,
                "jades": 0.30
            },
            "cards": [],
            "up_cards": []
        }
    }

def generate_pools_config(person_dir: str, output_file: str) -> bool:
    """生成卡池配置文件
    
    Args:
        person_dir: 角色资源目录路径
        output_file: 输出文件路径
        
    Returns:
        bool: 是否成功生成配置文件
    """
    try:
        # 加载并分类所有角色
        classified_chars = load_character_resources(person_dir)
        if not any(classified_chars.values()):
            logger.error("未找到任何角色资源")
            return False
            
        # 打印分类结果
        for pool_name, chars in classified_chars.items():
            logger.info(f"{pool_name}池角色数量: {len(chars)}")
            if chars:
                logger.info(f"角色列表: {', '.join(chars)}")
        
        # 创建卡池配置
        pools_config = create_pool_template()
        
        # 将角色添加到各个卡池中
        for pool_name, chars in classified_chars.items():
            for char in chars:
                pools_config[pool_name]["cards"].append({
                    "name": char,
                    "type": "character"
                })
        
        # 保存配置文件
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(pools_config, f, ensure_ascii=False, indent=4)
            
        logger.info(f"成功生成卡池配置文件: {output_file}")
        
        # 打印每个池子的角色数量
        print("\n卡池角色统计：")
        for pool_name, pool_data in pools_config.items():
            print(f"{pool_data['display_name']}: {len(pool_data['cards'])} 个角色")
            if pool_data['cards']:
                print(f"角色列表: {', '.join(card['name'] for card in pool_data['cards'])}")
            print()
            
        return True
        
    except Exception as e:
        logger.error(f"生成卡池配置文件失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def classify_characters(characters: List[str]) -> Dict[str, List[str]]:
    """将角色分类到不同的卡池中
    
    分类规则：
    1. 标准池：不包含特殊关键词的角色
    2. 契约池：包含"契约"关键词的角色
    3. 限定池：包含"限定"关键词的角色
    4. 联名池：包含"联名"关键词的角色
    """
    pools = {
        "standard": [],
        "contract": [],
        "limited": [],
        "collab": []
    }
    
    for char in characters:
        if "契约" in char:
            pools["contract"].append(char)
        elif "限定" in char:
            pools["limited"].append(char)
        elif "联名" in char:
            pools["collab"].append(char)
        else:
            pools["standard"].append(char)
    
    # 打印分类结果
    for pool_name, chars in pools.items():
        logger.info(f"{pool_name}池角色数量: {len(chars)}")
        if chars:
            logger.info(f"{pool_name}池角色列表: {', '.join(chars)}")
    
    return pools

def main():
    """主函数"""
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 构建资源目录路径 - 使用相对路径
    # 从 modules/gacha 向上两级到达 astrbot_plugin_majsoul-master，然后进入 data/resources
    resources_dir = os.path.join(os.path.dirname(os.path.dirname(script_dir)), "data", "resources")
    person_dir = os.path.join(resources_dir, "person")
    
    # 构建输出文件路径
    output_file = os.path.join(script_dir, "pools.json")
    
    print(f"使用资源目录: {person_dir}")
    
    # 生成配置文件
    if generate_pools_config(person_dir, output_file):
        print(f"成功生成卡池配置文件: {output_file}")
    else:
        print("生成卡池配置文件失败")

if __name__ == "__main__":
    main() 
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os
import random
import logging
import time
from astrbot.api.message_components import Plain, Image as MessageImage
from .models import Card, GachaResult
from .resources import ResourceManager
from ...utils.image_utils import ImageUtils

logger = logging.getLogger(__name__)

class GachaPresenter:
    """抽卡结果展示器"""
    
    def __init__(self, resource_manager: ResourceManager):
        self.resource_manager = resource_manager
        self.resources_dir = resource_manager.resources_dir
        self.temp_dir = resource_manager.get_temp_dir()
        logger.info(f"使用临时目录: {self.temp_dir}")
        
        # 加载字体
        self._load_fonts()
        
        # 类型颜色
        self.type_colors = {
            "character": (255, 105, 180),  # 粉色
            "decoration": (50, 205, 50),   # 绿色
            "gift": (255, 165, 0),         # 橙色
            "jades": (64, 224, 208)        # 青色
        }

    def _load_fonts(self):
        """加载字体"""
        self.font_path = None
        system_fonts = [
            "C:/Windows/Fonts/msyh.ttc",  # Windows
            "C:/Windows/Fonts/simhei.ttf",  # Windows备选
            "/usr/share/fonts/truetype/msttcorefonts/msyh.ttc",  # Linux
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",  # Linux备选
            "/System/Library/Fonts/PingFang.ttc"  # macOS
        ]
        for font in system_fonts:
            if os.path.exists(font):
                self.font_path = font
                logger.info(f"使用系统字体: {font}")
                break
        
        if not self.font_path:
            logger.warning("未找到合适的字体，将使用默认字体")
            self.font_path = ImageFont.load_default()
    
    def _get_background(self) -> Image.Image:
        """获取背景图片"""
        try:
            # 获取所有背景图片路径
            bg_paths = self.resource_manager.get_all_backgrounds()
            if bg_paths:
                # 随机选择一个背景
                bg_path = random.choice(bg_paths)
                if os.path.exists(bg_path):
                    return Image.open(bg_path)
        except Exception as e:
            logger.error(f"加载背景图片失败: {e}")
        
        # 如果加载失败，创建一个默认背景
        return Image.new('RGB', (800, 600), (30, 30, 30))

    def _get_text_width(self, draw, text, font):
        """获取文本宽度，兼容不同版本的PIL"""
        if hasattr(draw, 'textlength'):
            return draw.textlength(text, font=font)
        else:
            # 对于较旧版本的PIL，使用getsize
            width, _ = font.getsize(text)
            return width

    def create_gacha_result_image(self, result: GachaResult) -> str:
        """创建抽卡结果图片
        
        Args:
            result: 抽卡结果
            
        Returns:
            str: 图片路径
        """
        try:
            logger.info("开始创建抽卡结果图片")
            
            # 设置卡片尺寸
            card_width = 160
            card_height = 180
            padding = 10
            cols = 5
            rows = (len(result.cards) + cols - 1) // cols
            
            # 创建背景图
            width = cols * card_width + (cols + 1) * padding
            height = rows * card_height + (rows + 1) * padding + 60  # 额外空间用于标题
            
            logger.info(f"创建背景图，尺寸: {width}x{height}")
            
            # 获取背景图片
            background = self._get_background()
            background = background.resize((width, height))
            background = background.filter(ImageFilter.GaussianBlur(radius=3))
            
            draw = ImageDraw.Draw(background)
            
            # 加载字体
            try:
                if isinstance(self.font_path, str):
                    title_font = ImageFont.truetype(self.font_path, 32)
                    name_font = ImageFont.truetype(self.font_path, 16)
                else:
                    title_font = self.font_path
                    name_font = self.font_path
            except Exception as e:
                logger.error(f"加载字体失败: {e}，使用默认字体")
                title_font = ImageFont.load_default()
                name_font = ImageFont.load_default()
            
            # 绘制每张卡片
            logger.info(f"开始绘制{len(result.cards)}张卡片")
            
            for i, card in enumerate(result.cards):
                try:
                    row = i // cols
                    col = i % cols
                    
                    x = padding + col * (card_width + padding)
                    y = padding + row * (card_height + padding) + 60  # 标题下方开始
                    
                    # 创建卡片背景
                    card_bg_color = (*self.type_colors.get(card.type, (100, 100, 100)), 150)
                    card_img = Image.new('RGBA', (card_width, card_height), (0, 0, 0, 0))
                    card_draw = ImageDraw.Draw(card_img)
                    
                    # 绘制半透明卡片背景
                    card_draw.rectangle((0, 0, card_width, card_height), fill=card_bg_color)
                    
                    # 获取卡片图片路径并加载
                    card_image_path = card.get_image_path(self.resources_dir)
                    if card_image_path and os.path.exists(card_image_path):
                        try:
                            card_image = Image.open(card_image_path)
                            # 调整图片大小
                            card_image = card_image.resize((card_width - 6, card_height - 30))
                            # 将图片粘贴到卡片中央
                            card_img.paste(card_image, (3, 3))
                        except Exception as e:
                            logger.error(f"加载卡片图片失败: {e}")
                    
                    # 如果没有找到图片，绘制占位符
                    if not card_image_path or not os.path.exists(card_image_path):
                        text = {
                            "character": "角色",
                            "decoration": "装饰",
                            "gift": "礼物",
                            "jades": "玉石"
                        }.get(card.type, card.type)
                        
                        text_width = self._get_text_width(card_draw, text, name_font)
                        card_draw.text(
                            ((card_width - text_width) // 2, card_height // 2 - 10),
                            text,
                            font=name_font,
                            fill=(200, 200, 200)
                        )
                    
                    # 绘制卡片名称
                    name = card.name[:7] + "..." if len(card.name) > 8 else card.name
                    name_bg = Image.new('RGBA', (card_width, 25), (0, 0, 0, 180))
                    name_draw = ImageDraw.Draw(name_bg)
                    name_width = self._get_text_width(name_draw, name, name_font)
                    name_draw.text(
                        ((card_width - name_width) // 2, 5),
                        name,
                        font=name_font,
                        fill=(255, 255, 255)
                    )
                    card_img.paste(name_bg, (0, card_height - 25), name_bg)
                    
                    # 转换为RGB并粘贴到背景
                    card_rgb = Image.new('RGB', card_img.size, (0, 0, 0))
                    card_rgb.paste(card_img, (0, 0), card_img)
                    background.paste(card_rgb, (x, y))
                    
                except Exception as e:
                    logger.error(f"绘制第{i+1}张卡片时出错: {e}")
            
            # 保存图片
            timestamp = int(time.time() * 1000)
            random_suffix = random.randint(0, 999)
            output_path = os.path.join(self.temp_dir, f"gacha_result_{timestamp}_{random_suffix}.png")
            background.save(output_path)
            return output_path
            
        except Exception as e:
            logger.error(f"创建抽卡结果图片失败: {e}")
            return ""

    def generate_gacha_image(self, result: GachaResult) -> str:
        """生成抽卡结果图片（别名方法）
        
        Args:
            result: 抽卡结果
            
        Returns:
            str: 图片路径
        """
        return self.create_gacha_result_image(result)

    def format_all_pools(self, current_pool_name: str) -> str:
        """格式化所有卡池信息
        
        Args:
            current_pool_name: 当前卡池名称
            
        Returns:
            str: 格式化后的卡池信息
        """
        text = "【雀魂抽卡卡池列表】\n\n"
        text += f"当前卡池: {current_pool_name}\n\n"
        text += "可用卡池:\n"
        
        # 获取所有卡池信息并排序
        pools = []
        available_pools = self.resource_manager.get_available_pools()
        for pool_id, pool_data in available_pools.items():
            is_current = pool_data.get("name") == current_pool_name
            pools.append((pool_id, pool_data.get("name", pool_id), pool_data.get("description", ""), is_current))
        
        # 按照是否为当前卡池和ID排序
        pools.sort(key=lambda x: (not x[3], x[0]))
        
        # 格式化每个卡池信息
        for pool_id, name, description, is_current in pools:
            prefix = "▶ " if is_current else "- "
            text += f"{prefix}{pool_id} ({name}): {description}\n"
            
            # 显示UP角色
            pool_data = available_pools.get(pool_id, {})
            if "up_cards" in pool_data and pool_data["up_cards"]:
                text += "  [UP!]: "
                up_cards = []
                for card in pool_data["up_cards"]:
                    up_cards.append(card.get("name"))
                text += ", ".join(up_cards) + "\n"
        
        text += "\n切换卡池命令: 切换雀魂卡池 [卡池ID]"
        return text 
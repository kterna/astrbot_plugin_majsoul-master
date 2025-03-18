from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import os
import io
import random
import requests
from typing import Tuple, Optional, List, Dict, Any, Union
import logging

logger = logging.getLogger(__name__)

class ImageUtils:
    @staticmethod
    def create_background(width: int, height: int, bg_dir: Optional[str] = None) -> Image.Image:
        """创建或加载背景图片"""
        if bg_dir and os.path.exists(bg_dir):
            bg_files = [f for f in os.listdir(bg_dir) if f.endswith(('.jpg', '.png'))]
            if bg_files:
                bg_path = os.path.join(bg_dir, random.choice(bg_files))
                background = Image.open(bg_path)
                return background.resize((width, height))
        return Image.new('RGB', (width, height), (30, 30, 30))

    @staticmethod
    def get_font(size: int = 24, font_name: str = "simhei.ttf") -> ImageFont.FreeTypeFont:
        """获取字体
        
        Args:
            size: 字体大小
            font_name: 字体名称
            
        Returns:
            字体对象
        """
        try:
            # 尝试从系统字体目录加载
            system_font_dirs = [
                "C:/Windows/Fonts/",  # Windows
                "/usr/share/fonts/",  # Linux
                "/System/Library/Fonts/",  # macOS
                "./resources/fonts/"  # 本地资源目录
            ]
            
            for font_dir in system_font_dirs:
                font_path = os.path.join(font_dir, font_name)
                if os.path.exists(font_path):
                    return ImageFont.truetype(font_path, size)
            
            # 如果找不到指定字体，尝试其他常见字体
            fallback_fonts = ["simhei.ttf", "simsun.ttc", "msyh.ttc", "Arial.ttf"]
            for fallback in fallback_fonts:
                if fallback != font_name:  # 避免重复尝试
                    for font_dir in system_font_dirs:
                        font_path = os.path.join(font_dir, fallback)
                        if os.path.exists(font_path):
                            logger.warning(f"找不到字体 {font_name}，使用备用字体 {fallback}")
                            return ImageFont.truetype(font_path, size)
            
            # 最后尝试使用默认字体
            return ImageFont.load_default()
        except Exception as e:
            logger.error(f"加载字体失败: {e}")
            return ImageFont.load_default()

    @staticmethod
    def create_text_with_background(
        draw: ImageDraw.ImageDraw,
        text: str,
        position: Tuple[int, int],
        font: ImageFont.FreeTypeFont,
        text_color: Tuple[int, int, int],
        bg_color: Tuple[int, int, int, int],
        width: int,
        height: int
    ) -> None:
        """创建带背景的文字"""
        # 绘制文字背景
        x, y = position
        draw.rectangle([x, y, x + width, y + height], fill=bg_color)
        
        # 计算文字位置使其居中
        text_width = font.getlength(text) if hasattr(font, 'getlength') else font.getsize(text)[0]
        text_y = y + (height - font.size) // 2
        
        # 绘制文字
        draw.text((x + 10, text_y), text, font=font, fill=text_color)

    @staticmethod
    def image_to_bytes(image: Image.Image, format: str = 'PNG') -> bytes:
        """将PIL Image转换为字节流"""
        img_byte_array = io.BytesIO()
        image.save(img_byte_array, format=format)
        return img_byte_array.getvalue()
    
    @staticmethod
    def download_image(url: str) -> Optional[Image.Image]:
        """从URL下载图片
        
        Args:
            url: 图片URL
            
        Returns:
            下载的图片对象，下载失败则返回None
        """
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return Image.open(io.BytesIO(response.content))
        except Exception as e:
            logger.error(f"下载图片失败: {e}")
            return None
    
    @staticmethod
    def create_rounded_rectangle(
        draw: ImageDraw.ImageDraw,
        position: Tuple[int, int, int, int],
        radius: int,
        color: Tuple[int, int, int, int]
    ) -> None:
        """绘制圆角矩形
        
        Args:
            draw: ImageDraw对象
            position: 矩形位置 (x0, y0, x1, y1)
            radius: 圆角半径
            color: 填充颜色
        """
        x0, y0, x1, y1 = position
        
        # 绘制矩形主体
        draw.rectangle((x0 + radius, y0, x1 - radius, y1), fill=color)
        draw.rectangle((x0, y0 + radius, x1, y1 - radius), fill=color)
        
        # 绘制四个圆角
        draw.ellipse((x0, y0, x0 + 2 * radius, y0 + 2 * radius), fill=color)
        draw.ellipse((x1 - 2 * radius, y0, x1, y0 + 2 * radius), fill=color)
        draw.ellipse((x0, y1 - 2 * radius, x0 + 2 * radius, y1), fill=color)
        draw.ellipse((x1 - 2 * radius, y1 - 2 * radius, x1, y1), fill=color)
    
    @staticmethod
    def add_watermark(
        image: Image.Image,
        text: str,
        position: str = "bottom-right",
        opacity: float = 0.5,
        font_size: int = 20,
        color: Tuple[int, int, int] = (255, 255, 255)
    ) -> Image.Image:
        """添加水印
        
        Args:
            image: 原始图片
            text: 水印文字
            position: 水印位置，可选 "top-left", "top-right", "bottom-left", "bottom-right", "center"
            opacity: 不透明度，0.0-1.0
            font_size: 字体大小
            color: 文字颜色
            
        Returns:
            添加水印后的图片
        """
        # 创建一个透明图层
        watermark = Image.new('RGBA', image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(watermark)
        
        # 获取字体
        font = ImageUtils.get_font(font_size)
        
        # 计算文字大小
        text_width = font.getlength(text) if hasattr(font, 'getlength') else font.getsize(text)[0]
        text_height = font_size
        
        # 确定位置
        width, height = image.size
        padding = 10
        
        if position == "top-left":
            pos = (padding, padding)
        elif position == "top-right":
            pos = (width - text_width - padding, padding)
        elif position == "bottom-left":
            pos = (padding, height - text_height - padding)
        elif position == "bottom-right":
            pos = (width - text_width - padding, height - text_height - padding)
        else:  # center
            pos = ((width - text_width) // 2, (height - text_height) // 2)
        
        # 绘制文字
        draw.text(pos, text, font=font, fill=(*color, int(255 * opacity)))
        
        # 合并图层
        return Image.alpha_composite(image.convert('RGBA'), watermark).convert('RGB')
    
    @staticmethod
    def create_card_image(
        title: str,
        content: str,
        width: int = 600,
        height: int = 400,
        bg_color: Tuple[int, int, int] = (30, 30, 30),
        title_color: Tuple[int, int, int] = (255, 255, 255),
        content_color: Tuple[int, int, int] = (200, 200, 200)
    ) -> Image.Image:
        """创建卡片图片
        
        Args:
            title: 卡片标题
            content: 卡片内容
            width: 卡片宽度
            height: 卡片高度
            bg_color: 背景颜色
            title_color: 标题颜色
            content_color: 内容颜色
            
        Returns:
            卡片图片
        """
        # 创建背景
        image = Image.new('RGB', (width, height), bg_color)
        draw = ImageDraw.Draw(image)
        
        # 标题字体和内容字体
        title_font = ImageUtils.get_font(32)
        content_font = ImageUtils.get_font(20)
        
        # 绘制标题背景
        draw.rectangle((0, 0, width, 60), fill=(50, 50, 50))
        
        # 绘制标题
        draw.text((20, 10), title, font=title_font, fill=title_color)
        
        # 绘制内容
        # 处理多行文本
        lines = []
        current_line = ""
        for word in content.split():
            test_line = current_line + " " + word if current_line else word
            test_width = content_font.getlength(test_line) if hasattr(content_font, 'getlength') else content_font.getsize(test_line)[0]
            
            if test_width <= width - 40:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
        
        # 绘制内容行
        y = 80
        for line in lines:
            draw.text((20, y), line, font=content_font, fill=content_color)
            y += 30
        
        return image 
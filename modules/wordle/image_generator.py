import os
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, List, Tuple, Optional, Any

class MahjongImageGenerator:
    """麻将图像生成器"""
    
    # 定义状态对应的颜色
    STATUS_COLORS = {
        "correct": (76, 175, 80),  # 绿色 - 正确
        "exists": (255, 193, 7),   # 黄色 - 存在但位置不对
        "wrong": (158, 158, 158)   # 灰色 - 不存在
    }
    
    def __init__(self, resources_dir: str, max_attempts: int = 6):
        """初始化图像生成器
        
        Args:
            resources_dir: 资源目录路径
            max_attempts: 最大猜测次数，默认为6
        """
        self.resources_dir = resources_dir
        self.tile_size = (60, 80)  # 麻将牌大小
        self.tile_spacing = 5      # 麻将牌间距
        self.margin = 20           # 边距
        self.tile_cache = {}       # 缓存已加载的麻将牌图像
        self.max_attempts = max_attempts  # 最大猜测次数
        
    def get_tile_image(self, tile_code: str) -> Image.Image:
        """获取麻将牌图像
        
        Args:
            tile_code: 麻将牌代码，如 "1m", "3p" 等
            
        Returns:
            麻将牌图像
        """
        if tile_code in self.tile_cache:
            return self.tile_cache[tile_code].copy()
        
        # 解析牌代码
        number = tile_code[0]
        tile_type = tile_code[1]
        
        # 映射到文件名
        file_mapping = {
            "m": {
                "1": "Man1.png", "2": "Man2.png", "3": "Man3.png",
                "4": "Man4.png", "5": "Man5.png", "6": "Man6.png",
                "7": "Man7.png", "8": "Man8.png", "9": "Man9.png"
            },
            "p": {
                "1": "Pin1.png", "2": "Pin2.png", "3": "Pin3.png",
                "4": "Pin4.png", "5": "Pin5.png", "6": "Pin6.png",
                "7": "Pin7.png", "8": "Pin8.png", "9": "Pin9.png"
            },
            "s": {
                "1": "Sou1.png", "2": "Sou2.png", "3": "Sou3.png",
                "4": "Sou4.png", "5": "Sou5.png", "6": "Sou6.png",
                "7": "Sou7.png", "8": "Sou8.png", "9": "Sou9.png"
            },
            "z": {
                "1": "Ton.png", "2": "Nan.png", "3": "Shaa.png",
                "4": "Pei.png", "5": "Haku.png", "6": "Hatsu.png",
                "7": "Chun.png"
            }
        }
        
        tile_filename = file_mapping.get(tile_type, {}).get(number)
        
        if not tile_filename:
            # 如果找不到对应的牌，使用空白牌
            tile_filename = "Blank.png"
        
        png_path = os.path.join(self.resources_dir, tile_filename)

        try:
            tile_image = Image.open(png_path)
            if tile_image.size != self.tile_size:
                tile_image = tile_image.resize(self.tile_size, Image.Resampling.LANCZOS)
            if tile_image.mode != 'RGBA': # Ensure RGBA for alpha compositing
                 tile_image = tile_image.convert('RGBA')
        except FileNotFoundError:
            # print(f"Tile image not found: {png_path}. Using a blank image.")
            # Attempt to load a generic Blank.png if the specific tile is missing
            try:
                blank_png_path = os.path.join(self.resources_dir, "Blank.png")
                tile_image = Image.open(blank_png_path)
                if tile_image.size != self.tile_size:
                    tile_image = tile_image.resize(self.tile_size, Image.Resampling.LANCZOS)
                if tile_image.mode != 'RGBA':
                    tile_image = tile_image.convert('RGBA')
            except Exception as e_blank:
                # print(f"Blank.png also not found or error loading it: {e_blank}. Creating a default blank.")
                tile_image = Image.new('RGBA', self.tile_size, (255, 255, 255, 0)) # Transparent blank
        except Exception as e:
            # print(f"Error loading tile image '{png_path}': {e}. Using a default blank image.")
            tile_image = Image.new('RGBA', self.tile_size, (255, 255, 255, 0))
            
        self.tile_cache[tile_code] = tile_image
        return tile_image.copy()
    
    def create_wordle_image(
        self, 
        guesses: List[Dict[str, Any]],
        round_wind: str,
        player_wind: str,
        han: int,
        fu: int
    ) -> Image.Image:
        """创建麻将Wordle图像
        
        Args:
            guesses: 用户猜测列表，每个猜测包含牌代码和状态
            round_wind: 场风
            player_wind: 自风
            han: 番数
            fu: 符数
            
        Returns:
            Wordle图像
        """
        # 计算最大牌数
        max_tiles = max([len(guess["tiles"]) for guess in guesses]) if guesses else 14
        
        # 始终使用最大猜测次数创建图像，而不是仅基于当前猜测数量
        rows_to_display = self.max_attempts
        
        # 计算图像尺寸
        image_width = self.margin * 2 + max_tiles * (self.tile_size[0] + self.tile_spacing)
        image_height = self.margin * 2 + rows_to_display * (self.tile_size[1] + self.tile_spacing)
        
        # 创建基础图像
        image = Image.new('RGB', (image_width, image_height), (240, 240, 240))
        draw = ImageDraw.Draw(image)
        
        # 添加场风、自风、番、符信息
        info_font = ImageFont.truetype("simhei.ttf", 20) if os.path.exists("C:/Windows/Fonts/simhei.ttf") else ImageFont.load_default()
        info_text = f"场风: {round_wind} 自风: {player_wind} 番: {han} 符: {fu}"
        draw.text((image_width - 240, 10), info_text, fill=(0, 0, 0), font=info_font)
        
        # 绘制所有行（包括空行）
        for i in range(rows_to_display):
            y = self.margin + i * (self.tile_size[1] + self.tile_spacing)
            
            # 如果这行有猜测数据
            if i < len(guesses):
                guess = guesses[i]
                
                for j, tile_info in enumerate(guess["tiles"]):
                    x = self.margin + j * (self.tile_size[0] + self.tile_spacing)
                    
                    # 获取牌图像
                    tile_image = self.get_tile_image(tile_info["code"])
                    
                    # 创建状态背景
                    status = tile_info.get("status", "wrong")
                    status_color = self.STATUS_COLORS.get(status, self.STATUS_COLORS["wrong"])
                    
                    # 创建状态背景
                    status_bg = Image.new('RGBA', tile_image.size, (*status_color, 128))
                    
                    # 合并图像
                    if status != "wrong":  # 不为错误状态时显示状态背景
                        # 使用带有透明度的状态背景
                        tile_with_status = Image.alpha_composite(
                            tile_image.convert('RGBA'), 
                            Image.new('RGBA', tile_image.size, (*status_color, 80))
                        )
                        image.paste(tile_with_status, (x, y), tile_with_status)
                    else:
                        # 直接粘贴原始图像
                        image.paste(tile_image, (x, y), tile_image)
            else:
                # 绘制空行，用于未来的猜测
                for j in range(max_tiles):
                    x = self.margin + j * (self.tile_size[0] + self.tile_spacing)
                    # 创建空白牌位的边框
                    draw.rectangle(
                        [(x, y), (x + self.tile_size[0], y + self.tile_size[1])],
                        outline=(200, 200, 200),
                        width=1
                    )
        
        return image
    
    def save_image(self, image: Image.Image, output_path: str) -> str:
        """保存图像
        
        Args:
            image: 图像对象
            output_path: 输出路径
            
        Returns:
            完整的保存路径
        """
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        image.save(output_path,'PNG')
        return output_path 
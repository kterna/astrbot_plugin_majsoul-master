from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api.message_components import Plain, Image
from .modules.query.extended_query import MajsoulQuery
from .modules.gacha.gacha import GachaSystem
from .modules.analysis.mahjong_utils import PaiAnalyzer
import os
import re

@register("astrbot_plugin_majsoul", "AstrBot Team", "雀魂多功能插件", "1.3.0")
class MajsoulPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.ensure_directories()
        
        # 初始化配置
        self.data_dir = os.path.join(os.path.dirname(__file__), "data")
        self.config = config or {}
        
        # 初始化各个系统
        self.api_url = "https://5-data.amae-koromo.com/api/v2"  # 使用新的API地址
        self.default_pool = self.config.get('default_pool', 'standard')
        
        # 初始化模块
        self.query = MajsoulQuery(self.api_url)
        self.gacha = GachaSystem(self.data_dir)
        self.pai_analyzer = PaiAnalyzer()

    def ensure_directories(self):
        """确保必要的目录存在"""
        directories = ['data', 'logs', 'cache']
        for dir_name in directories:
            dir_path = os.path.join(os.path.dirname(__file__), dir_name)
            os.makedirs(dir_path, exist_ok=True)

    @filter.command("雀魂帮助")
    async def handle_help(self, event: AstrMessageEvent):
        """显示雀魂插件帮助信息"""
        help_text = """雀魂多功能插件使用帮助：
        
【查询功能】
（仅支持金之间以上场次）
基础查询：
- /雀魂查询 昵称：查询玩家四麻金之间南场战绩
- /雀魂查询 昵称 金东：查询玩家四麻金之间东场战绩
- /雀魂查询 昵称 三人金南：查询玩家三麻金之间南场战绩

场次说明：
- 人数：三人/不填（默认四人）
- 等级：金/玉/王座
- 场次：东/南（默认南）

示例：
四麻场：
- /雀魂查询 昵称 金南：金之间南场
- /雀魂查询 昵称 玉东：玉之间东场
- /雀魂查询 昵称 王座南：王座之间南场

三麻场：
- /雀魂查询 昵称 三人金南：三人金之间南场
- /雀魂查询 昵称 三人玉东：三人玉之间东场
- /雀魂查询 昵称 三人王座南：三人王座之间南场

详细查询：
- /雀魂详细 昵称：查询玩家四麻金之间南场详细数据
- /雀魂详细 昵称 金南：查询玩家四麻金之间南场详细数据


牌谱查询：
- /雀魂牌谱 昵称：查询玩家最近的四麻对局记录
- /雀魂牌谱 昵称 三人：查询玩家最近的三麻对局记录

【抽卡功能】
- 雀魂十连：模拟雀魂十连抽卡
- 切换雀魂卡池 <卡池名>：切换抽卡卡池
- 查看雀魂卡池：查看当前可用卡池

【牌理分析】
- 牌理 <手牌>：分析麻将手牌（如：牌理 1112345678999m）
"""
        yield event.plain_result(help_text)

    @filter.command("雀魂查询", alias=['雀魂信息'])
    async def handle_query(self, event: AstrMessageEvent):
        """查询雀魂玩家信息"""
        try:
            # 去除命令前缀
            args = re.sub(r'^(雀魂查询|雀魂信息)\s*', '', event.message_str.strip())
            if not args:
                yield event.plain_result("请输入要查询的昵称")
                return
                
            # 解析参数并执行查询
            nickname, room_level, is_south, mode = self.query.parse_command_args(args)
            success, result = await self.query.query_stats(nickname, mode, room_level, is_south)
            yield event.plain_result(result if success else f"查询失败: {result}")
        except Exception as e:
            yield event.plain_result(f"处理查询命令时出错: {str(e)}")

    @filter.command("雀魂牌谱")
    async def handle_records(self, event: AstrMessageEvent):
        """查询雀魂玩家最近对局记录"""
        try:
            # 去除命令前缀
            args = re.sub(r'^雀魂牌谱\s*', '', event.message_str.strip())
            if not args:
                yield event.plain_result("请输入要查询的昵称")
                return
                
            # 解析参数并执行查询
            nickname, room_level, is_south, mode = self.query.parse_command_args(args)
            success, result = await self.query.query_records(nickname, mode, DEFAULT_LIMIT, is_south)
            yield event.plain_result(result if success else f"查询失败: {result}")
        except Exception as e:
            yield event.plain_result(f"处理查询命令时出错: {str(e)}")

    @filter.command("雀魂详细", alias=["详细雀魂"])
    async def handle_detailed_query(self, event: AstrMessageEvent):
        """查询雀魂玩家详细战绩"""
        try:
            # 去除命令前缀
            args = re.sub(r'^(雀魂详细|详细雀魂)\s*', '', event.message_str.strip())
            if not args:
                yield event.plain_result("请输入要查询的雀魂昵称")
                return
            
            # 解析命令参数
            nickname, room_level, is_south, mode = self.query.parse_command_args(args)
            
            # 获取详细统计
            success, stats_result = await self.query.query_extended_stats(nickname, mode, room_level, is_south)
            if not success:
                yield event.plain_result(f"查询失败: {stats_result}")
                return
                
            # 获取最近对局记录
            success, records_result = await self.query.query_records(nickname, mode, 3)
            if not success:
                yield event.plain_result(stats_result + "\n\n无法获取最近对局记录")
                return
                
            # 合并结果
            yield event.plain_result(f"{stats_result}\n\n{records_result}")
            
        except Exception as e:
            yield event.plain_result(f"处理查询命令时出错: {str(e)}")

    @filter.command("雀魂十连")
    async def handle_gacha(self, event: AstrMessageEvent):
        """模拟雀魂十连抽卡"""
        pool = self.gacha.pools.get(self.gacha.current_pool)
        if not pool:
            pool = self.gacha.pools["standard"]
        
        result = self.gacha.gacha_ten(pool)
        image_path = self.gacha.presenter.create_gacha_result_image(result)
        
        if image_path and os.path.exists(image_path):
            message_result = event.make_result()
            message_result.chain = [Plain(f"【{pool.display_name}】十连抽卡结果:"), Image(file=image_path)]
            yield message_result
        else:
            yield event.plain_result("抽卡结果生成失败")

    @filter.command("切换雀魂卡池")
    async def handle_switch_pool(self, event: AstrMessageEvent):
        """切换雀魂抽卡卡池"""
        parts = event.message_str.split(maxsplit=1)
        if len(parts) < 2:
            yield event.plain_result("请指定要切换的卡池名称")
            return
        
        pool_name = parts[1].strip()
        success, message = self.gacha.switch_pool(pool_name)
        yield event.plain_result(message)

    @filter.command("查看雀魂卡池")
    async def handle_view_pools(self, event: AstrMessageEvent):
        """查看当前可用的雀魂卡池"""
        pool = self.gacha.pools.get(self.gacha.current_pool)
        if not pool:
            pool = self.gacha.pools["standard"]
        
        text = self.gacha.presenter.format_all_pools(pool.name)
        yield event.plain_result(text)

    @filter.command("牌理")
    async def mahjong_analysis(self, event: AstrMessageEvent):
        """处理牌理分析命令"""
        parts = event.message_str.split(maxsplit=1)
        if len(parts) < 2:
            yield event.plain_result("请输入要分析的手牌，例如：牌理 123456789m123p1s")
            return
        
        hand_str = parts[1].strip()
        analysis_result = self.pai_analyzer.analyze_hand(hand_str)
        yield event.plain_result(analysis_result)

    @filter.command(["雀魂开", "雀魂关"])
    async def handle_plugin_switch(self, event: AstrMessageEvent):
        """处理插件开关命令"""
        message = event.message_str.strip()
        group_id = str(event.message_obj.group_id)
        
        enabled = message == "雀魂开"
        await self.set_group_enabled(group_id, enabled)
        
        yield event.plain_result(f"已{'启用' if enabled else '禁用'}雀魂插件")
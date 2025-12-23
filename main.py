from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api.message_components import Plain, Image
from astrbot.api import logger
from .modules.query.extended_query import MajsoulQuery
from .modules.gacha.gacha import GachaSystem
from .modules.analysis.mahjong_utils import PaiAnalyzer
from .modules.wordle.mahjong_wordle import MahjongWordle
from .modules.wordle.multi_mahjong_wordle import MultiMahjongWordle
from .utils.message_formatter import MahjongFormatter
from .utils.generate_hands import generate_valid_hands
from .modules.wordle.data_loader import MahjongDataLoader

import os
import re

@register("astrbot_plugin_majsoul", "kterna", "雀魂多功能插件", "1.5.1")
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
        
        # 初始化麻将Wordle游戏
        self.wordle = MahjongWordle(os.path.dirname(__file__))
        
        # 初始化多牌谱麻将Wordle游戏
        self.multi_wordle = MultiMahjongWordle(os.path.dirname(__file__))

    def ensure_directories(self):
        """确保必要的目录存在"""
        directories = ['data', 'logs', 'cache', 'cache/wordle']
        for dir_name in directories:
            dir_path = os.path.join(os.path.dirname(__file__), dir_name)
            os.makedirs(dir_path, exist_ok=True)

    async def set_group_enabled(self, group_id: str, enabled: bool):
        """设置群组的插件启用状态"""
        if 'group_enabled' not in self.config:
            self.config['group_enabled'] = {}
        self.config['group_enabled'][group_id] = enabled
        logger.info(f"雀魂插件状态更新：群组 {group_id} -> {enabled}")

    @filter.command("雀魂帮助")
    async def handle_help(self, event: AstrMessageEvent):
        """显示雀魂插件帮助信息"""
        help_text = """雀魂多功能插件使用帮助：
        
【查询功能】
（仅支持金之间以上场次）
基础查询：
- 雀魂查询 昵称：查询玩家四麻金之间南场战绩
- 雀魂查询 昵称 金东：查询玩家四麻金之间东场战绩
- 雀魂查询 昵称 三人金南：查询玩家三麻金之间南场战绩

场次说明：
- 人数：三人/不填（默认四人）
- 等级：金/玉/王座
- 场次：东/南（默认南）

示例：
四麻场：
- 雀魂查询 昵称 金南：金之间南场
- 雀魂查询 昵称 玉东：玉之间东场
- 雀魂查询 昵称 王座南：王座之间南场

三麻场：
- 雀魂查询 昵称 三人金南：三人金之间南场
- 雀魂查询 昵称 三人玉东：三人玉之间东场
- 雀魂查询 昵称 三人王座南：三人王座之间南场

详细查询：
- 雀魂详细 昵称：查询玩家四麻金之间南场详细数据
- 雀魂详细 昵称 金南：查询玩家四麻金之间南场详细数据


牌谱查询：
- 雀魂牌谱 昵称：查询玩家最近的四麻对局记录
- 雀魂牌谱 昵称 三人：查询玩家最近的三麻对局记录

【抽卡功能】
- 雀魂十连：模拟雀魂十连抽卡
- 切换雀魂卡池 <卡池名>：切换抽卡卡池
- 查看雀魂卡池：查看当前可用卡池

【牌理分析】
- 牌理 <手牌>：分析麻将手牌（如：牌理 1112345678999m）

【雀魂猜牌游戏】
- 雀魂猜牌：开始新的麻将猜牌游戏
- 雀魂猜牌 <手牌>：猜测当前游戏的手牌

【雀魂多牌谱猜牌游戏】
- 雀魂我要猜一万个：开始新的多牌谱麻将猜牌游戏（4个牌谱，10次猜测机会）
- 雀魂我要猜一万个 <手牌>：猜测当前多牌谱游戏的手牌

【生成题库】
- 雀魂猜牌题库刷新 <数量>：生成指定数量的新题库

【使用说明】
万:m
筒:p
索:s
字:z 1234567对应东南西北白发中
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
        # 使用新的结构化分析
        analysis_result = self.pai_analyzer.analyze_hand(hand_str)
        # 使用格式化工具将结构化结果转换为可读文本
        formatted_result = MahjongFormatter.format_hand_analysis(analysis_result.to_dict())
        yield event.plain_result(formatted_result)

    @filter.command("雀魂猜牌")
    async def handle_wordle(self, event: AstrMessageEvent):
        """处理麻将Wordle游戏命令"""
        user_id = str(event.message_obj.sender.user_id)
        # 获取群聊ID，私聊时为None
        group_id = str(event.message_obj.group_id) if event.message_obj.group_id else None
        
        # 提取参数
        message = event.message_str.strip()
        args = re.sub(r'^雀魂猜牌\s*', '', message)
        
        # 判断是开始游戏还是猜测
        if args == "雀魂猜牌" or not args:
            # 开始新游戏
            try:
                self.wordle.start_game(user_id, group_id)
                
                # 生成初始图像
                image_path = self.wordle.generate_image(user_id, group_id)
                
                # 获取游戏信息
                game_info = self.wordle.get_game_info(user_id, group_id)
                
                message_result = event.make_result()
                message_result.chain = [
                    Plain(f"雀魂猜牌游戏开始！\n"
                          f"场风: {game_info['round_wind']} 自风: {game_info['player_wind']} "
                          f"番: {game_info['han']} 符: {game_info['fu']}\n"
                          f"请输入您的猜测，格式如: 雀魂猜牌 123456789m123p11s"),
                    Image(file=image_path)
                ]
                yield message_result
            except Exception as e:
                yield event.plain_result(f"开始游戏失败: {str(e)}")
                
        else:
            # 用户猜测
            try:
                # 检查猜测
                result = self.wordle.check_guess(user_id, args, group_id)
                game_state = result["game_state"]
                
                # 生成图像
                image_path = self.wordle.generate_image(user_id, group_id)
                
                # 构造结果消息
                message_result = event.make_result()
                
                if game_state["completed"]:
                    if game_state["win"]:
                        result_text = "恭喜你猜对了！\n"
                    else:
                        result_text = f"游戏结束，你没有猜对。正确答案是: {game_state['hand_data']['hand']}\n"
                        
                    # 显示役种信息
                    yaku_names = [y.get("chinese_name", y.get("name", "")) for y in game_state["hand_data"].get("yaku", [])]
                    result_text += f"役种: {', '.join(yaku_names)}\n"
                    
                    # 游戏结束时清理游戏状态
                    game_key = self.wordle._get_game_key(user_id, group_id)
                    if game_key in self.wordle.current_games:
                        del self.wordle.current_games[game_key]
                else:
                    result_text = f"你还有{game_state['max_attempts'] - len(game_state['guesses'])}次猜测机会\n"
                
                message_result.chain = [
                    Plain(result_text),
                    Image(file=image_path)
                ]
                yield message_result
                
            except Exception as e:
                yield event.plain_result(f"处理猜测失败: {str(e)}")

    @filter.command("雀魂猜牌题库刷新")
    async def handle_refresh_wordle_library(self, event: AstrMessageEvent):
        """刷新雀魂猜牌题库"""
        try:
            args = re.sub(r'^雀魂猜牌题库刷新\s*', '', event.message_str.strip())
            number = int(args) if args else 100
            
            # 获取插件根目录
            plugin_root = os.path.dirname(os.path.abspath(__file__))
            data_dir = os.path.join(plugin_root, "data")
            output_dir = os.path.join(data_dir, "generated_hands")
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, "valid_hands.json")
            
            result = generate_valid_hands(
                limit=number,
                output_file=output_file
            )

            # 重新初始化数据加载器，使用正确的数据目录路径
            self.wordle.data_loader = MahjongDataLoader(data_dir)
            
            yield event.plain_result(result)
        except Exception as e:
            yield event.plain_result(f"生成题库失败: {str(e)}")
            
    @filter.command("雀魂开", alias=["雀魂关"])
    async def handle_plugin_switch(self, event: AstrMessageEvent):
        """处理插件开关命令"""
        message = event.message_str.strip()
        group_id = str(event.message_obj.group_id)
        
        enabled = message == "雀魂开"
        await self.set_group_enabled(group_id, enabled)
        
        yield event.plain_result(f"已{'启用' if enabled else '禁用'}雀魂插件")

    @filter.command("雀魂我要猜一万个")
    async def handle_multi_wordle(self, event: AstrMessageEvent):
        """处理多牌谱麻将Wordle游戏命令"""
        user_id = str(event.message_obj.sender.user_id)
        # 获取群聊ID，私聊时为None
        group_id = str(event.message_obj.group_id) if event.message_obj.group_id else None
        
        # 提取参数
        message = event.message_str.strip()
        args = re.sub(r'^雀魂我要猜一万个\s*', '', message)
        
        # 判断是开始游戏还是猜测
        if args == "雀魂我要猜一万个" or not args:
            # 开始新游戏
            try:
                self.multi_wordle.start_games(user_id, group_id)
                
                # 生成初始复合图像
                image_path = self.multi_wordle.generate_composite_image(user_id, group_id)
                
                # 获取多牌谱游戏信息
                game_info = self.multi_wordle.get_multi_game_info(user_id, group_id)
                game_infos = game_info["game_infos"]
                
                # 构建提示文本
                hints = []
                for i, info in enumerate(game_infos):
                    # 为每个牌谱添加序号和信息
                    hint = f"牌谱{i+1}: 场风: {info.get('round_wind', '?')} 自风: {info.get('player_wind', '?')} 番: {info.get('han', '?')} 符: {info.get('fu', '?')}"
                    hints.append(hint)
                
                hint_text = "\n".join(hints)
                
                message_result = event.make_result()
                message_result.chain = [
                    Plain(f"雀魂多牌谱猜牌游戏开始！\n"
                          f"本局游戏包含4个牌谱，共有10次猜测机会。\n"
                          f"{hint_text}\n"
                          f"请输入要猜测的手牌："),
                    Image(file=image_path)
                ]
                yield message_result
                
            except Exception as e:
                yield event.plain_result(f"开始游戏失败: {e}")
        else:
            # 猜测
            try:
                # 检查猜测
                result = self.multi_wordle.check_guess(user_id, args, group_id)
                
                # 生成更新后的图像
                image_path = self.multi_wordle.generate_composite_image(user_id, group_id)
                
                # 构建结果文本
                win_count = result["win_count"]
                total_games = result["total_games"]
                current_attempt = result["current_attempt"]
                max_attempts = result["max_attempts"]
                
                if result["completed"]:
                    if win_count == total_games:
                        result_text = f"恭喜你猜对了全部{total_games}个牌谱！总共用了{current_attempt}次猜测。"
                    else:
                        result_text = f"游戏结束！你猜对了{win_count}/{total_games}个牌谱，总共用了{current_attempt}次猜测。"
                else:
                    result_text = f"当前猜测: {current_attempt}/{max_attempts}\n已猜对: {win_count}/{total_games}个牌谱"
                
                message_result = event.make_result()
                message_result.chain = [
                    Plain(f"{result_text}"),
                    Image(file=image_path)
                ]
                yield message_result
                
            except Exception as e:
                yield event.plain_result(f"猜测失败: {e}")
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, StarTools, register
from astrbot.api.message_components import Plain, Image
from astrbot.api import logger, llm_tool
from .modules.query.extended_query import DEFAULT_LIMIT, MajsoulQuery
from .modules.gacha.gacha import GachaSystem
from .modules.analysis.mahjong_utils import PaiAnalyzer
from .modules.wordle.mahjong_wordle import MahjongWordle
from .modules.wordle.multi_mahjong_wordle import MultiMahjongWordle
from .modules.review import PaipuAnalysisService, ReviewService
from .modules.webui import MajsoulWebUIApi
from .modules.resource_pack import ResourcePackManager, format_bytes
from .utils.message_formatter import MahjongFormatter
from .utils.generate_hands import generate_valid_hands
from .modules.wordle.data_loader import MahjongDataLoader

import os
import re
import json
import asyncio
from pathlib import Path

@register("astrbot_plugin_majsoul", "kterna", "雀魂多功能插件", "1.6.0")
class MajsoulPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.plugin_root = Path(__file__).resolve().parent
        self.plugin_data_dir = StarTools.get_data_dir("astrbot_plugin_majsoul")
        self.ensure_directories()
        
        # 初始化配置
        self.data_dir = os.path.join(os.path.dirname(__file__), "data")
        self.config = config or {}
        self.resource_pack = ResourcePackManager(self.plugin_data_dir, self.config)
        
        # 初始化各个系统
        self.api_url = "https://5-data.amae-koromo.com/api/v2"  # 使用新的API地址
        self.default_pool = self.config.get('default_pool', 'standard')
        
        # 初始化模块
        self.query = MajsoulQuery(self.api_url)
        self.gacha = GachaSystem(self.data_dir, resources_dir=str(self.resource_pack.resources_dir))
        self.pai_analyzer = PaiAnalyzer()
        
        # 初始化麻将Wordle游戏
        self.wordle = MahjongWordle(os.path.dirname(__file__))

        # 初始化多牌谱麻将Wordle游戏
        self.multi_wordle = MultiMahjongWordle(os.path.dirname(__file__))

        # 加载账号绑定数据
        self.bindings_file = str(self.plugin_data_dir / "bindings.json")
        self.bindings = self._load_bindings()

        # 牌谱拉取服务
        self.review_service = ReviewService(
            plugin_root=self.plugin_root,
            data_root=self.plugin_data_dir,
            config=self.config,
        )
        self.paipu_analysis = PaipuAnalysisService(self.review_service)
        self.webui_api = MajsoulWebUIApi(self)
        self.webui_api.register(context)

    def ensure_directories(self):
        """确保必要的目录存在"""
        plugin_dirs = [
            "data",
            "logs",
            "cache",
            "cache/wordle",
        ]
        for dir_name in plugin_dirs:
            dir_path = self.plugin_root / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)

        data_dirs = [
            self.plugin_data_dir,
            self.plugin_data_dir / "review",
            self.plugin_data_dir / "review" / "paipu",
            self.plugin_data_dir / "cache",
            self.plugin_data_dir / "cache" / "resource_pack",
        ]
        for path in data_dirs:
            path.mkdir(parents=True, exist_ok=True)

    async def set_group_enabled(self, group_id: str, enabled: bool):
        """设置群组的插件启用状态"""
        if 'group_enabled' not in self.config:
            self.config['group_enabled'] = {}
        self.config['group_enabled'][group_id] = enabled
        logger.info(f"雀魂插件状态更新：群组 {group_id} -> {enabled}")

    def _load_bindings(self) -> dict:
        """加载账号绑定数据"""
        if os.path.exists(self.bindings_file):
            try:
                with open(self.bindings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载绑定数据失败: {e}")
        return {}

    def _save_bindings(self):
        """保存账号绑定数据"""
        try:
            with open(self.bindings_file, 'w', encoding='utf-8') as f:
                json.dump(self.bindings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存绑定数据失败: {e}")

    def _get_bound_nickname(self, user_id: str) -> str:
        """获取用户绑定的昵称"""
        return self.bindings.get(user_id, {}).get("nickname")

    def _is_room_param(self, arg: str) -> bool:
        """Check if arg is a room/mode param (e.g. 金东, 三人玉之间, 三人)."""
        normalized = arg.strip().replace(" ", "")
        normalized = normalized.replace("麻将", "")
        normalized = normalized.replace("模式", "")
        normalized = normalized.replace("房", "")
        normalized = normalized.replace("场次", "")
        normalized = normalized.replace("之间", "")
        normalized = normalized.replace("场", "")

        room_patterns = [
            r'^(三人|四人)?(金|玉|王座?|王)(东|南)?$',
            r'^(三人|四人)$',  # default to 金南
        ]
        return any(re.match(p, normalized) for p in room_patterns)

    def _prepend_bound_nickname(self, args: str, user_id: str) -> str:
        """如果args只有房间参数，则在前面添加绑定的昵称"""
        bound_nickname = self._get_bound_nickname(user_id)
        if not bound_nickname:
            return args

        parts = args.strip().split()
        # 如果第一个参数看起来是房间参数，则在前面添加绑定的昵称
        if parts and self._is_room_param(parts[0]):
            return f"{bound_nickname} {args}"
        return args

    @filter.command("雀魂帮助")
    async def handle_help(self, event: AstrMessageEvent):
        """显示雀魂插件帮助信息"""
        help_text = """雀魂多功能插件使用帮助：

【账号绑定】
- 雀魂绑定 昵称：绑定雀魂账号（绑定后查询可省略昵称）
- 雀魂解绑：解除账号绑定
- 雀魂绑定查询：查看当前绑定信息

【查询功能】
（仅支持金之间以上场次）
（绑定账号后可省略昵称直接查询）
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
- 雀魂牌谱 昵称：查询玩家最近的四麻对局记录（默认5条）
- 雀魂牌谱 昵称 10：查询玩家最近10条四麻对局记录
- 雀魂牌谱 昵称 三人：查询玩家最近的三麻对局记录
- 雀魂牌谱 昵称 三人 10：查询玩家最近10条三麻对局记录

【牌谱拉取】
- 雀魂review <牌谱URL或paipu_id>：拉取并缓存原始牌谱（raw.json）

【账号池管理（管理员）】
- 雀魂登录国服 <用户名> <密码>：添加或更新国服账号
- 雀魂登录列表：查看当前账号池
- 雀魂登录删除 <序号|uid|用户名>：删除账号池账号

【抽卡功能】
- 雀魂十连：模拟雀魂十连抽卡
- 切换雀魂卡池 <卡池名>：切换抽卡卡池
- 查看雀魂卡池：查看当前可用卡池

【资源管理（管理员）】
- 雀魂资源状态：查看外置资源包安装状态
- 雀魂资源下载：下载抽卡图片资源到插件数据目录
- 雀魂资源更新：强制重新下载抽卡图片资源
- 雀魂资源删除：删除本地外置资源包

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

    @filter.command("雀魂查询")
    async def handle_query(self, event: AstrMessageEvent):
        """查询雀魂玩家信息"""
        try:
            user_id = str(event.message_obj.sender.user_id)
            # 去除命令前缀
            args = re.sub(r'^(雀魂查询|雀魂信息)\s*', '', event.message_str.strip())

            # 如果没有输入参数，尝试使用绑定的昵称
            if not args:
                bound_nickname = self._get_bound_nickname(user_id)
                if bound_nickname:
                    args = bound_nickname
                else:
                    yield event.plain_result("请输入要查询的昵称，或使用 雀魂绑定 昵称 绑定账号")
                    return
            else:
                # 尝试在房间参数前添加绑定昵称
                args = self._prepend_bound_nickname(args, user_id)

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
            user_id = str(event.message_obj.sender.user_id)
            # 去除命令前缀
            args = re.sub(r'^雀魂牌谱\s*', '', event.message_str.strip())

            # 如果没有输入参数，尝试使用绑定的昵称
            if not args:
                bound_nickname = self._get_bound_nickname(user_id)
                if bound_nickname:
                    args = bound_nickname
                else:
                    yield event.plain_result("请输入要查询的昵称，或使用 雀魂绑定 昵称 绑定账号")
                    return
            else:
                # 尝试在房间参数前添加绑定昵称
                args = self._prepend_bound_nickname(args, user_id)

            # 解析数量参数（最后一个纯数字参数）
            parts = args.strip().split()
            limit = DEFAULT_LIMIT
            if parts and parts[-1].isdigit():
                limit = min(int(parts[-1]), 30)  # 最多30条
                args = ' '.join(parts[:-1])

            # 解析参数并执行查询
            nickname, room_level, is_south, mode = self.query.parse_command_args(args)
            success, result = await self.query.query_records(nickname, mode, limit, room_level, is_south)
            yield event.plain_result(result if success else f"查询失败: {result}")
        except Exception as e:
            yield event.plain_result(f"处理查询命令时出错: {str(e)}")

    @filter.command("雀魂review")
    async def handle_review(self, event: AstrMessageEvent):
        """拉取并缓存雀魂原始牌谱"""
        args = re.sub(r'^雀魂review\s*', '', event.message_str.strip())
        if not args:
            yield event.plain_result("请输入牌谱URL或paipu_id，例如：雀魂review https://game.maj-soul.com/1/?paipu=xxxx")
            return

        yield event.plain_result("正在拉取牌谱，请稍候...")
        try:
            success, message, _images = await asyncio.wait_for(
                self.review_service.do_review(args),
                timeout=180,
            )
        except asyncio.TimeoutError:
            yield event.plain_result("牌谱拉取超时（超过180秒），请稍后重试")
            return
        except Exception as exc:
            logger.error(f"[majsoul-review] do_review执行异常: {exc}", exc_info=True)
            yield event.plain_result(f"牌谱拉取失败: {exc}")
            return

        if not success:
            yield event.plain_result(message)
            return

        yield event.plain_result(message)

    @staticmethod
    def _tool_json(payload: dict) -> str:
        return json.dumps(payload, ensure_ascii=False, indent=2)

    async def _run_paipu_analysis_tool(self, coro, tool_name: str) -> str:
        try:
            return self._tool_json(
                await asyncio.wait_for(
                    coro,
                    timeout=180,
                )
            )
        except asyncio.TimeoutError:
            return self._tool_json(
                {
                    "status": "error",
                    "message": "牌谱分析超时（超过180秒），请稍后重试",
                }
            )
        except Exception as exc:
            logger.error(f"[majsoul-review] {tool_name}执行异常: {exc}", exc_info=True)
            return self._tool_json(
                {
                    "status": "error",
                    "message": f"牌谱分析失败: {exc}",
                }
            )

    @llm_tool("majsoul_fetch_paipu_json")
    async def majsoul_fetch_paipu_json(
        self,
        event: AstrMessageEvent,
        paipu_url_or_id: str,
    ) -> str:
        """将雀魂牌谱链接或 paipu_id 拉取为原始牌谱 JSON 并保存到插件缓存目录。

        当用户希望把 `雀魂牌谱` 命令返回的原始牌谱链接保存成 json 文件时，调用这个工具。

        Args:
            paipu_url_or_id(string): 必填。雀魂牌谱链接，或链接中的 paipu_id。

        """
        try:
            success, message, fetch_result = await asyncio.wait_for(
                self.review_service.fetch_raw_paipu(paipu_url_or_id),
                timeout=180,
            )
        except asyncio.TimeoutError:
            return json.dumps(
                {
                    "status": "error",
                    "message": "牌谱拉取超时（超过180秒），请稍后重试",
                },
                ensure_ascii=False,
                indent=2,
            )
        except Exception as exc:
            logger.error(f"[majsoul-review] majsoul_fetch_paipu_json执行异常: {exc}", exc_info=True)
            return json.dumps(
                {
                    "status": "error",
                    "message": f"牌谱拉取失败: {exc}",
                },
                ensure_ascii=False,
                indent=2,
            )

        if not success or fetch_result is None:
            return json.dumps(
                {
                    "status": "error",
                    "message": message,
                },
                ensure_ascii=False,
                indent=2,
            )

        return json.dumps(
            {
                "status": "success",
                "game_id": fetch_result.game_id,
                "raw_json_path": fetch_result.raw_path_relative,
                "cache_hit": fetch_result.cache_hit,
            },
            ensure_ascii=False,
            indent=2,
        )

    @llm_tool("majsoul_list_paipu_rounds")
    async def majsoul_list_paipu_rounds(
        self,
        event: AstrMessageEvent,
        paipu_source: str,
    ) -> str:
        """列出牌谱中的所有局，并返回每局的基础结果摘要。

        Args:
            paipu_source(string): 必填。仓库相对 raw.json 路径，或雀魂牌谱链接，或 paipu_id。

        """
        return await self._run_paipu_analysis_tool(
            self.paipu_analysis.list_rounds(paipu_source),
            "majsoul_list_paipu_rounds",
        )

    @llm_tool("majsoul_get_round_result")
    async def majsoul_get_round_result(
        self,
        event: AstrMessageEvent,
        paipu_source: str,
        round_selector: str,
    ) -> str:
        """读取指定局的输赢、点数和役种信息。

        Args:
            paipu_source(string): 必填。仓库相对 raw.json 路径，或雀魂牌谱链接，或 paipu_id。
            round_selector(string): 必填。局索引字符串，如 `8`，或局标签，如 `南2一本场`。

        """
        return await self._run_paipu_analysis_tool(
            self.paipu_analysis.get_round_result(paipu_source, round_selector),
            "majsoul_get_round_result",
        )

    @llm_tool("majsoul_get_round_turn_state")
    async def majsoul_get_round_turn_state(
        self,
        event: AstrMessageEvent,
        paipu_source: str,
        round_selector: str,
        turn_mode: str,
        turn_number: int,
        seat: int = -1,
        phase: str = "discard",
    ) -> str:
        """读取指定局在某个巡目节点的各家手牌快照，并可附带指定 seat 的摸打轨迹。

        Args:
            paipu_source(string): 必填。仓库相对 raw.json 路径，或雀魂牌谱链接，或 paipu_id。
            round_selector(string): 必填。局索引字符串，如 `8`，或局标签，如 `南2一本场`。
            turn_mode(string): 必填。`global` 表示全桌第 N 巡快照，`seat_local` 表示指定 seat 的本地第 N 次摸打节点。
            turn_number(number): 必填。第几巡或第几次摸打，必须大于 0。
            seat(number): 可选。`seat_local` 模式下必填；`global` 模式下可填用于附带该 seat 的摸打轨迹，不需要时传 -1。
            phase(string): 可选。仅 `seat_local` 模式有效，支持 `draw` 或 `discard`，默认 `discard`。

        """
        return await self._run_paipu_analysis_tool(
            self.paipu_analysis.get_round_turn_state(
                paipu_source,
                round_selector,
                turn_mode,
                turn_number,
                seat=seat,
                phase=phase,
            ),
            "majsoul_get_round_turn_state",
        )

    @llm_tool("majsoul_get_player_round_trace")
    async def majsoul_get_player_round_trace(
        self,
        event: AstrMessageEvent,
        paipu_source: str,
        round_selector: str,
        player_selector: str,
    ) -> str:
        """读取指定玩家在某一局中的完整进张手牌轨迹。

        Args:
            paipu_source(string): 必填。仓库相对 raw.json 路径，或雀魂牌谱链接，或 paipu_id。
            round_selector(string): 必填。局索引字符串，如 `8`，或局标签，如 `南2一本场`。
            player_selector(string): 必填。玩家 seat 字符串，如 `0`，或该局中的精确昵称。

        """
        return await self._run_paipu_analysis_tool(
            self.paipu_analysis.get_player_round_trace(
                paipu_source,
                round_selector,
                player_selector,
            ),
            "majsoul_get_player_round_trace",
        )

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("雀魂登录国服")
    async def handle_login_cn(self, event: AstrMessageEvent):
        """管理员添加/更新国服账号"""
        args = re.sub(r'^雀魂登录国服\s*', '', event.message_str.strip())
        parts = args.split(maxsplit=1)
        if len(parts) != 2:
            yield event.plain_result("请输入账号密码：雀魂登录国服 <用户名> <密码>")
            return

        yield event.plain_result("正在登录并验证账号，请稍候...")
        try:
            success, message = await asyncio.wait_for(
                self.review_service.add_cn_account(parts[0].strip(), parts[1].strip()),
                timeout=180,
            )
        except asyncio.TimeoutError:
            yield event.plain_result("登录超时（超过180秒），请检查网络后重试")
            return
        except Exception as exc:
            logger.error(f"[majsoul-review] add_cn_account执行异常: {exc}", exc_info=True)
            yield event.plain_result(f"登录失败: {exc}")
            return

        yield event.plain_result(message)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("雀魂登录列表")
    async def handle_login_list(self, event: AstrMessageEvent):
        """管理员查看账号池"""
        text = await self.review_service.list_accounts()
        yield event.plain_result(text)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("雀魂登录删除")
    async def handle_login_remove(self, event: AstrMessageEvent):
        """管理员删除账号池账号"""
        args = re.sub(r'^雀魂登录删除\s*', '', event.message_str.strip())
        if not args:
            yield event.plain_result("请输入要删除的目标：序号/uid/用户名")
            return

        success, message = await self.review_service.remove_account(args.strip())
        yield event.plain_result(message)

    def _format_resource_status(self) -> str:
        status = self.resource_pack.status()
        installed_text = "已安装" if status.installed else "未安装"
        return (
            "【雀魂资源状态】\n"
            f"状态：{installed_text}\n"
            f"版本：{status.version or '未知'}\n"
            f"文件数：{status.file_count}\n"
            f"大小：{format_bytes(status.total_size_bytes)}\n"
            f"目录：{status.resources_dir}\n"
            f"下载源：{self.resource_pack.pack_url}"
        )

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("雀魂资源状态")
    async def handle_resource_status(self, event: AstrMessageEvent):
        """管理员查看外置资源包状态"""
        yield event.plain_result(self._format_resource_status())

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("雀魂资源下载")
    async def handle_resource_download(self, event: AstrMessageEvent):
        """管理员下载外置资源包"""
        yield event.plain_result("正在下载雀魂外置资源包，请稍候...")
        try:
            await asyncio.to_thread(self.resource_pack.install, False)
            self.gacha.reload_resources()
        except Exception as exc:
            logger.error(f"[majsoul-resource] 下载资源包失败: {exc}", exc_info=True)
            yield event.plain_result(f"资源下载失败: {exc}")
            return
        yield event.plain_result("资源下载完成。\n" + self._format_resource_status())

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("雀魂资源更新")
    async def handle_resource_update(self, event: AstrMessageEvent):
        """管理员强制更新外置资源包"""
        yield event.plain_result("正在更新雀魂外置资源包，请稍候...")
        try:
            await asyncio.to_thread(self.resource_pack.install, True)
            self.gacha.reload_resources()
        except Exception as exc:
            logger.error(f"[majsoul-resource] 更新资源包失败: {exc}", exc_info=True)
            yield event.plain_result(f"资源更新失败: {exc}")
            return
        yield event.plain_result("资源更新完成。\n" + self._format_resource_status())

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("雀魂资源删除")
    async def handle_resource_delete(self, event: AstrMessageEvent):
        """管理员删除本地外置资源包"""
        await asyncio.to_thread(self.resource_pack.delete)
        self.gacha.reload_resources()
        yield event.plain_result("已删除本地雀魂外置资源包。")

    @filter.command("雀魂详细")
    async def handle_detailed_query(self, event: AstrMessageEvent):
        """查询雀魂玩家详细战绩"""
        try:
            user_id = str(event.message_obj.sender.user_id)
            # 去除命令前缀
            args = re.sub(r'^(雀魂详细|详细雀魂)\s*', '', event.message_str.strip())

            # 如果没有输入参数，尝试使用绑定的昵称
            if not args:
                bound_nickname = self._get_bound_nickname(user_id)
                if bound_nickname:
                    args = bound_nickname
                else:
                    yield event.plain_result("请输入要查询的雀魂昵称，或使用 雀魂绑定 昵称 绑定账号")
                    return
            else:
                # 尝试在房间参数前添加绑定昵称
                args = self._prepend_bound_nickname(args, user_id)

            # 解析命令参数
            nickname, room_level, is_south, mode = self.query.parse_command_args(args)
            
            # 获取详细统计
            success, stats_result = await self.query.query_extended_stats(nickname, mode, room_level, is_south)
            if not success:
                yield event.plain_result(f"查询失败: {stats_result}")
                return
                
            # 获取最近对局记录
            success, records_result = await self.query.query_records(nickname, mode, 3, room_level, is_south)
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
        if not self.gacha.resources_ready():
            yield event.plain_result("抽卡资源未安装，请管理员先执行：雀魂资源下载")
            return

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
            
    @filter.command("雀魂开", alias={"雀魂关"})
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

    @filter.command("雀魂绑定")
    async def handle_bind(self, event: AstrMessageEvent):
        """绑定雀魂账号"""
        user_id = str(event.message_obj.sender.user_id)
        args = re.sub(r'^雀魂绑定\s*', '', event.message_str.strip())

        if not args:
            yield event.plain_result("请输入要绑定的雀魂昵称，例如：雀魂绑定 你的昵称")
            return

        nickname = args.split()[0]

        # 验证昵称是否存在（通过查询API）
        success, result = await self.query.search_player(nickname)
        if not success:
            yield event.plain_result(f"绑定失败：{result}")
            return

        # 保存绑定
        self.bindings[user_id] = {"nickname": nickname}
        self._save_bindings()

        yield event.plain_result(f"绑定成功！已将您的账号绑定到雀魂昵称：{nickname}\n现在使用雀魂查询/雀魂牌谱/雀魂详细时可以不用输入昵称了。")

    @filter.command("雀魂解绑")
    async def handle_unbind(self, event: AstrMessageEvent):
        """解绑雀魂账号"""
        user_id = str(event.message_obj.sender.user_id)

        if user_id not in self.bindings:
            yield event.plain_result("您还没有绑定雀魂账号。")
            return

        nickname = self.bindings[user_id].get("nickname", "未知")
        del self.bindings[user_id]
        self._save_bindings()

        yield event.plain_result(f"解绑成功！已解除与雀魂昵称 {nickname} 的绑定。")

    @filter.command("雀魂绑定查询")
    async def handle_binding_info(self, event: AstrMessageEvent):
        """查询当前绑定信息"""
        user_id = str(event.message_obj.sender.user_id)

        if user_id not in self.bindings:
            yield event.plain_result("您还没有绑定雀魂账号。使用 雀魂绑定 昵称 来绑定。")
            return

        nickname = self.bindings[user_id].get("nickname", "未知")
        yield event.plain_result(f"您当前绑定的雀魂昵称：{nickname}")

"""
雀魂段位转换模块
"""

from enum import Enum
from typing import Optional

# 段位名称
PLAYER_RANKS = "初士杰豪圣魂"
PLAYER_RANKS_DETAIL = ["初心", "雀士", "雀杰", "雀豪", "雀圣", "魂天"]

# 魂天等级标记
LEVEL_KONTEN = 7

# 魂天最大分数
LEVEL_MAX_POINT_KONTEN = 2000

# 各段位最大分数
LEVEL_MAX_POINTS = [
    20,    # 初心一
    80,    # 初心二
    200,   # 初心三
    600,   # 雀士一
    800,   # 雀士二
    1000,  # 雀士三
    1200,  # 雀杰一
    1400,  # 雀杰二
    2000,  # 雀杰三
    2800,  # 雀豪一
    3200,  # 雀豪二
    3600,  # 雀豪三
    4000,  # 雀圣一
    6000,  # 雀圣二
    9000,  # 雀圣三
]

# 各段位降级惩罚点数 (四人南)
LEVEL_PENALTY = [
    0, 0, 0,        # 初心
    20, 40, 60,     # 雀士
    80, 100, 120,   # 雀杰
    165, 180, 195,  # 雀豪
    210, 225, 240,  # 雀圣
    255,            # 魂天
]

# 三人南降级惩罚点数
LEVEL_PENALTY_3 = [
    0, 0, 0,
    20, 40, 60,
    80, 100, 120,
    165, 190, 215,
    240, 265, 290,
    320,
]

# 四人东降级惩罚点数
LEVEL_PENALTY_E = [
    0, 0, 0,
    10, 20, 30,
    40, 50, 60,
    80, 90, 100,
    110, 120, 130,
    140,
]

# 三人东降级惩罚点数
LEVEL_PENALTY_E_3 = [
    0, 0, 0,
    10, 20, 30,
    40, 50, 60,
    80, 95, 110,
    125, 140, 160,
    175,
]


class GameMode(Enum):
    """游戏模式枚举"""
    王座 = 16
    玉 = 12
    金 = 9
    王东 = 15
    玉东 = 11
    金东 = 8
    三金 = 22
    三玉 = 24
    三王座 = 26
    三金东 = 21
    三玉东 = 23
    三王东 = 25


# 游戏模式对应的降级惩罚表
MODE_PENALTY = {
    GameMode.金: LEVEL_PENALTY,
    GameMode.玉: LEVEL_PENALTY,
    GameMode.王座: LEVEL_PENALTY,
    GameMode.金东: LEVEL_PENALTY_E,
    GameMode.玉东: LEVEL_PENALTY_E,
    GameMode.王东: LEVEL_PENALTY_E,
    GameMode.三金: LEVEL_PENALTY_3,
    GameMode.三玉: LEVEL_PENALTY_3,
    GameMode.三王座: LEVEL_PENALTY_3,
    GameMode.三金东: LEVEL_PENALTY_E_3,
    GameMode.三玉东: LEVEL_PENALTY_E_3,
    GameMode.三王东: LEVEL_PENALTY_E_3,
}


class MajsoulLevel:
    """雀魂段位类

    用于解析和处理雀魂的段位信息。

    levelId 编码格式: [num_player_id][major_rank][minor_rank]
    - num_player_id: 玩家模式 (1=四人, 2=三人)
    - major_rank: 主段位 (1=初心, 2=雀士, 3=雀杰, 4=雀豪, 5=雀圣, 6+=魂天)
    - minor_rank: 次段位 (1=一, 2=二, 3=三)

    示例:
    - 10101 = 四人初心一
    - 10302 = 四人雀杰二
    - 20401 = 三人雀豪一
    """

    def __init__(self, level_id: int):
        """初始化段位对象

        Args:
            level_id: 段位ID，格式为 num_player_id * 10000 + major_rank * 100 + minor_rank
        """
        real_id = level_id % 10000

        self.id = level_id
        self.major_rank = real_id // 100      # 主段位
        self.minor_rank = real_id % 100       # 次段位
        self.num_player_id = level_id // 10000  # 玩家模式

    def to_level_id(self) -> int:
        """转换回段位ID"""
        return self.num_player_id * 10000 + self.major_rank * 100 + self.minor_rank

    def is_konten(self) -> bool:
        """是否为魂天段位"""
        return self.major_rank >= LEVEL_KONTEN - 1

    def get_label(self) -> str:
        """获取段位基础名称 (如: 雀士, 雀杰)"""
        index = LEVEL_KONTEN - 2 if self.is_konten() else self.major_rank - 1
        if 0 <= index < len(PLAYER_RANKS_DETAIL):
            return PLAYER_RANKS_DETAIL[index]
        return "未知"

    def get_tag(self) -> str:
        """获取完整段位标签 (如: 雀士一, 雀杰三, 魂天)

        Returns:
            str: 完整的段位名称
        """
        label = self.get_label()

        # 魂天特殊处理
        if self.is_konten():
            if self.minor_rank == LEVEL_KONTEN - 1:
                return label
            # 魂天等级
            return f"{label}{self.minor_rank}"

        # 普通段位
        minor_names = {1: "一", 2: "二", 3: "三"}
        minor_name = minor_names.get(self.minor_rank, str(self.minor_rank))
        return f"{label}{minor_name}"

    def is_same_major_rank(self, other: "MajsoulLevel") -> bool:
        """判断是否同一主段位"""
        return self.major_rank == other.major_rank

    def is_same(self, other: "MajsoulLevel") -> bool:
        """判断是否相同段位"""
        if self.is_konten() and other.is_konten():
            if self.major_rank == LEVEL_KONTEN - 1 or other.major_rank == LEVEL_KONTEN - 1:
                return True
            return (self.major_rank == other.major_rank and
                    self.minor_rank == other.minor_rank)
        return (self.major_rank == other.major_rank and
                self.minor_rank == other.minor_rank)

    def get_max_point(self) -> int:
        """获取当前段位的最大分数"""
        if self.is_konten():
            if self.minor_rank == 20:
                return 0  # 魂天20无上限
            return LEVEL_MAX_POINT_KONTEN

        index = (self.major_rank - 1) * 3 + self.minor_rank - 1
        if 0 <= index < len(LEVEL_MAX_POINTS):
            return LEVEL_MAX_POINTS[index]
        return 0

    def get_penalty_point(self, mode: GameMode) -> int:
        """获取降级惩罚点数

        Args:
            mode: 游戏模式

        Returns:
            int: 降级惩罚点数
        """
        if self.is_konten():
            return 0

        penalty_list = MODE_PENALTY.get(mode, LEVEL_PENALTY)
        index = (self.major_rank - 1) * 3 + self.minor_rank - 1
        if 0 <= index < len(penalty_list):
            return penalty_list[index]
        return 0

    def get_starting_point(self) -> int:
        """获取初始分数 (升/降级后的起始分)"""
        if self.major_rank == 1:
            return 0
        return self.get_max_point() // 2

    def get_next_level(self) -> "MajsoulLevel":
        """获取下一个段位"""
        level = self.get_version_adjusted_level()
        major_rank = level.major_rank
        minor_rank = level.minor_rank + 1

        if minor_rank > 3 and not level.is_konten():
            major_rank += 1
            minor_rank = 1

        if major_rank == LEVEL_KONTEN - 1:
            major_rank = LEVEL_KONTEN

        return MajsoulLevel(level.num_player_id * 10000 + major_rank * 100 + minor_rank)

    def get_previous_level(self) -> "MajsoulLevel":
        """获取上一个段位"""
        if self.major_rank == 1 and self.minor_rank == 1:
            return self

        level = self.get_version_adjusted_level()
        major_rank = level.major_rank
        minor_rank = level.minor_rank - 1

        if minor_rank < 1:
            major_rank -= 1
            minor_rank = 3

        if major_rank == LEVEL_KONTEN - 1:
            major_rank = LEVEL_KONTEN - 2

        return MajsoulLevel(level.num_player_id * 10000 + major_rank * 100 + minor_rank)

    def get_adjusted_level(self, score: int) -> "MajsoulLevel":
        """根据分数获取调整后的段位

        Args:
            score: 当前分数

        Returns:
            MajsoulLevel: 调整后的段位对象
        """
        score = self.get_version_adjusted_score(score)
        level = self.get_version_adjusted_level()
        max_points = level.get_max_point()

        if max_points and score >= max_points:
            level = level.get_next_level()
        elif score < 0:
            if (not max_points or level.major_rank == 1 or
                (level.major_rank == 2 and level.minor_rank == 1)):
                pass  # 不降级
            else:
                level = level.get_previous_level()

        return level

    def get_version_adjusted_score(self, score: int) -> int:
        """获取版本调整后的分数"""
        if self.major_rank == LEVEL_KONTEN - 1:
            return (score // 100) * 10 + 200
        return score

    def get_version_adjusted_level(self) -> "MajsoulLevel":
        """获取版本调整后的段位"""
        if self.major_rank != LEVEL_KONTEN - 1:
            return self
        return MajsoulLevel(self.num_player_id * 10000 + LEVEL_KONTEN * 100 + 1)

    def get_score_display(self, score: int) -> str:
        """获取分数显示字符串"""
        score = self.get_version_adjusted_score(score)
        if self.is_konten():
            return f"{score / 100:.1f}"
        return str(score)

    def get_max_point_display(self) -> str:
        """获取最大分数显示字符串"""
        max_point = self.get_max_point()
        if self.is_konten():
            return f"{max_point / 100:.1f}"
        return str(max_point)

    def format_score(self, score: int) -> str:
        """格式化分数显示

        Args:
            score: 当前分数

        Returns:
            str: 格式化后的分数，如 "150/800"
        """
        score_display = self.get_score_display(score)
        max_point = self.get_max_point()
        if not max_point:
            return score_display
        return f"{score_display}/{self.get_max_point_display()}"

    def format_with_tag(self, score: int) -> str:
        """格式化段位和分数

        Args:
            score: 当前分数

        Returns:
            str: 格式化后的段位和分数，如 "雀士二 150/800"
        """
        level = self.get_adjusted_level(score)
        return f"{level.get_tag()} {self.format_score(score)}"

    def __repr__(self) -> str:
        return f"MajsoulLevel({self.id}, {self.get_tag()})"

    def __str__(self) -> str:
        return self.get_tag()


def level_id_to_tag(level_id: int) -> str:
    """便捷函数：将段位ID转换为段位标签

    Args:
        level_id: 段位ID

    Returns:
        str: 段位标签，如 "雀士二"
    """
    return MajsoulLevel(level_id).get_tag()


def level_id_to_display(level_id: int, score: int) -> str:
    """便捷函数：将段位ID和分数转换为完整显示

    Args:
        level_id: 段位ID
        score: 当前分数

    Returns:
        str: 完整显示，如 "雀士二 150/800"
    """
    return MajsoulLevel(level_id).format_with_tag(score)

URL_BASE = "https://game.maj-soul.com/"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/100.0.4896.88 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "If-Modified-Since": "0",
    "Referer": URL_BASE,
    "sec-ch-ua": "'Chromium';v='100', 'Google Chrome';v='100'",
    "sec-ch-ua-platform": "Windows",
}

ROOM_MODE_MAP = {
    1: {"name": "四人铜东", "is_3p": False, "room": "铜之间"},
    2: {"name": "四人铜南", "is_3p": False, "room": "铜之间"},
    3: {"name": "四人铜东", "is_3p": False, "room": "铜之间"},
    4: {"name": "四人银东", "is_3p": False, "room": "银之间"},
    5: {"name": "四人银东", "is_3p": False, "room": "银之间"},
    6: {"name": "四人银南", "is_3p": False, "room": "银之间"},
    7: {"name": "四人金东", "is_3p": False, "room": "金之间"},
    8: {"name": "四人金东", "is_3p": False, "room": "金之间"},
    9: {"name": "四人金南", "is_3p": False, "room": "金之间"},
    10: {"name": "四人玉东", "is_3p": False, "room": "玉之间"},
    11: {"name": "四人玉东", "is_3p": False, "room": "玉之间"},
    12: {"name": "四人玉南", "is_3p": False, "room": "玉之间"},
    13: {"name": "乱斗之间", "is_3p": False, "room": "乱斗之间"},
    14: {"name": "乱斗之间", "is_3p": False, "room": "乱斗之间"},
    15: {"name": "四人王座东", "is_3p": False, "room": "王座间"},
    16: {"name": "四人王座南", "is_3p": False, "room": "王座间"},
    17: {"name": "三人铜东", "is_3p": True, "room": "铜之间"},
    18: {"name": "三人铜南", "is_3p": True, "room": "铜之间"},
    19: {"name": "三人银东", "is_3p": True, "room": "银之间"},
    20: {"name": "三人银南", "is_3p": True, "room": "银之间"},
    21: {"name": "三人金东", "is_3p": True, "room": "金之间"},
    22: {"name": "三人金南", "is_3p": True, "room": "金之间"},
    23: {"name": "三人玉东", "is_3p": True, "room": "玉之间"},
    24: {"name": "三人玉南", "is_3p": True, "room": "玉之间"},
    25: {"name": "三人王座东", "is_3p": True, "room": "王座间"},
    26: {"name": "三人王座南", "is_3p": True, "room": "王座间"},
}


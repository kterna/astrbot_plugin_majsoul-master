from typing import List, Union

import betterproto
from msgspec import Struct

from .lib.lq import RecordGame


class InflightRequest(Struct):
    method_name: str
    msg_obj: type[betterproto.Message]


class MajsoulVersionInfo(Struct):
    version: str
    force_version: str
    code: str


class ResItem(Struct):
    prefix: str


class MajsoulResInfo(Struct):
    res: dict[str, ResItem]


class ReqRes(Struct):
    requestType: str
    responseType: str


class MajsoulLiqiItem(Struct):
    fields: dict[str, dict] | None = None
    methods: dict[str, ReqRes] | None = None


class MajsoulLiqiNested(Struct):
    nested: dict[str, MajsoulLiqiItem]


class MajsoulLiqiProto(Struct):
    nested: dict[str, MajsoulLiqiNested]


class MajsoulRegionUrl(Struct):
    id: str
    url: str


class MajsoulConfigIp(Struct):
    name: str
    gateways: List[MajsoulRegionUrl]


class MajsoulConfig(Struct):
    ip: List[MajsoulConfigIp]


class MajsoulDecodedMessage(Struct):
    msg_type: int
    req_index: int
    method_name: str
    payload: betterproto.Message


class MjsLogItem(Struct):
    name: str
    data: betterproto.Message


class MjsLog(Struct):
    head: RecordGame
    data: List[MjsLogItem]


class AccountInfo(Struct):
    uid: str
    username: str
    password: str
    token: str = ""
    nickname: str = ""
    last_status: str = "unknown"
    last_error: str = ""
    updated_at: int = 0

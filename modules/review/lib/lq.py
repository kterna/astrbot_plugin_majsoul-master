"""Fallback stubs for missing Majsoul protocol definitions.

This plugin references generated protocol classes under modules/review/lib/lq.py.
The upstream repository currently omits those files, so we provide minimal
placeholders to keep the plugin importable. Any runtime use of these stubs
will raise a descriptive error so users know how to fix the installation.
"""

from __future__ import annotations

__missing__ = True


class MissingProtoError(RuntimeError):
    """Raised when protocol definitions are missing."""


def _raise() -> None:
    raise MissingProtoError(
        "Majsoul protocol definitions are missing (modules/review/lib/lq.py). "
        "This repository is incomplete. Please obtain the original lib/lq "
        "files from the plugin author or a complete release before using review features."
    )


class ProtoStub:
    """Base stub that raises if unknown attributes are accessed."""

    def __init__(self, *args, **kwargs):
        self.__dict__.update(kwargs)

    def __getattr__(self, name):
        _raise()


class Wrapper(ProtoStub):
    def parse(self, *args, **kwargs):
        _raise()


class GameDetailRecords(ProtoStub):
    def parse(self, *args, **kwargs):
        _raise()


class ResLogin(ProtoStub):
    pass


class ResOauth2Check(ProtoStub):
    pass


class ResCommon(ProtoStub):
    pass


class ResGameRecord(ProtoStub):
    pass


class RecordGame(ProtoStub):
    """Placeholder type used by model.py when protocol definitions are missing."""


class HuleInfo(ProtoStub):
    pass


class RecordAnGangAddGang(ProtoStub):
    pass


class RecordBaBei(ProtoStub):
    pass


class RecordChiPengGang(ProtoStub):
    pass


class RecordDealTile(ProtoStub):
    pass


class RecordDiscardTile(ProtoStub):
    pass


class RecordHule(ProtoStub):
    pass


class RecordLiuJu(ProtoStub):
    pass


class RecordNewRound(ProtoStub):
    pass


class RecordNoTile(ProtoStub):
    pass

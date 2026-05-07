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


class Wrapper:
    def __init__(self, *args, **kwargs):
        _raise()

    def parse(self, *args, **kwargs):
        _raise()


class GameDetailRecords:
    def __init__(self, *args, **kwargs):
        _raise()

    def parse(self, *args, **kwargs):
        _raise()


class ResLogin:
    def __init__(self, *args, **kwargs):
        _raise()


class ResOauth2Check:
    def __init__(self, *args, **kwargs):
        _raise()


class ResCommon:
    def __init__(self, *args, **kwargs):
        _raise()


class ResGameRecord:
    def __init__(self, *args, **kwargs):
        _raise()


class RecordGame:
    """Placeholder type used by model.py when protocol definitions are missing."""

    def __init__(self, *args, **kwargs):
        _raise()

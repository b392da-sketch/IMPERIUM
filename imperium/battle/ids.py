"""Layer 1: identifier records (contract 5.2).

Each identifier is a distinct frozen record holding one ASCII token. The
classes never interchange with each other, with ``str`` or with
quantities.
"""

import re
from dataclasses import dataclass

from .errors import InvalidValue

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,63}")


def valid_token(token):
    """True iff ``token`` is an exact ``str`` matching the 5.2 grammar."""
    return type(token) is str and TOKEN_PATTERN.fullmatch(token) is not None


def _check_token(token):
    if not valid_token(token):
        raise InvalidValue("T07", "token", "invalid identifier token")


@dataclass(frozen=True, slots=True)
class FormationId:
    token: str

    def __post_init__(self):
        _check_token(self.token)


@dataclass(frozen=True, slots=True)
class GroupId:
    token: str

    def __post_init__(self):
        _check_token(self.token)


@dataclass(frozen=True, slots=True)
class LotId:
    token: str

    def __post_init__(self):
        _check_token(self.token)


@dataclass(frozen=True, slots=True)
class EventRef:
    token: str

    def __post_init__(self):
        _check_token(self.token)


@dataclass(frozen=True, slots=True)
class FixtureId:
    token: str

    def __post_init__(self):
        _check_token(self.token)


ID_CLASSES = (FormationId, GroupId, LotId, EventRef, FixtureId)

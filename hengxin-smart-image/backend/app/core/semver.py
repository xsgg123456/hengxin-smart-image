"""Strict ASCII SemVer 2.0.0 for newly registered local publications."""
import re

_NUMBER = r'(?:0|[1-9][0-9]*)'
_PRERELEASE = rf'(?:{_NUMBER}|[0-9]*[A-Za-z-][0-9A-Za-z-]*)'
_SEMVER = re.compile(
    rf'{_NUMBER}\.{_NUMBER}\.{_NUMBER}'
    rf'(?:-{_PRERELEASE}(?:\.{_PRERELEASE})*)?'
    r'(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?'
)


def validate_semver(value: str) -> str:
    if not isinstance(value, str) or len(value) > 100 or not _SEMVER.fullmatch(value):
        raise ValueError('版本必须为不超过100字符的有效 ASCII SemVer 2.0.0')
    return value

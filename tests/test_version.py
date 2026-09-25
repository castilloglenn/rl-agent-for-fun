import re

from src.utils.version import code_version


def test_code_version_is_a_commit_or_unknown():
    version = code_version()
    assert version == "unknown" or re.fullmatch(
        r"[0-9a-f]{7,}(-dirty)?", version
    )

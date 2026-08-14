# tests/test_roundtrip_short.py
"""Encode -> detect -> decode must not raise for short whole strings.

The contract under test (issue #380): when a caller hands chardet a complete
short string, ``data.decode(result["encoding"])`` succeeds.  It is *not* a
fidelity guarantee --- a sibling codec may decode the bytes to different
text --- and it deliberately excludes fragments cut mid-character, where the
correct answer is an encoding that cannot decode the input and correctness
wins (see ``test_truncated_input.py``).

Three populations, all measured before these tests were written:

* ASCII-dominant strings ending in an accented letter --- the dangling-tail
  bait that made utf-8 win undecodably.  Guaranteed by the decode-safety
  flip in postprocess.
* Fully non-ASCII whole words in single-byte scripts --- naturally safe;
  their winners decode.
* Whole CJK strings at character boundaries --- naturally safe.
"""

from __future__ import annotations

import pytest

import chardet

# Population 1: ASCII stem + accented final letter (the issue-380 shape).
_ACCENT_FINAL = [
    ("windows-1252", "mamá"),
    ("windows-1252", "papa ané"),
    ("windows-1252", "cafe olé"),
    ("iso-8859-1", "mamá"),
    ("iso-8859-1", "the fox jumps ß"),
    ("windows-1250", "pan kůň"),
    ("iso-8859-2", "hello pané"),
    ("windows-1254", "pasha çabuş"),
    ("iso-8859-9", "hello efendı"),
    ("mac-roman", "voila déjà"),
    ("windows-1253", "hello κό"),
    ("iso-8859-7", "abc δώ"),
    ("windows-1251", "hello миря"),
    ("iso-8859-5", "abc покой"),
    ("koi8-r", "hello миря"),
    ("cp866", "hello мир"),
    ("windows-1255", "abc שלום"),
    ("windows-1256", "abc مرحبا"),
]

# Population 2: fully non-ASCII whole words, single-byte scripts.
_WHOLE_WORDS = [
    ("windows-1251", "привет мир"),
    ("windows-1251", "хорошо очень"),
    ("koi8-r", "молоко"),
    ("cp866", "вода"),
    ("iso-8859-7", "καλημέρα"),
    ("windows-1253", "ευχαριστώ πολύ"),
    ("windows-1255", "תודה רבה"),
    ("windows-1256", "صباح الخير"),
    ("cp874", "สวัสดี"),
    ("windows-1252", "café"),
    ("windows-1252", "niño año"),
    ("iso-8859-2", "žlutý kůň"),
    ("iso-8859-2", "čeština"),
]

# Population 3: whole CJK strings at character boundaries.
_CJK_WHOLE = [
    ("shift_jis", "こんにちは"),
    ("cp932", "ありがとう"),
    ("euc-jp", "こんにちは"),
    ("euc-kr", "안녕하세요"),
    ("cp949", "감사합니다"),
    ("big5", "早安你好"),
    ("gb2312", "早安你好"),
    ("gbk", "谢谢你们"),
    ("gb18030", "谢谢你们"),
]

_ALL = _ACCENT_FINAL + _WHOLE_WORDS + _CJK_WHOLE


@pytest.mark.parametrize(
    ("encoding", "text"), _ALL, ids=[f"{e}-{t[:8]}" for e, t in _ALL]
)
def test_short_string_roundtrip_decodes(encoding: str, text: str) -> None:
    """detect() on a complete short string returns an encoding that decodes it."""
    data = text.encode(encoding)
    assert 3 <= len(data) <= 40, "test string outside the short-input range"
    result = chardet.detect(data)
    assert result["encoding"] is not None, f"no detection for {data!r}"
    decoded = data.decode(result["encoding"])  # must not raise
    assert decoded


def test_roundtrip_fidelity_when_detection_is_exact() -> None:
    """When the detected codec maps the bytes identically, text survives."""
    data = "mamá".encode("iso-8859-1")
    result = chardet.detect(data)
    assert data.decode(result["encoding"]) == "mamá"

from typing import Optional

try:
    from typing import TypedDict
except ImportError:
    # TypedDict was introduced in Python 3.8.
    #
    # TODO: Remove this block when dropping support for Python 3.7.
    TypedDict = object


class ResultDict(TypedDict):
    encoding: Optional[str]
    confidence: float
    language: Optional[str]

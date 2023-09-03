from typing import Optional, TypedDict


class ResultDict(TypedDict):
    encoding: Optional[str]
    confidence: float
    language: Optional[str]

from typing import TypedDict


class CodingStateMachineDict(TypedDict, total=False):
    class_table: tuple[int, ...]
    class_factor: int
    state_table: tuple[int, ...]
    char_len_table: tuple[int, ...]
    name: str
    language: str  # Optional key

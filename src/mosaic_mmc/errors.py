"""Typed refusals. A refusal is not a claim that external state was inspected."""
from __future__ import annotations

class MMCError(ValueError):
    def __init__(self, code: str, path: str = "$", detail: str = "") -> None:
        self.code, self.path, self.detail = code, path, detail
        super().__init__(f"{code} at {path}: {detail}")

    def record(self) -> dict:
        return {"code": self.code, "path": self.path, "detail": self.detail}


def require(condition: bool, code: str, path: str = "$", detail: str = "") -> None:
    if not condition:
        raise MMCError(code, path, detail)

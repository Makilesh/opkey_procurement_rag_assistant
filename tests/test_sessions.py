from typing import Any

import pytest

from core.config import settings
from core.sessions import SessionStore


class FakeRedis:
    """Minimal in-memory stand-in for the redis.asyncio client methods we use."""

    def __init__(self) -> None:
        self.lists: dict[str, list[str]] = {}
        self.hashes: dict[str, dict[str, str]] = {}

    async def ping(self) -> bool:
        return True

    async def exists(self, key: str) -> int:
        return int(key in self.lists or key in self.hashes)

    async def rpush(self, key: str, value: str) -> int:
        self.lists.setdefault(key, []).append(value)
        return len(self.lists[key])

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        items = self.lists.get(key, [])
        end = len(items) if end == -1 else end + 1 if end >= 0 else len(items) + end + 1
        if start < 0:
            start = max(0, len(items) + start)
        return items[start:end]

    async def hset(self, key: str, mapping: dict[str, str]) -> int:
        self.hashes.setdefault(key, {}).update(mapping)
        return len(mapping)

    async def hsetnx(self, key: str, field: str, value: str) -> int:
        h = self.hashes.setdefault(key, {})
        if field in h:
            return 0
        h[field] = value
        return 1

    async def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            removed += int(self.lists.pop(key, None) is not None)
            removed += int(self.hashes.pop(key, None) is not None)
        return removed

    async def llen(self, key: str) -> int:
        return len(self.lists.get(key, []))

    async def hgetall(self, key: str) -> dict[str, str]:
        return dict(self.hashes.get(key, {}))

    async def scan_iter(self, match: str = "*", count: int = 100) -> Any:
        import fnmatch

        for key in list(self.lists) + [k for k in self.hashes if k not in self.lists]:
            if fnmatch.fnmatch(key, match):
                yield key


def make_store() -> SessionStore:
    return SessionStore(FakeRedis())  # type: ignore[arg-type]


def turn(role: str, content: str, **extra: Any) -> dict[str, Any]:
    return {"role": role, "content": content, "sources": [], **extra}


@pytest.mark.asyncio
async def test_append_and_full_history() -> None:
    store = make_store()
    await store.append_turn("s1", turn("user", "what is a purchase order?"))
    await store.append_turn("s1", turn("assistant", "A purchase order is..."))
    history = await store.history("s1")
    assert history is not None
    assert [t["role"] for t in history] == ["user", "assistant"]
    assert all("ts" in t for t in history)


@pytest.mark.asyncio
async def test_unknown_session_history_is_none() -> None:
    store = make_store()
    assert await store.history("nope") is None


@pytest.mark.asyncio
async def test_window_caps_turn_count() -> None:
    store = make_store()
    for i in range(settings.history_window_turns + 4):
        await store.append_turn("s1", turn("user", f"message {i}"))
    window = await store.window("s1")
    assert len(window) == settings.history_window_turns
    assert window[-1]["content"] == f"message {settings.history_window_turns + 3}"


@pytest.mark.asyncio
async def test_window_caps_token_budget() -> None:
    store = make_store()
    huge = "x" * (settings.history_token_budget * 4)  # ~budget tokens on its own
    await store.append_turn("s1", turn("user", huge))
    await store.append_turn("s1", turn("user", huge))
    await store.append_turn("s1", turn("user", "recent short message"))
    window = await store.window("s1")
    # newest turn always kept; older huge turns must be dropped by the budget
    assert window[-1]["content"] == "recent short message"
    assert len(window) < 3


@pytest.mark.asyncio
async def test_delete_then_gone() -> None:
    store = make_store()
    await store.append_turn("s1", turn("user", "hello"))
    assert await store.delete("s1") is True
    assert await store.history("s1") is None
    assert await store.delete("s1") is False

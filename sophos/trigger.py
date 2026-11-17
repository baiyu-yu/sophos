"""触发器配置管理。

概率触发模型：
  - 私聊：始终触发
  - 群聊被 @：触发（可配置关闭）
  - 群聊命中正则：触发（WebUI「设置」或 .trigger regex 配置）
  - 群聊含关键词：base_rate + max(匹配 boost)
  - 群聊普通消息：base_rate
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

# 正则编译缓存：patterns 不变时复用已编译对象。
_regex_cache: tuple[tuple[str, ...], list[re.Pattern[str]]] | None = None


def compile_regexes(patterns: list[str]) -> list[re.Pattern[str]]:
    """编译正则列表；非法表达式抛 re.error。"""
    return [re.compile(pattern) for pattern in patterns]


def match_regex(text: str, patterns: list[str]) -> str | None:
    """返回第一条命中的正则（原字符串），未命中返回 None。"""
    global _regex_cache  # noqa: PLW0603
    if not patterns:
        return None
    key = tuple(patterns)
    if _regex_cache is None or _regex_cache[0] != key:
        compiled: list[re.Pattern[str]] = []
        for pattern in patterns:
            try:
                compiled.append(re.compile(pattern))
            except re.error as exc:
                logger.warning("忽略非法的触发正则 %r: %s", pattern, exc)
        _regex_cache = (key, compiled)
    for pattern in _regex_cache[1]:
        if pattern.search(text):
            return pattern.pattern
    return None


def invalidate_regex_cache() -> None:
    global _regex_cache  # noqa: PLW0603
    _regex_cache = None


@dataclass
class Keyword:
    word: str
    boost: float


@dataclass
class TriggerConfig:
    base_rate: float = 0.05
    at_always: bool = True
    keywords: list[Keyword] = field(default_factory=list)

    def to_keywords_json(self) -> str:
        return json.dumps(
            [{"word": k.word, "boost": k.boost} for k in self.keywords],
            ensure_ascii=False,
        )

    @staticmethod
    def parse_keywords(raw: Any) -> list[Keyword]:
        if isinstance(raw, str):
            raw = json.loads(raw)
        if not isinstance(raw, list):
            return []
        return [Keyword(word=e["word"], boost=e["boost"]) for e in raw if "word" in e]


# ── 缓存 ─────────────────────────────────────────────────────

_cached: TriggerConfig | None = None


def invalidate() -> None:
    """清除缓存，下次 load 时重新从 DB 读取。"""
    global _cached  # noqa: PLW0603
    _cached = None


async def load(pool: asyncpg.Pool) -> TriggerConfig:
    """加载配置（带缓存）。"""
    global _cached  # noqa: PLW0603
    if _cached is not None:
        return _cached
    row = await pool.fetchrow("SELECT base_rate, at_always, keywords FROM trigger_config WHERE id = 1")
    if row is None:
        _cached = TriggerConfig()
    else:
        _cached = TriggerConfig(
            base_rate=row["base_rate"],
            at_always=row["at_always"],
            keywords=TriggerConfig.parse_keywords(row["keywords"]),
        )
    return _cached


async def set_base_rate(pool: asyncpg.Pool, rate: float) -> None:
    await pool.execute(
        "UPDATE trigger_config SET base_rate = $1, updated_at = now() WHERE id = 1",
        rate,
    )
    invalidate()


async def set_at_always(pool: asyncpg.Pool, value: bool) -> None:
    await pool.execute(
        "UPDATE trigger_config SET at_always = $1, updated_at = now() WHERE id = 1",
        value,
    )
    invalidate()


async def add_keyword(pool: asyncpg.Pool, word: str, boost: float) -> None:
    """添加或更新关键词。"""
    cfg = await load(pool)
    kws = [k for k in cfg.keywords if k.word != word]
    kws.append(Keyword(word=word, boost=boost))
    cfg.keywords = kws
    await pool.execute(
        "UPDATE trigger_config SET keywords = $1::jsonb, updated_at = now() WHERE id = 1",
        cfg.to_keywords_json(),
    )
    invalidate()


async def remove_keyword(pool: asyncpg.Pool, word: str) -> bool:
    """删除关键词。返回是否找到并删除。"""
    cfg = await load(pool)
    before = len(cfg.keywords)
    kws = [k for k in cfg.keywords if k.word != word]
    if len(kws) == before:
        return False
    cfg.keywords = kws
    await pool.execute(
        "UPDATE trigger_config SET keywords = $1::jsonb, updated_at = now() WHERE id = 1",
        cfg.to_keywords_json(),
    )
    invalidate()
    return True

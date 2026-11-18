"""识别模型把工具调用写成普通文本的情况。

部分服务商（尤其是走 OpenAI 兼容层的模型）在 ``tool_choice`` 不被遵守时，
会把调用写成 ``send_message(reply_to_message_id=2708) 正文``、``send_message({"text": ...})``
或 ``send_message{...}`` 这样的纯文本。这里统一解析成结构化调用，避免把调用语法
原样发到聊天里，也避免参数名被猜成 ``message`` / ``content``。
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from typing import Any

_SEND_MESSAGE_TEXT_ALIASES = ("message", "content", "msg")

_KWARG_RE = re.compile(
    r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"(\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'|\[[^\]]*\]|\{[^}]*\}|[^,]+)"
)


@dataclass(frozen=True, slots=True)
class TextualToolCall:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    positional: str = ""
    trailing: str = ""

    def text_argument(self) -> str:
        for value in (self.arguments.get("text"), self.positional, self.trailing):
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""


def _split_call(text: str) -> tuple[str, str, str, str] | None:
    """把 ``name(...)`` / ``name{...}`` 拆成 (name, opener, 括号内, 括号后剩余)。"""
    match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*([\(\{])", text)
    if match is None:
        return None
    name = match.group(1)
    opener = match.group(2)
    start = match.end() - 1
    depth = 0
    quote: str | None = None
    index = start
    while index < len(text):
        char = text[index]
        if quote is not None:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char in "({[":
            depth += 1
        elif char in ")}]":
            depth -= 1
            if depth == 0:
                inner = text[match.end() : index]
                return name, opener, inner, text[index + 1 :].strip()
        index += 1
    return None


def _parse_value(raw: str) -> Any:
    value = raw.strip()
    if not value:
        return ""
    lowered = value.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if lowered == "null":
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return value


def _parse_kwargs(inner: str) -> dict[str, Any]:
    arguments: dict[str, Any] = {}
    for match in _KWARG_RE.finditer(inner):
        arguments[match.group(1)] = _parse_value(match.group(2))
    return arguments


def parse_textual_tool_call(content: str) -> TextualToolCall | None:
    """解析纯文本形式的工具调用；不像调用时返回 None。"""
    text = (content or "").strip()
    if not text:
        return None
    split = _split_call(text)
    if split is None:
        return None
    name, opener, inner, trailing = split
    inner = inner.strip()
    arguments: dict[str, Any] = {}
    positional = ""
    if opener == "{":
        try:
            data = json.loads("{" + inner + "}")
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        arguments = data
    elif inner.startswith("{"):
        try:
            data = json.loads(inner)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        arguments = data
    elif inner:
        parsed = _parse_kwargs(inner)
        if parsed:
            arguments = parsed
        else:
            positional = inner
    return TextualToolCall(name=name, arguments=arguments, positional=positional, trailing=trailing)


def normalize_tool_arguments(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """容忍模型把 send_message 的正文写成 message / content / msg。"""
    if name != "send_message":
        return dict(arguments)
    normalized = dict(arguments)
    if isinstance(normalized.get("text"), str) and normalized["text"].strip():
        return normalized
    for alias in _SEND_MESSAGE_TEXT_ALIASES:
        value = normalized.pop(alias, None)
        if isinstance(value, str) and value.strip():
            normalized["text"] = value
            break
    return normalized


def call_from_text(content: str) -> TextualToolCall | None:
    """解析并规范化文本调用，正文缺失时依次回退到位置参数和括号后文本。"""
    call = parse_textual_tool_call(content)
    if call is None:
        return None
    arguments = normalize_tool_arguments(call.name, call.arguments)
    positional = call.positional
    trailing = call.trailing
    if call.name == "send_message" and not str(arguments.get("text") or "").strip():
        for value in (positional, trailing):
            if value.strip():
                arguments["text"] = value.strip()
                break
    return TextualToolCall(name=call.name, arguments=arguments, positional=positional, trailing=trailing)


__all__ = ["TextualToolCall", "call_from_text", "normalize_tool_arguments", "parse_textual_tool_call"]

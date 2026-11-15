"""插件元数据与异常 — 插件加载器、插件 API 与 WebUI 共享的契约。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


class PluginError(RuntimeError):
    """插件子系统的基础异常。"""


class PluginNotFoundError(PluginError):
    """请求的插件不存在。"""


class PluginLoadError(PluginError):
    """插件导入或初始化失败。"""


class PluginInstallError(PluginError):
    """插件安装包无效或安装失败。"""


@dataclass(frozen=True, slots=True)
class PluginMetadata:
    """插件的自描述信息。

    插件可以在模块里用 ``METADATA`` 字典提供这些字段，也可以把它们作为
    ``PLUGIN`` 对象的属性。``name`` 必须唯一，建议使用小写字母、数字和
    连字符/下划线。
    """

    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    homepage: str = ""
    default_config: Mapping[str, Any] = field(default_factory=dict)

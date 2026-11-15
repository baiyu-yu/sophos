"""内置工具包。

内置工具与插件工具共享同一套 :class:`sophos.toolkit.Tool` / ``ToolRegistry``，
区别只是注册来源（origin）为 ``"builtin"``。插件使用
:class:`sophos.plugins.api.PluginAPI` 注册工具。
"""

from sophos.toolkit.base import Tool


def load_builtin_tools() -> list[Tool]:
    """实例化所有内置工具。

    延迟导入各工具模块，避免 ``sophos.tools`` 与 ``sophos.toolkit.runtime``
    之间形成循环依赖。
    """
    from sophos.tools.image_gen import IMAGE_GEN_TOOLS
    from sophos.tools.memory import MEMORY_TOOLS
    from sophos.tools.messaging import ALL_MESSAGING_TOOLS
    from sophos.tools.vision import VISION_TOOLS
    from sophos.tools.web import WEB_TOOLS

    return [
        *ALL_MESSAGING_TOOLS,
        *MEMORY_TOOLS,
        *VISION_TOOLS,
        *WEB_TOOLS,
        *IMAGE_GEN_TOOLS,
    ]


__all__ = ["Tool", "load_builtin_tools"]

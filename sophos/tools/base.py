"""向后兼容层：工具基类已移动到 :mod:`sophos.toolkit.base`。

新代码建议直接从 ``sophos.toolkit`` 导入。
"""

from sophos.toolkit.base import FunctionTool, Tool, ToolHandler

__all__ = ["FunctionTool", "Tool", "ToolHandler"]

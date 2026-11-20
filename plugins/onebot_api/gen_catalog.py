"""从 @snowluma/mcp 的动作目录生成 ``actions.py``。

SnowLuma 的官方 MCP 包（``@snowluma/mcp``）内置了完整的 OneBot 动作目录
（``dist/generated/catalog.js``），包含每个 action 的参数、是否只读、分类与说明。
本脚本把其中的关键信息压缩成 Python 字面量，供 onebot_api 插件做：

* action 名校验与拼写建议；
* 参数说明查询（``onebot_api_docs`` 工具）；
* 按参数 role 自动补全 ``group_id`` / ``user_id``。

用法（需要 Node.js 读取该 ESM 文件）::

    npm pack @snowluma/mcp@2.4.2 && tar -xzf snowluma-mcp-2.4.2.tgz
    node --input-type=module -e "import('./package/dist/generated/catalog.js').then(m => ...)"
    python plugins/onebot_api/gen_catalog.py catalog.json

其中 ``catalog.json`` 的结构为::

    {"source": "snowluma-mcp@2.4.2", "categories": ["信息", ...],
     "actions": [{"name": ..., "summary": ..., "read_only": false,
                  "category": ..., "aliases": [...],
                  "params": [{"name": ..., "required": true, "type": ...,
                              "role": ..., "desc": ...}]}]}
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

OUTPUT = Path(__file__).with_name("actions.py")


def _quote(value: str) -> str:
    text = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")
    return f'"{text}"'


def _render_params(params: list[dict[str, Any]], indent: str) -> list[str]:
    lines = [f'{indent}"params": (']
    for param in params:
        name = _quote(str(param.get("name") or ""))
        required = "True" if param.get("required") else "False"
        type_name = _quote(str(param.get("type") or ""))
        role = _quote(str(param.get("role") or ""))
        desc = _quote(str(param.get("desc") or ""))
        lines.append(f"{indent}    ({name}, {required}, {type_name}, {role}, {desc}),")
    lines.append(f"{indent}),")
    return lines


def render(data: dict[str, Any]) -> str:
    actions = sorted(data["actions"], key=lambda item: item["name"])
    categories = list(data.get("categories") or [])
    source = str(data.get("source") or "snowluma-mcp")

    lines = [
        '"""SnowLuma OneBot 动作目录（自动生成，请勿手改）。',
        "",
        "来源：@snowluma/mcp 的 dist/generated/catalog.js。",
        "重新生成：python plugins/onebot_api/gen_catalog.py <catalog.json>",
        "具体字段含义见 gen_catalog.py 的模块文档。",
        '"""',
        "",
        "# ruff: noqa: E501",
        "",
        "from __future__ import annotations",
        "",
        "from typing import Any",
        "",
        f"CATALOG_SOURCE = {_quote(source)}",
        "",
        f"CATALOG_SIZE = {len(actions)}",
        "",
        "CATEGORIES: tuple[str, ...] = (",
    ]
    lines.extend(f"    {_quote(name)}," for name in categories)
    lines.append(")")
    lines.append("")

    # category -> action names（保留分类顺序）
    by_category: dict[str, list[str]] = {name: [] for name in categories}
    for action in actions:
        by_category.setdefault(str(action.get("category") or ""), []).append(str(action["name"]))
    lines.append("CATEGORY_ACTIONS: dict[str, tuple[str, ...]] = {")
    for category, names in by_category.items():
        if not names:
            continue
        joined = ", ".join(_quote(name) for name in names)
        lines.append(f"    {_quote(category)}: ({joined}),")
    lines.append("}")
    lines.append("")

    lines.append("# name -> {summary, read_only, category, aliases, params[(name, required, type, role, desc)]}")
    lines.append("ACTIONS: dict[str, dict[str, Any]] = {")
    for action in actions:
        aliases = action.get("aliases") or []
        alias_repr = "(" + "".join(f"{_quote(str(alias))}," for alias in aliases) + ")"
        lines.append(f"    {_quote(str(action['name']))}: {{")
        lines.append(f"        \"summary\": {_quote(str(action.get('summary') or ''))},")
        lines.append(f"        \"read_only\": {'True' if action.get('read_only') else 'False'},")
        lines.append(f"        \"category\": {_quote(str(action.get('category') or ''))},")
        lines.append(f"        \"aliases\": {alias_repr},")
        lines.extend(_render_params(list(action.get("params") or []), "        "))
        lines.append("    },")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: gen_catalog.py <catalog.json>", file=sys.stderr)
        return 2
    data = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    OUTPUT.write_text(render(data), encoding="utf-8")
    print(f"wrote {OUTPUT} ({len(data['actions'])} actions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

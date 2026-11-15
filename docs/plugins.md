# 插件系统

Sophos 的工具子系统已经独立成 `sophos/toolkit`，插件系统建在它之上：
插件可以在运行时注册/注销工具，调用任意已注册工具（内置或其它插件的），
通过平台中立的 `MessageService` 发消息，也可以绕过 Sophos 的封装直接调用
协议端接口（当前是 OneBot 11）。

```
sophos/toolkit/     工具抽象与注册表（与具体应用解耦）
sophos/tools/       内置工具包（messaging / memory / vision / web / image_gen）
sophos/plugins/     插件 API、加载器、状态存储
plugins/            插件目录（PLUGINS_DIR）
```

- [快速开始](#快速开始)
- [插件放置与加载规则](#插件放置与加载规则)
- [插件定义形式](#插件定义形式)
- [PluginAPI 参考](#pluginapi-参考)
- [工具上下文](#工具上下文)
- [直连协议端（OneBot 11）](#直连协议端onebot-11)
- [管理 API 与 WebUI](#管理-api-与-webui)
- [生命周期与热重载](#生命周期与热重载)
- [持久化与数据库迁移](#持久化与数据库迁移)
- [安全模型](#安全模型)
- [调试与测试](#调试与测试)

## 快速开始

最省事的方式是打开 WebUI 的「插件」页面，点「上传插件」选择 `.zip` 或 `.py`，
上传后立即加载并在列表中显示。下面的命令行方式适合自动化或批量部署。

1. 复制示例插件：

   ```bash
   cp -r plugins/examples/demo plugins/demo
   ```

2. 重启 Sophos，或热重载插件：

   ```bash
   curl -X POST http://127.0.0.1:8080/api/plugins/reload
   ```

3. 查看插件与其工具：

   ```bash
   curl http://127.0.0.1:8080/api/plugins
   ```

   返回示例（节选）：

   ```json
   {
     "plugins": [
       {
         "name": "demo",
         "version": "0.1.0",
         "status": "loaded",
         "enabled": true,
         "tools": ["demo_echo", "demo_send_message", "demo_protocol_call"],
         "config": {"prefix": "[demo]", "allow_protocol_call": true},
         "default_config": {"prefix": "[demo]", "allow_protocol_call": true},
         "source": "directory",
         "path": "/app/plugins/demo/plugin.py",
         "error": null
       }
     ],
     "plugins_dir": "/app/plugins"
   }
   ```

插件注册的工具会立刻出现在 WebUI「工具」页的「插件」分组里，也自动进入
LLM 的 tool calling 列表（仍受会话工具白名单、适配器能力等既有约束）。

## 插件放置与加载规则

扫描 `PLUGINS_DIR`（环境变量，默认 `plugins`）：

```
plugins/
├── my-plugin/plugin.py   # 目录插件：按包加载，支持 from .helpers import ...
├── another.py            # 单文件插件
└── examples/demo/...     # 不会被扫描（示例）
```

| 规则 | 说明 |
| --- | --- |
| 目录插件 | `<dir>/<name>/plugin.py`，模块名 `sophos_plugins.<name>`，允许相对导入同目录模块 |
| 单文件插件 | `<dir>/<name>.py`，模块名 `sophos_plugins.<name>` |
| entry point | pip 包声明 `[project.entry-points."sophos.plugins"] demo = "my_package:plugin"`，值可以是模块，也可以是带 `setup` 的对象 |
| 同名冲突 | 目录/单文件优先，entry point 被忽略并记录 warning |
| 跳过 | 名称以 `.` 或 `_` 开头的文件/目录；`__init__.py` |
| 加载失败 | 不会影响 Sophos 启动；插件状态变为 `failed` 并带上 `error` 文本 |

## 插件定义形式

### 形式一：`PLUGIN` 对象/类（推荐）

```python
from sophos.plugins import PluginAPI, PluginMetadata


class MyPlugin:
    metadata = PluginMetadata(
        name="my-plugin",
        version="1.0.0",
        description="一句话介绍",
        author="you",
        homepage="https://example.com",
        default_config={"api_key": "", "reply_prefix": "[bot]"},
    )

    def setup(self, api: PluginAPI) -> None:
        ...

    def teardown(self) -> None:
        ...


PLUGIN = MyPlugin()
```

`PLUGIN` 也可以是类（加载器会实例化）。元数据也可以直接写成类属性
`name` / `version` / `description` / `author` / `homepage` / `default_config`。

### 形式二：模块级函数

```python
METADATA = {
    "name": "my-plugin",
    "version": "1.0.0",
    "description": "一句话介绍",
    "default_config": {"timeout": 10},
}


def setup(api):
    ...


def teardown():
    ...
```

`setup` / `teardown` 可以是普通函数，也可以是 `async def`。

## PluginAPI 参考

`setup(api)` 收到的对象提供以下稳定接口：

### 元信息与配置

| 成员 | 说明 |
| --- | --- |
| `api.name` / `api.version` / `api.description` / `api.author` / `api.homepage` | 插件元数据 |
| `api.metadata` | `PluginMetadata` 对象 |
| `api.config` | 只读映射，等于 `default_config` 与数据库覆盖值的合并结果 |
| `api.logger` | `logging.Logger`，名称 `sophos.plugin.<name>` |
| `api.tools` | 本插件当前注册的工具名列表 |

配置必须是 JSON 可序列化的 dict。管理端保存的是「覆盖值」，未覆盖的键回落到
`default_config`；修改配置会自动重载启用中的插件。

### 注册工具

```python
@api.tool(
    name="weather",                       # 省略则用函数名
    description="查询城市天气",            # 省略则用 docstring
    parameters={
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "城市名"},
        },
        "required": ["city"],
    },
    group="plugin",                       # WebUI 分组
    category="input",                     # input / output
    conversation_kinds=None,              # 例如 frozenset({"group"})
    required_capabilities=None,           # 例如 frozenset({"message.image"})
)
async def weather(params: dict, context: dict):
    return {"city": params["city"], "text": "晴，25°C"}
```

- 工具名在全局注册表内必须唯一；与内置工具重名会覆盖并写 warning，**不推荐**；
- 返回任意可 JSON 序列化的值；返回 `{"error": "..."}` 会被 LLM 当作失败结果；
- `parameters` 是标准 JSON Schema（没有 `required` 时允许空参数）；
- `required_capabilities` 使用 `sophos.platform.Capability` 的字符串值，
  当前适配器不满足时该工具不会暴露给 LLM，直接调用会抛 `PermissionError`；
- `conversation_kinds` 限定可用会话类型（`direct` / `group` / `channel` / `thread`）。

复杂工具可以继承 `sophos.toolkit.Tool` 后注册：

```python
from sophos.toolkit import Tool


class MyTool(Tool):
    group = "plugin"
    category = "input"

    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def description(self) -> str:
        return "..."

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    async def execute(self, params, context):
        return {"ok": True}


def setup(api):
    api.register_tool(MyTool())
```

`api.unregister_tool(name)` 只会移除本插件注册的工具，不会误删内置工具。

### 调用内置 / 其它工具

```python
async def setup(api):
    @api.tool(name="recall_helper", description="撤回消息并返回结果",
              parameters={"type": "object",
                          "properties": {"message_id": {"type": "integer"}},
                          "required": ["message_id"]})
    async def recall_helper(params, context):
        # 调用任意已注册工具；不传 context 时使用默认上下文（不绑定会话）
        return await api.call_tool("send_message", {
            "conversation_id": 1,
            "text": "hello",
        }, context)
```

- 内置工具清单可从 `GET /api/tools` 或 `sophos.toolkit.runtime.get_registry().list_tools()` 获取；
- 与 LLM 调用走同一套 `ToolRegistry.execute` 校验：禁用状态、工具白名单（当传入带会话的
  context 时由管线决定）、`required_capabilities`、必填参数；
- 插件工具也可以互相调用；注意避免无限递归。

### 发送消息

```python
sent = await api.send_message(
    "你好",
    conversation_id=42,
    reply_to_message_id=None,
    mention_user_ids=(),
    attachment_ids=(),
    inline_media=(),
)
# sent: SentMessage(message_id, conversation_id, external_message_id)
```

走平台中立的 `MessageService`，由当前账号的适配器发送；需要 Sophos 内部的
`conversation_id`（可从工具 context、数据库或 `query_messages` 等内置工具获得）。

### 外部 HTTP

```python
resp = await api.http.get("https://api.example.com/v1/status", params={"q": "1"})
if resp.ok:
    data = resp.json()

resp = await api.http.post(
    "https://api.example.com/v1/items",
    json={"name": "x"},
    headers={"Authorization": "Bearer ..."},
    timeout=15,
)
print(resp.status, resp.text)
```

| 成员 | 说明 |
| --- | --- |
| `request(method, url, *, params, json, data, headers, timeout=30.0, max_bytes=10*1024*1024)` | 通用请求，返回 `PluginHTTPResponse` |
| `get(url, *, params, headers, timeout=30.0)` | 便捷 GET |
| `post(url, *, json, data, headers, timeout=30.0)` | 便捷 POST |
| `PluginHTTPResponse.status/.headers/.content/.ok/.text/.json()` | 响应对象 |
| `PluginHTTPError` | 网络错误、超时、响应体超过 `max_bytes` |

共享一个 `aiohttp.ClientSession`（由插件管理器创建/关闭），不需要自己管理连接池。

### 数据库

```python
rows = await api.db.fetch("SELECT id, name FROM conversations LIMIT 5")
```

`api.db` 是原始 `asyncpg` 连接池，属于「逃生舱」：可执行任意 SQL。
表结构可能随版本变化，插件需自行承担兼容性与注入风险。没有数据库时抛 `RuntimeError`。

### 卸载回调

```python
def setup(api):
    task = asyncio.create_task(poll_loop())
    api.on_unload(lambda: task.cancel())
```

插件停用/重载/进程退出时，回调按注册顺序的**逆序**执行；同步函数和协程函数都支持，
单个回调异常会记录日志但不影响其它回调。

## 工具上下文

插件工具被 LLM 调用时，`context` 由消息管线构造，包含：

| 键 | 说明 |
| --- | --- |
| `store` | `MessageStore`，消息查询 |
| `message_service` | `MessageService`，发消息 |
| `platform_store` | 身份/会话/账号绑定查询 |
| `conversation_id` / `conversation_kind` / `account_id` | 当前会话 |
| `adapter_capabilities` | 当前适配器能力集合（字符串） |
| `timezone` / `user_id` | 时区与触发用户 |
| `provider_mgr` | LLM provider 管理器 |
| `pool` | asyncpg 连接池 |
| `memory_store` / `embedding_provider` | 记忆系统（启用时） |
| `vision_provider` | 视觉模型（配置时） |

`api.call_tool()` 不传 `context` 时使用默认上下文：能力取所有在线适配器的并集，
没有 `conversation_id`/`conversation_kind`，因此依赖会话的工具需要显式参数。

## 直连协议端（OneBot 11）

`api.protocol` 把 action 原样发给已连接的协议端，适合 Sophos 尚未封装的接口：

```python
@api.tool(name="group_digest", description="获取群列表与群信息",
          parameters={"type": "object", "properties": {}})
async def group_digest(params, context):
    groups = await api.protocol.call("get_group_list")
    first = await api.protocol.call("get_group_info", {"group_id": groups[0]["group_id"]})
    return {"count": len(groups), "first": first}
```

| 成员 | 说明 |
| --- | --- |
| `api.protocol.accounts()` | 当前已连接的账号 ID 列表 |
| `api.protocol.call(action, params=None, *, account_id=None, timeout=None)` | 调用协议 action，`account_id=None` 时使用第一个在线适配器 |

常用 OneBot 11 action：`get_login_info`、`get_group_list`、`get_group_info`、
`get_group_member_list`、`get_group_member_info`、`send_msg`、`delete_msg`、
`set_group_name`、`set_group_kick`、`set_group_ban`、`get_msg`、`get_friend_list`。

注意：

- 返回值是协议端响应中的 `data` 字段，结构随 action 变化；
- 协议端返回失败（retcode 非 0）时抛 `OneBotAPIError`，超时抛 `asyncio.TimeoutError`；
- 没有在线适配器时抛 `RuntimeError("无法连接协议端: ...")`；
- 仅当适配器实现了 `RawProtocolAdapter` 协议时可用（OneBot 11 适配器已实现）。

一些协议端能力与内置工具重叠（如发消息），优先使用 `api.send_message` /
`api.call_tool`，这样可以复用 Sophos 的入库、权限与会话解析逻辑。

## 管理 API 与 WebUI

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/plugins` | 列出插件、状态、配置、工具、目录 |
| POST | `/api/plugins/upload` | multipart 上传 `.zip` / `.py`；query `overwrite=true` 覆盖同名插件 |
| PUT | `/api/plugins/{name}/enabled` | body `{"enabled": false}`，立即停用/启用 |
| PUT | `/api/plugins/{name}/config` | body `{"config": {...}}`，覆盖配置并自动重载 |
| DELETE | `/api/plugins/{name}` | 停用并删除插件文件，同时清理开关与配置 |
| POST | `/api/plugins/reload` | 重新扫描目录并重载全部插件 |
| POST | `/api/plugins/{name}/reload` | 只重载一个插件 |

```bash
curl -X PUT http://127.0.0.1:8080/api/plugins/demo/enabled \
  -H 'Content-Type: application/json' -d '{"enabled": false}'

curl -X PUT http://127.0.0.1:8080/api/plugins/demo/config \
  -H 'Content-Type: application/json' \
  -d '{"config": {"prefix": "[测试]"}}'
```

`POST /api/plugins/upload` 的约束：

- 只接受 `.zip` 目录插件包或单个 `.py` 文件，请求体上限 16MB；
- zip 内必须包含 `plugin.py`（位于包根目录或唯一顶层目录下，唯一顶层目录会被剥掉并作为插件目录名）；
- zip ≤ 5MB、解压后 ≤ 20MB、条目 ≤ 500、单文件 ≤ 1MB；
- 拒绝绝对路径、`..` 路径穿越与软链接；
- `overwrite=true` 时覆盖同名插件目录/文件。

WebUI 的「插件」页面会按 `default_config` 的值类型渲染配置表单：布尔值用开关、
数字用数字输入框、字符串用文本框、数组/对象用 JSON 文本域；也可以切到 JSON
模式直接编辑整个配置。保存后启用中的插件会自动重载，停用中的插件只更新配置。

启用了 WebUI 密码时，这些接口同样需要登录 cookie。

## 生命周期与热重载

```
发现(discover) → 导入(import) → 解析 PLUGIN/setup → 合并配置
   → setup(api) → 注册工具 → status=loaded
```

停用/重载时：

```
卸载回调（逆序）→ teardown() → 注销本插件全部工具 → 从 sys.modules 移除
   → 重新导入（仅重载时）
```

插件工具在停用后会从注册表移除，因此 LLM 立刻看不到它们；启用后重新出现。
插件配置/开关保存在数据库，删除插件文件不会删除记录。

## 持久化与数据库迁移

插件状态存放在 `plugins` 表（`name` 主键、`enabled`、`config`、`updated_at`）。
本版本数据库 schema 版本为 **6**。从旧版本升级时先执行一次离线迁移：

```bash
# 宿主机（uv）
uv run python -m sophos.migrate_plugins

# Docker
docker compose run --rm sophos python -m sophos.migrate_plugins
```

未迁移直接启动会收到 `unsupported database schema version ...` 错误，属于预期行为。

## 安全模型

**插件代码与 Sophos 同进程运行，拥有完全信任**：可以访问文件系统、网络、环境变量、
数据库与任何内部对象。安装第三方插件前请先审阅代码。

系统提供的是「能力约束」而不是沙箱：

- 工具注册受注册表管理，插件只能注销自己来源的工具；
- `send_message` 属于不可禁用工具（`UNSAFE_DISABLE_TOOLS`），避免 bot 失去唯一回复手段；
- 工具执行时校验 `required_capabilities`、会话类型、必填参数；
- 会话级工具白名单在管线侧生效（直接调用 `api.call_tool` 时不自动套用会话白名单）；
- 插件配置以 JSON 明文存储，不要在其中放一次性密钥以外的敏感凭据；
- 建议在插件内部为网络请求设置超时，并捕获异常，避免拖慢 tool loop。

## 调试与测试

- 日志：`sophos.plugin.<name>` 前缀，文件日志（TRACE 级别）在 `logs/sophos.log`；
- 加载失败：`GET /api/plugins` 中 `status=failed`，`error` 字段是
  `异常类名: 消息`，同时日志里有完整 traceback；
- 重载单个插件只影响该插件，不会中断消息处理；
- 单元测试可以用 `MemoryPluginStateStore` + 临时目录 + 真实 `ToolRegistry`：

```python
from pathlib import Path

from sophos.plugins import MemoryPluginStateStore, PluginManager
from sophos.toolkit.registry import ToolRegistry


async def test_plugin(tmp_path: Path):
    plugin_dir = tmp_path / "demo"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.py").write_text(
        "from sophos.plugins import PluginMetadata\n"
        "class P:\n"
        "    metadata = PluginMetadata(name='demo')\n"
        "    def setup(self, api):\n"
        "        @api.tool(name='demo_ping', description='ping')\n"
        "        async def ping(params, context):\n"
        "            return {'pong': True}\n"
        "PLUGIN = P()\n",
        encoding="utf-8",
    )
    registry = ToolRegistry()
    manager = PluginManager(
        registry=registry,
        plugin_dir=plugin_dir.parent,
        state_store=MemoryPluginStateStore(),
    )
    await manager.init()
    assert registry.get("demo_ping") is not None
    await manager.close()
```

参考实现：`sophos/plugins/api.py`、`sophos/plugins/loader.py`、`sophos/toolkit/`。

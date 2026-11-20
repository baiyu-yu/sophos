# onebot_api 插件

让模型自主调用 OneBot 11 协议端接口（SnowLuma / NapCat / Lagrange / LLOneBot 等），
并把 SnowLuma 官方动作目录（222 个 action、12 个分类）内置进来，避免模型臆造接口名。

## 工具

| 工具 | 类型 | 说明 |
| --- | --- | --- |
| `onebot_api_docs` | 输入 | 查动作目录：不带参数列分类；`keyword` 搜索；`category` 过滤；`action` 看参数与示例 |
| `onebot_call` | 输出 | 调用任意 action：`action` + `params`（JSON 对象字符串） |

`onebot_api_docs` 是输入类工具，collector 节点也能用；`onebot_call` 是输出类工具，actor 节点调用。

## 自动补全

插件读取动作目录里参数的 `role` 字段：

- `role=group_id`：params 里省略或传 0 时，自动填入当前群聊的群号；
- `role=user_id` / `role=member_id`：把上下文里的 **内部 uid**（`{{uid}}`）自动映射成协议端账号（QQ 号），
  映射不到时按原值透传。

所以改群名片只需要：

```json
{"action": "set_group_card", "params": {"user_id": 12, "card": "新名片"}}
```

## 默认屏蔽

只屏蔽会让消息绕过 Sophos 入库/权限链路的写操作，并提示对应的内置工具：

- 发消息/转发/闪传/自定义表情/AI 语音/原始包 → `send_message`（或 `send_image`）
- `delete_msg` → `recall_message`
- `set_group_kick` / `set_group_ban` → `moderate_member`

其余接口（查询、群管理、群文件、群相册、空间、系统表情、流式接口等）默认放行。
需要时可在 WebUI「插件 → 配置」里改 `blocked_actions`。

## 配置

| 键 | 默认 | 说明 |
| --- | --- | --- |
| `blocked_actions` | 见上 | 禁止调用的 action 列表（整体覆盖默认值） |
| `allow_unknown_actions` | `false` | 允许调用目录之外的 action（拼错时会先报错并给建议） |
| `timeout` | `30` | 单次调用超时秒数（1–120） |
| `max_result_chars` | `12000` | 返回结果最大字符数（1000–200000） |

## 动作目录

`actions.py` 由 `gen_catalog.py` 从 `@snowluma/mcp` 的
`dist/generated/catalog.js`（动作名、分类、参数、是否只读、说明）生成，请勿手改。
更新目录：

```bash
npm pack @snowluma/mcp@latest && tar -xzf snowluma-mcp-*.tgz
node --input-type=module -e "...导出 catalog.json..."
python plugins/onebot_api/gen_catalog.py catalog.json
```

`catalog.json` 的结构见 `gen_catalog.py` 顶部的模块文档。

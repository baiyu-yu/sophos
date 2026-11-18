# Sophos

Sophos 是一个使用 PostgreSQL/pgvector 持久化数据、通过外部 IM adapter 接收消息的聊天机器人。

平台中间层的数据约束、工具能力模型和后续适配顺序见 [平台中间层架构与后续计划](docs/platform-abstraction-plan.md)。

## 开发

复制本地配置：

```bash
cp .env.example .env
```

日常开发只在容器中启动 PostgreSQL，Python 后端和 Vue 前端在宿主机运行：

```bash
docker compose up -d postgres
uv run python -m sophos.main
pnpm dev
```

Vite 开发服务器监听 `5173` 并将 `/api` 代理到后端的 `8080` 端口。

## Prompt

所有 prompt 存储在数据库中，在 WebUI 的「Prompt」页编辑，保存即生效并保留完整版本历史。

模板使用 `{{name}}` 引用变量，使用 `{{prompt.<key>}}` 引入另一条 prompt。系统提示词可用的变量：

`{{nickname}}`、`{{current_time}}`、`{{timezone}}`、`{{self_user_id}}`、`{{current_user_id}}`、`{{current_user_roles}}`、`{{conversation_id}}`、`{{conversation_kind}}`、`{{master_users}}`、`{{identity_context}}`、`{{message_format}}`、`{{runtime_context}}`。

单花括号原样保留。输出格式约束类 prompt 默认锁定，需要在 WebUI 中显式解锁后编辑。

## 设置与模型

WebUI「设置」页会列出全部运行时可调配置（按分组显示：身份与时间、对话与上下文、命令与触发、模型参数、视觉、失败告警、联网、工作流、数据清理、日志与网络），每项带说明与默认值，保存即写入数据库并立即生效；只有标注「重启生效」的少数项（日志轮转）需要重启。`.env` 只提供首次启动的默认值，除数据库地址、WebUI 密码、插件目录等启动引导项外，其余都不必改 `.env`。

- **命令前缀**：WebUI「设置」页可改，支持 1–3 个字符（如 `!`、`/`），保存后立即生效；`.` 始终兼容，中文句号「。」也会被识别。
- **触发正则**：WebUI「设置」页每行一条，群聊消息匹配任意一条正则即触发回复（不受 @ 与概率限制），支持 Python 正则、最多 50 条；也可在聊天里用 `.trigger regex add/remove/list/clear` 管理。
- **模型服务商**：添加服务商后会自动拉取可用模型；在模型列表点「设为…」即可绑定到对话回复、信息收集、图片识别、触发判断或向量嵌入；卡片上的刷新按钮可重新获取模型列表。
- **失败告警**：模型/工作流连续失败时不再向会话发送「模型服务暂时无响应」，而是静默记录；同一会话在 10 分钟内累计 3 次失败后，私信通知所有 Master。阈值、窗口与冷却可用 `.config failure_alert_threshold 5`、`.config failure_alert_window_seconds 600`、`.config failure_alert_cooldown_seconds 1800` 调整。
- **多条气泡**：模型调用 `send_message` 时可在 `text` 里用换页符 `\f` 分隔，Sophos 会拆成多条消息依次发送（回复与 @ 只挂在第一条）；模型如果输出的是字面量 `\f`（反斜杠 + f）也会被识别。
- **清理上下文**：`.clear assistant|user|all` 只清理当前会话（`assistant` 只删机器人消息，`user` 只删用户消息）；加 `global` 清理所有会话，仅 Master 可用。
- **消息模板**：`LLM_USER_SCHEMA` / `LLM_BOT_SCHEMA` 的值里含 `#`，在 `.env` 中必须用引号包起来（如 `LLM_USER_SCHEMA="[{{time}}] #{{mid}} {{name}}：{{message}}"`），否则 `#` 之后会被 dotenv 当成注释截断，导致上下文里只剩时间戳。模板缺少 `{{message}}` 时 Sophos 会把正文追加到末尾并打印警告。

## 权限与 Master

「权限管理」页的「最高权限」标签用于设置 **Master**：Master 隐式拥有全部权限，不受会话工具白名单与授权限制，也是失败告警的接收者。选择用户点「设为 Master」即可，至少保留一个 Master。

其余标签：

- **会话权限**：开关某个会话是否响应，并配置该会话的工具白名单；
- **用户授权**：把某个权限（如 `cmd.config`、`bot`）授予指定用户，可限定在某个会话或全局；
- **用户策略**：抑制 LLM 触发、调整触发概率倍率、抑制刷新注入。

Master 存储在 `user_roles` 表（`role='master'`），启动时加载；WebUI 修改后立即刷新缓存。

## 插件

工具子系统独立在 `sophos/toolkit`，插件放在 `plugins/`（可用 `PLUGINS_DIR` 修改）：

```
plugins/
└── my-plugin/
    └── plugin.py
```

插件可以注册任意工具、调用内置工具、通过 `MessageService` 发消息、直连 OneBot 11
协议端接口，或访问外部 HTTP API。除了把文件放进 `plugins/`，也可以直接在 WebUI 的
「插件」页面**上传** `.zip` 或 `.py` 插件，并在同一页面启停、修改配置、重载或删除。

示例：

```bash
cp -r plugins/examples/demo plugins/demo
curl -X POST http://127.0.0.1:8080/api/plugins/reload
curl http://127.0.0.1:8080/api/plugins
```

完整的插件 API、工具参数 Schema、协议端调用示例和安全说明见
[插件开发文档](docs/plugins.md)。插件状态（启用开关、配置）保存在数据库 `plugins` 表，
从 schema v5 升级时需要执行一次 `python -m sophos.migrate_plugins`。

插件注册的工具会出现在「工具管理」里，并带有「插件 · 插件名」标识，可以在同一页面
启停、改描述；从「插件」页面或工具管理页右上角的「上传插件」都能直接上传。

## 协议端连接

OneBot 11 连接不再写死在环境变量里，由 WebUI 的「协议端」页面管理（保存在数据库
`onebot_connections` 表）：

- 新增、编辑、删除连接，配置 WebSocket 地址与 token；
- 开关「自动重连」、调整重连间隔（1~600 秒）；
- 随时「停止」「启动」或「重连」，页面每 5 秒刷新一次连接状态与机器人信息。

首次启动会从 `ONEBOT_WS_URL`（Docker 环境为 `CONTAINER_ONEBOT_WS_URL`）生成一条
「默认连接」作为种子；之后以页面中的配置为准，已经存在的连接不会被 env 覆盖。

从 schema v6 升级时需要执行一次 `python -m sophos.migrate_connections`。

## 容器集成验证

完整镜像同时包含 Python 后端和构建后的 Vue WebUI。生产运行时由 Aiohttp 在 `8080` 端口提供 API 和前端静态资源，不运行 Vite 进程。

```bash
docker compose up -d --build
```

仓库中的 Compose 只管理 Sophos 和 PostgreSQL。NapCat 等 IM adapter 由部署环境独立管理，并通过 `CONTAINER_ONEBOT_WS_URL` 配置连接地址。

## 镜像部署

镜像通过 GitHub Actions 手动构建并推送到 Docker Hub。推送分支后：

1. 打开仓库 **Actions** → **Docker** → **Run workflow**；
2. 选择分支，填写版本标签（默认 `latest`，也可填 `v1.0.0` 等）；
3. 运行完成后镜像位于 `docker.io/<DOCKERHUB_USERNAME>/sophos:<版本>`。

> 重要：`<DOCKERHUB_USERNAME>` 是 Actions 里配置的 secret 值，不是 GitHub 用户名。
> 本仓库默认使用 `baiyuyuyu/sophos`；如果你换了自己的 Docker Hub 账号，记得同步
> 修改 compose 的 `SOPHOS_IMAGE`。

在 `.env` 里指定实际仓库名（只写仓库，不带 tag）：

```bash
SOPHOS_IMAGE=<你的DockerHub用户名>/sophos
SOPHOS_VERSION=v1.0.0   # 或 latest
```

然后：

```bash
docker compose pull
docker compose up -d
```

如果 Docker Hub 仓库是**私有**的，需要先登录；另外国内镜像加速器
（如 `docker.m.daocloud.io`）通常无法代理私有仓库，会返回 403，此时可临时直连
Docker Hub 或换用支持私有仓库的加速器：

```bash
docker login -u <你的DockerHub用户名>
```

### 配置 Docker Hub 凭据

在 GitHub 仓库页面：**Settings → Secrets and variables → Actions → New repository secret**，
添加：

| Name | 说明 |
| --- | --- |
| `DOCKERHUB_TOKEN` | 必填。Docker Hub 的 Access Token（Docker Hub → Account settings → Personal access tokens，权限选 Read & Write） |
| `DOCKERHUB_USERNAME` | 必填。Docker Hub 用户名；必须与 compose 里 `SOPHOS_IMAGE` 的用户名一致 |

实际的 `.env`、数据库数据和日志不会打包进镜像或提交到 Git。

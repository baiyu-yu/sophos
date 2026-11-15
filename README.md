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

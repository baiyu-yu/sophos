# 插件目录

Sophos 启动时扫描 `PLUGINS_DIR`（默认 `plugins/`）并加载插件。支持两种放置方式：

```
plugins/
├── my-plugin/          # 目录插件：按包加载，可用相对导入引用同目录辅助模块
│   ├── plugin.py       # 入口文件（必须）
│   └── helpers.py      # 可选
├── another.py          # 单文件插件
└── examples/           # 不会被扫描（没有 plugin.py），仅作示例
```

- 目录插件优先于同名单文件插件；
- 以 `.` 或 `_` 开头的目录/文件会被跳过；
- 也支持 pip 包通过 entry point 组 `sophos.plugins` 分发；
- 插件默认启用，可在 WebUI/管理 API 中停用，状态保存在数据库 `plugins` 表。

示例见 [`examples/demo/plugin.py`](examples/demo/plugin.py)：

```bash
cp -r plugins/examples/demo plugins/demo
# 重启 Sophos，或：
curl -X POST http://127.0.0.1:8080/api/plugins/reload
```

也可以直接在 WebUI 的「插件」页面点「上传插件」，选择 `.zip` 目录插件包或单个
`.py` 文件；如需配置项，在插件卡片上点配置按钮即可。上传、启停、配置与删除都不需要
重启服务。

完整 API 参考、工具注册、协议端直连（OneBot 11）、HTTP 调用与安全说明见
[`docs/plugins.md`](../docs/plugins.md)。

Docker 部署时 compose 会把宿主机 `./plugins` 挂载到容器 `/app/plugins`，改完插件后
重载即可生效，无需重建镜像。

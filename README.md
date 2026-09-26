# My_Clash 2.0

保留 My_Clash 的订阅转换、服务分流、地区测速、广告拦截和 Telegram / OpenClaw DNS 配置，将手工维护的长配置重构为可校验、可重复生成的规则工程。

原仓库：[Aitidi/My_Clash](https://github.com/Aitidi/My_Clash)。迁移基线、修复范围见 [迁移说明](docs/migration.md)。

## 快速开始

需要 Python 3.11 或更新版本。在仓库根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m my_clash validate
.\.venv\Scripts\python.exe -m my_clash build
```

Linux / macOS 使用 `.venv/bin/python` 替换 `.\.venv\Scripts\python.exe`。下文 `python` 指已安装项目依赖的解释器；可先激活虚拟环境。

## 使用配置

### 私有仓库：本机订阅转换

当前仓库为私有仓库，第三方在线转换服务不能匿名读取其 GitHub Raw 地址。保持仓库私有时，在本机运行 subconverter，然后启动配置服务：

```shell
python -m my_clash serve
```

将本机转换工具的「远程配置 / 外部配置」设为：

```text
http://127.0.0.1:8000/Config/my_config.ini
```

配置服务仅监听 `127.0.0.1`，仅提供 `dist/local/` 内的生成产物，不提供仓库源码。保持它运行，再在本机转换工具中填写自己的订阅链接。修改源文件后重启服务即可重新生成。端口可通过 `--port 8001` 调整。

**这里的 127.0.0.1 指转换后端所在的机器。** 远程在线转换后端不能访问你的本机服务；Docker 容器也有独立的回环地址。本用法针对直接运行在同一台电脑上的 subconverter。23 份 ACL4SSR 外部规则仍需联网读取，启动配置服务不等于完全离线转换。

subconverter 的 `config` 参数及订阅 URL 需要 URL 编码，具体调用方法见 [官方说明](https://github.com/tindy2013/subconverter/blob/master/README-cn.md#简易用法)。本项目不接收、保存或上传你的订阅链接。

### 可访问的静态托管地址

在拥有可供转换后端读取的静态文件服务时：

```shell
python -m my_clash build --base-url https://your-host.example/my-clash --output dist/publish
```

将 `dist/publish/` 的内容部署至对应目录，外部配置地址为 `https://your-host.example/my-clash/Config/my_config.ini`。

仓库根目录的默认生成产物使用 `settings/policy.yaml` 中的 GitHub Raw 根地址；该地址只有在仓库允许相应访问时才能使用。本次重构没有改变仓库可见性。

### DNS 与 Telegram 媒体下载

`Config/dns_config.yaml` 是 Clash Verge Rev 的 DNS 设置片段，不是完整订阅配置。启用本地 DNS 覆盖（`verge.yaml` 中的 `enable_dns_settings: true`），使用此片段，再重启 Clash Verge Rev / Mihomo 和 OpenClaw Gateway。

迁移保留了 `telegram.org`、`t.me`、`telegram-cdn.org` 及其子域名的 Fake-IP 例外。具体操作和排查见 [DNS 配置说明](Config/README.md)。

## 维护规则

| 修改内容 | 编辑位置 |
| --- | --- |
| 路由顺序、目标策略、外部规则地址 | `settings/policy.yaml` 的 `routes` |
| 分组和地区正则 | `settings/policy.yaml` 的 `groups` |
| 多个服务共用的选项 | `settings/policy.yaml` 的 `group_templates` |
| DNS | `settings/dns.yaml` |
| 本地规则 | `rules/Ruleset/`、`rules/BlockAD/` |

修改后执行：

```shell
python -m my_clash validate
python -m my_clash build
python -m unittest discover -s tests -v
python -m my_clash build --check
```

规则按原有顺序匹配。新增 `.list` 文件会导出到兼容路径，但**不会自动启用分流**，还需要在 `routes` 中添加引用。维护示例见 [架构与开发说明](docs/architecture.md)。

不要直接修改根目录下的 `Ruleset/`、`BlockAD/`、`Config/my_config.ini`、`Config/dns_config.yaml` 或 `Config/catalog.json`，这些都是生成产物。提交时同时提交源文件和生成产物；CI 会检查两者一致。

## 命令

| 命令 | 用途 |
| --- | --- |
| `python -m my_clash validate` | 离线检查规则语法、路径大小写、分组引用、循环、兜底规则和 DNS |
| `python -m my_clash build` | 生成 INI、DNS、161 份规则列表及带 SHA-256 的目录 |
| `python -m my_clash build --check` | 只检查产物差异，有差异返回非零退出码 |
| `python -m my_clash stats` | 查看 JSON 统计 |
| `python -m my_clash serve` | 提供本机转换配置 |
| `python -m my_clash check-sources` | 显式联网检查外部规则是否可读取及解析 |

普通生成、校验和测试均不访问网络。外部规则仍保留原仓库的 ACL4SSR 动态来源；构建可重复不代表远端规则内容被锁定。`check-sources` 不自动修改或同步规则。

## 来源

原有规则和来源注释保留在 `rules/`，包括 ACL4SSR 及其他作者的贡献；具体出处以每份规则的注释为准。详见 [来源说明](NOTICE.md)。

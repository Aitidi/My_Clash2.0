# 配置产物

- `my_config.ini`：subconverter 外部配置，包含有序路由与代理分组。
- `dns_config.yaml`：Clash Verge Rev 本地 DNS 设置片段。
- `catalog.json`：所有本地规则文件的数量、启用策略、文件内去重数量与生成内容 SHA-256。

修改 `settings/` 与 `rules/` 后运行 `python -m my_clash build` 更新产物。

## Telegram / OpenClaw 媒体下载

1. 在 Clash Verge Rev 中启用本地 DNS 设置；本机 `verge.yaml` 中应有 `enable_dns_settings: true`。它属于客户端设置，不是此 INI 能控制的订阅字段。
2. 在客户端 DNS 设置处使用 `dns_config.yaml` 的内容。该文件没有最外层 `dns:`；如果手动合并到完整 Mihomo 配置，需要放到 `dns:` 下。
3. 重启 Clash Verge Rev / Mihomo，再重启 OpenClaw Gateway。
4. 重新测试 Telegram 图片与文件的上传、下载。

Fake-IP 例外包括 Telegram 主域及子域，目的是避免相关域名被解析为 Fake-IP 后影响媒体处理。保留原始监听地址、DNS 上游和其余配置；这次重构未修改你电脑上的客户端设置。

`my_config.ini` 并不自动导入 DNS 片段，两个配置需要分别使用。

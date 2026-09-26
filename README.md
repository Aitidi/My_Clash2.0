# My_Clash2.0

供 [subconverter](https://github.com/tindy2013/subconverter) 使用的静态外部配置。填写以下配置地址，并另外填写你自己的订阅地址：

```text
https://raw.githubusercontent.com/Aitidi/My_Clash2.0/main/Config/my_config.ini
```

`Config/my_config.ini` 引用本仓库 `Ruleset/` 中的 40 份规则列表，按用途分为：

- `Ruleset/拦截/`：6 份拦截规则
- `Ruleset/直连/`：14 份直连规则
- `Ruleset/服务/`：20 份服务及加速规则

转换器需要能够访问 GitHub Raw。修改规则时直接编辑对应 `.list`；调整分组或引用顺序时编辑 `Config/my_config.ini`。

本仓库只保存订阅转换所需的静态文件，不包含代理节点、订阅链接或 DNS 覆盖配置。规则来源与许可见 [NOTICE.md](NOTICE.md)。

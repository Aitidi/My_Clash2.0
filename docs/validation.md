# 重构验证记录

验证日期：2026-09-26。

## 本地验证

- Windows，Python 3.14.3，PyYAML 6.0.3。
- 29 项离线单元 / 回归测试通过，包括旧 Windows 控制台编码兼容性和跨平台目录排序检查。
- `validate`：161 份规则列表，文件内去重后 59,458 条，27 个分组，42 条规则来源 / 兜底配置。
- `build --check`：生成产物与当前源码一致。
- 23 个 ACL4SSR 远程地址均成功下载并通过规则解析。动态上游可能在本次验证后变化。
- 与原仓库快照比较：所有 27 个分组逐行一致；路由仅删除迁移说明中列出的两处问题引用，并替换本仓库发布根地址；DNS 仅移除重复 `time.*.com`。

## 真实转换验证

使用 [subconverter v0.9.0](https://github.com/tindy2013/subconverter/releases/tag/v0.9.0) 官方 Windows x64 发布包运行 `scripts/smoke_subconverter.py`：

```json
{"groups": 27, "proxies": 9, "rules": 55417, "result": "passed"}
```

这里的 55,417 是当前启用的本地与远端规则经 subconverter 转换后的数量；59,458 是仓库全部本地列表的去重后数量，两者统计口径不同。

验证确认配置能够被真实转换程序接受、分组引用有效、测试地区分组有节点、个人规则存在且最终规则为 `MATCH,漏网之鱼`。未使用真实订阅，不代表真实节点连通性、客户端 DNS 覆盖或 OpenClaw 媒体下载已在用户环境中验证。

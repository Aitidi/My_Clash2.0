# 规则精简验证记录

验证日期：2026-09-26。

- Windows，Python 3.14.3，PyYAML 6.0.3：32 项离线单元与回归测试通过。
- `validate`：40 份规则列表，文件内去重后 55,305 条；27 个分组、42 条路由来源与内置规则、外部规则 URL 计数为 0。
- `build --check`：生成配置与源文件一致。根目录的 40 份 `.list` 与 `settings/policy.yaml` 中的文件引用集合完全一致。
- 23 份 ACL4SSR 规则取自提交 `46ce840aa8cbfccce071558bfc1ad57704e32219`；每份原始内容的 SHA-256 记录在 `settings/acl4ssr-lock.json` 并由 `validate` 校验。保存了原仓库 CC BY-SA 4.0 许可证文本。
- 与原仓库快照比较：27 个分组逐行一致，路由顺序和目标保持一致，仅移除了此前已确认的重复及无效引用；所有 ACL4SSR 地址改为本仓库规则路径。
- 清理了 248 个未被引用的列表文件（源目录与生成目录合计）。
- 后续合并了仍存在的 40 份源与生成规则副本，仓库只保留根目录的 40 份原始规则。

真实转换验证使用 [subconverter v0.9.0](https://github.com/tindy2013/subconverter/releases/tag/v0.9.0) 官方 Windows x64 发布包运行 `scripts/smoke_subconverter.py`：

```json
{"groups": 27, "proxies": 9, "rules": 55424, "result": "passed"}
```

测试使用 9 个虚拟节点，通过本机回环 HTTP 服务提供配置与全部规则。生成结果的分组、个人规则及最终兜底规则均通过检查。55,424 是 subconverter 输出规则数；55,305 是仓库内 40 份列表在单文件内去重后的总数，两者统计口径不同。原始规则中的重复项保留。未使用真实订阅，也未验证真实节点连通性或用户设备上的 DNS 与 OpenClaw 行为。

# 从 My_Clash 迁移

基线提交：`ee8a9461374a480c4cb858073ab7585ff0377155`，来自 [原仓库](https://github.com/Aitidi/My_Clash)。机器可读记录见 `settings/provenance.json`。

## 保留行为

- 当前分流所需的自定义规则及其内容保留在 `rules/`。原仓库未引用的列表在后续精简中已删除。
- 27 个分组的名称、顺序、默认选项、地区正则、测速 URL、间隔和容差全部保留，测试按旧 INI 逐行对比。
- 广告拦截优先及其余路由先后顺序保留；AdobeBan 原本被注释，继续不启用。
- 原有 23 份 ACL4SSR 规则的路由位置与目标组保持不变；规则内容现按同一上游提交保存于本仓库，不再动态访问 ACL4SSR。
- DNS 服务器、监听配置、Fake-IP 设置及 Telegram 例外保留。
- 生成文件继续提供 `Config/my_config.ini`、`Config/dns_config.yaml`、`Ruleset/`、`BlockAD/` 路径，规则目录只含当前引用的 40 份列表。

## 修复

| 原问题 | 处理 | 对行为的影响 |
| --- | --- | --- |
| `Ruleset/aitidi.list` 不存在，只有 `Aitidi.list` | 移除无效直连引用 | 现有 `Aitidi` 分组和较早的有效引用保持原样；没有擅自改成直连 |
| GoogleFCM 先分流到 Google，后又在加速中重复引用 | 移除后面的重复引用 | 保持先匹配 Google 的逻辑 |
| DNS 的 `time.*.com` 重复 | 保留第一次 | 匹配范围不变 |
| AdobeBan 是 YAML payload，TikTok 混入 Surge 标头 | 生成时统一为标准规则列表 | 原始内容及注释仍保留在源文件 |
| 同一文件出现重复规则 | 生成时保留第一次 | 共移除 18 条重复项，不跨文件去重 |
| 本地规则 URL 指向旧仓库，路径混用 `refs/heads` | 统一为可配置发布根地址 | 新产物不再读取旧仓库的自定义列表 |

## 使用差异

以前直接修改长 INI；现在修改 `settings/policy.yaml` 后生成。以前直接修改根目录的 `.list`；现在修改 `rules/` 内同名文件。

2026-09-26 的进一步精简将全部 ACL4SSR 引用换成仓库内快照，并移除所有未引用的源与生成列表。要更新快照，执行 `python scripts/update_acl4ssr.py --commit <ACL4SSR 完整提交 SHA>`，再重建并检查差异。

新仓库当前为私有，不能把新的 GitHub Raw 链接直接交给匿名第三方转换服务。使用 `python -m my_clash serve` 配合本机转换后端，或部署生成产物至可访问的静态服务。未改变旧仓库或用户本机代理设置。

## 不属于本次修改

未调整个人域名、拦截范围和服务分流偏好。旧配置中的韩国、法国测速组仍被保留，但没有擅自加入其他分组的选项。使用者可以在 `group_templates.service` 中按需增加它们。

此项目管理规则与转换配置，不提供代理节点。本次验证使用虚拟测试节点，不代表已经测试用户的真实机场订阅或 Telegram / OpenClaw 实际网络连通性。

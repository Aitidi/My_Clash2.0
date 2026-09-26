# 架构与维护

## 数据流

```text
settings/policy.yaml ─┐
settings/dns.yaml ────┼─> Project 校验 ─> Config/ 中的生成配置
Ruleset/ + BlockAD/ ─┘          │
                               ├─> --check 检测生成配置差异
                               └─> --output 打包配置和原始规则
```

`settings/` 与 `Config/` 使用不同名称，确保在 Windows 不区分大小写的文件系统上也能清晰区分源文件和产物。

## 代码职责

- `my_clash/model.py`：读取声明式策略，展开模板，检查分组依赖图、来源路径及 DNS 必需项。重复 YAML 字段直接报错，避免误覆盖。
- `my_clash/rules.py`：解析普通列表、Surge `[Rule]` 和 Clash `payload`；验证已有规则类型与 CIDR，并报告文件内重复数量，不改写规则内容。
- `my_clash/build.py`：生成 subconverter INI、DNS YAML 和目录清单；向其他目录打包时原样复制规则。所有输入先校验，每个输出以临时文件加原子替换方式写入。已有正确文件不会重写；不是全目录事务。
- `scripts/update_acl4ssr.py`：按一个上游提交下载、解析并锁定当前使用的 23 份 ACL4SSR 规则。
- `my_clash/cli.py`：命令入口和仅监听回环地址的本机配置服务。

使用 Python 标准库和固定版本的 PyYAML；无数据库、无账号系统、无订阅存储。命令默认以当前目录为仓库根，也可使用 `python -m my_clash --root /path/to/repo validate`。

## 新增分流

1. 在 `Ruleset/Example.list` 中写入：

   ```text
   DOMAIN-SUFFIX,example.com
   ```

2. 在 `settings/policy.yaml` 的 `routes` 中合适的位置添加：

   ```yaml
   - target: 加速
     file: Ruleset/Example.list
   ```

3. 执行校验、构建和测试。`file` 按大小写精确匹配，直接使用仓库相对路径。

路由来源只能是 `file`、`url`、`rule` 中的一种。内置规则支持 `GEOIP,国家代码`（可带 `no-resolve`）和最后的 `FINAL`；重复来源直接报错。停用规则时也需移除不再被引用的 `.list` 文件。

## 分组模板

```yaml
group_templates:
  service:
  - 加速
  - 自动选择
  - 手动选择
groups:
- name: Example
  type: select
  template: service
  choices:
  - DIRECT
```

模板列表会放在附加 `choices` 之前，因此不会改变默认选项。模板仅包含选项名称，不构成实际分组。分组 `filter` 沿用 subconverter 的正则格式；地区排除正则中的负向前瞻不应直接复制到仅支持 RE2 的其他引擎。

本工具只支持现有工程需要的 `select` 和 `url-test` 类型；需要扩展类型时，应同步修改模型、渲染和测试。

## 规则兼容性与顺序

支持现有八种规则：`DOMAIN`、`DOMAIN-SUFFIX`、`DOMAIN-KEYWORD`、`IP-CIDR`、`IP-CIDR6`、`PROCESS-NAME`、`USER-AGENT`、`URL-REGEX`。

保留 `USER-AGENT` 与 `URL-REGEX` 是为了延续原有 subconverter 多目标规则库；不同目标客户端的支持由 subconverter 决定。这里导出的 `.list` 不是完整 Mihomo 配置，也不能假定所有规则都能直接作为 Mihomo 原生 rule-provider 使用。

不会排序、改写或跨文件去重，因为这些操作可能改变首次匹配结果。原文件注释含历史计数时，以 `Config/catalog.json` 中的当前解析计数为准。规则目录只能保存 `routes` 实际引用的 `.list`；未引用文件会使校验失败。

向已有外部目录打包时，若发现不属于当前规则集的旧 `.list`，构建会报错并列出文件。核对后手工删除，或换一个空目录打包；工具不递归清理目录。

## 测试和 CI

离线测试覆盖旧分组逐行一致性、路由顺序、DNS 迁移、混合规则格式、无效输入、循环引用、确定性生成和只读差异检查。`tests/fixtures/` 是原仓库配置快照，仅用于行为回归，不能作为当前配置使用。

迁移回归测试刻意固定了旧配置语义和基线规则数量。后续主动改变路由、分组、DNS 行为或增删规则时，需要同步调整相应预期并说明原因；不要用覆盖历史快照的方式让测试静默通过。

GitHub Actions 在 Windows / Ubuntu 和 Python 3.11 / 3.14 上安装依赖、校验、运行测试、检查生成产物，并上传独立配置包。正常 CI 不向 ACL4SSR 请求规则。

另提供真实转换烟雾测试。先在本机启动 subconverter，然后执行：

```shell
python scripts/smoke_subconverter.py --endpoint http://127.0.0.1:25500
```

测试在临时目录生成配置和 9 个虚拟 SOCKS5 节点，通过临时回环 HTTP 服务交给 subconverter，检查分组、节点引用、个人规则和最终兜底规则；结束后关闭临时服务。它不会连接测试代理，也不需要向 ACL4SSR 拉取规则。该测试不放入普通 CI，因为需要单独启动 subconverter。

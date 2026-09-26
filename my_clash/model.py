"""Load and validate policy data before any generated file is written."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import urlsplit

import yaml

from .rules import ConfigError, RuleList, parse_rules


class UniqueLoader(yaml.SafeLoader):
    """Reject duplicate YAML keys instead of silently overwriting policy."""


def _mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise ConfigError("YAML 字段名必须是字符串")
        if key in result:
            raise ConfigError(f"YAML 字段重复: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def load_yaml(path: Path) -> dict:
    try:
        value = yaml.load(path.read_text(encoding="utf-8-sig"), Loader=UniqueLoader)
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConfigError(f"{path}: 预期 YAML 对象")
    return value


def check_url(value: str, *, base: bool = False) -> str:
    if not isinstance(value, str) or any(c.isspace() for c in value) or "`" in value:
        raise ConfigError(f"URL 无效: {value!r}")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.fragment:
        raise ConfigError(f"URL 必须是有效的 HTTP(S) 地址: {value!r}")
    if parsed.username or parsed.password or (base and parsed.query):
        raise ConfigError("URL 不允许含凭据；发布根地址不允许含查询参数")
    return value.rstrip("/") if base else value


def _token(value, label):
    if not isinstance(value, str) or not value or any(c in value for c in "`\r\n,"):
        raise ConfigError(f"{label}: 必须是非空字符串，且不含换行、逗号或反引号")


def _keys(obj, required, optional, label):
    if not isinstance(obj, dict) or not required <= obj.keys() or obj.keys() - required - optional:
        raise ConfigError(f"{label}: 缺少必需字段或包含未知字段")


def expand_groups(policy: dict) -> list[dict]:
    templates = policy["group_templates"]
    if not isinstance(templates, dict):
        raise ConfigError("group_templates 必须是对象")
    for name, choices in templates.items():
        if not isinstance(choices, list):
            raise ConfigError(f"分组模板 {name}: 必须是字符串列表")
        for choice in choices:
            _token(choice, f"分组模板 {name}")
    if not isinstance(policy["groups"], list) or not policy["groups"]:
        raise ConfigError("groups 必须是非空列表")
    result = []
    names = set()
    for source in policy["groups"]:
        _keys(source, {"name", "type"}, {"template", "choices", "filter", "url", "interval", "tolerance"}, "分组")
        group = deepcopy(source)
        name = group["name"]
        _token(name, "分组名")
        if name in names or name in {"DIRECT", "REJECT"}:
            raise ConfigError(f"重复或保留的分组名: {name}")
        names.add(name)
        if not isinstance(group["type"], str) or group["type"] not in {"select", "url-test"}:
            raise ConfigError(f"分组 {name}: 不支持的类型")
        template = group.pop("template", None)
        if template is not None and (not isinstance(template, str) or template not in templates):
            raise ConfigError(f"分组 {name}: 未知模板 {template!r}")
        choices = group.get("choices", [])
        if not isinstance(choices, list):
            raise ConfigError(f"分组 {name}: choices 必须是列表")
        group["choices"] = [*(templates[template] if template else []), *choices]
        for choice in group["choices"]:
            _token(choice, f"分组 {name} 选项")
        if len(set(group["choices"])) != len(group["choices"]):
            raise ConfigError(f"分组 {name}: 重复选项")
        if "filter" in group:
            pattern = group["filter"]
            if not isinstance(pattern, str) or not pattern or any(c in pattern for c in "`\r\n"):
                raise ConfigError(f"分组 {name}: 无效筛选表达式")
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ConfigError(f"分组 {name}: 无效筛选表达式: {exc}") from exc
        if not group["choices"] and not group.get("filter"):
            raise ConfigError(f"分组 {name}: 缺少节点来源")
        if group["type"] == "url-test":
            if group["choices"] or not {"url", "interval", "tolerance"} <= group.keys():
                raise ConfigError(f"分组 {name}: 测速字段不完整或包含固定选项")
            check_url(group["url"])
            for field, minimum in (("interval", 1), ("tolerance", 0)):
                if type(group[field]) is not int or group[field] < minimum:
                    raise ConfigError(f"分组 {name}: {field} 必须是 >= {minimum} 的整数")
        elif {"url", "interval", "tolerance"} & group.keys():
            raise ConfigError(f"分组 {name}: select 分组不接受测速字段")
        result.append(group)
    graph = {g["name"]: g["choices"] for g in result}
    done, visiting = set(), set()

    def visit(name):
        if name in {"DIRECT", "REJECT"} or name in done:
            return
        if name not in graph:
            raise ConfigError(f"分组引用不存在: {name}")
        if name in visiting:
            raise ConfigError(f"分组存在循环引用: {name}")
        visiting.add(name)
        for child in graph[name]:
            visit(child)
        visiting.remove(name)
        done.add(name)

    for name in graph:
        visit(name)
    return result


class Project:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.policy = load_yaml(self.root / "settings/policy.yaml")
        _keys(self.policy, {"version", "publish", "group_templates", "groups", "routes"}, set(), "policy")
        if type(self.policy["version"]) is not int or self.policy["version"] != 1:
            raise ConfigError("不支持的配置版本")
        _keys(self.policy["publish"], {"base_url"}, set(), "publish")
        self.base_url = check_url(self.policy["publish"]["base_url"], base=True)
        self.groups = expand_groups(self.policy)
        self.rules: dict[str, RuleList] = {}
        paths = (self.root / "rules").rglob("*.list")
        for path in sorted(paths, key=lambda item: item.relative_to(self.root / "rules").as_posix()):
            if not path.resolve().is_relative_to(self.root / "rules"):
                raise ConfigError(f"规则文件越出 rules 目录: {path}")
            relative = path.relative_to(self.root / "rules").as_posix()
            if PurePosixPath(relative).parts[0] not in {"Ruleset", "BlockAD"}:
                raise ConfigError(f"规则目录必须位于 Ruleset 或 BlockAD: {relative}")
            self.rules[relative] = parse_rules(path.read_text(encoding="utf-8-sig"), relative)
        if not self.rules:
            raise ConfigError("rules 目录没有规则文件")
        self.routes = self.policy["routes"]
        self._validate_routes()
        self._validate_vendor_lock()
        self.dns = load_yaml(self.root / "settings/dns.yaml")
        self._validate_dns()

    def _validate_routes(self):
        if not isinstance(self.routes, list) or not self.routes:
            raise ConfigError("routes 必须是非空列表")
        names = {group["name"] for group in self.groups} | {"DIRECT", "REJECT"}
        seen = set()
        for index, route in enumerate(self.routes):
            _keys(route, {"target"}, {"file", "url", "rule"}, f"路由 {index + 1}")
            if not isinstance(route["target"], str) or route["target"] not in names:
                raise ConfigError(f"路由 {index + 1}: 目标分组不存在")
            sources = set(route) - {"target"}
            if len(sources) != 1:
                raise ConfigError(f"路由 {index + 1}: file/url/rule 必须且只能选一个")
            key = next(iter(sources))
            value = route[key]
            if not isinstance(value, str):
                raise ConfigError(f"路由 {index + 1}: 来源必须是字符串")
            if key == "file" and value not in self.rules:
                raise ConfigError(f"路由 {index + 1}: 文件不存在（区分大小写）: {value}")
            if key == "url":
                check_url(value)
            if key == "rule" and not re.fullmatch(r"FINAL|GEOIP,[A-Z]{2}(?:,no-resolve)?", value):
                raise ConfigError(f"路由 {index + 1}: 不支持的内置规则 {value}")
            if (key, value) in seen:
                raise ConfigError(f"路由 {index + 1}: 重复来源 {value}")
            seen.add((key, value))
            if value == "FINAL" and index != len(self.routes) - 1:
                raise ConfigError("FINAL 必须位于最后一条路由")
        if self.routes[-1].get("rule") != "FINAL":
            raise ConfigError("缺少最后的 FINAL 兜底规则")
        used = {route["file"] for route in self.routes if "file" in route}
        unused = set(self.rules) - used
        if unused:
            raise ConfigError("存在未引用的规则文件: " + ", ".join(sorted(unused)))

    def _validate_vendor_lock(self):
        manifest_path = self.root / "settings/acl4ssr.yaml"
        lock_path = self.root / "settings/acl4ssr-lock.json"
        if not manifest_path.exists() and not lock_path.exists():
            return
        if not manifest_path.exists() or not lock_path.exists():
            raise ConfigError("ACL4SSR 清单或锁定文件缺失")
        manifest = load_yaml(manifest_path)
        try:
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ConfigError(f"ACL4SSR 锁定文件无效: {exc}") from exc
        if (
            not isinstance(lock, dict) or lock.get("commit") != manifest.get("commit")
            or lock.get("repository") != manifest.get("repository")
            or not isinstance(manifest.get("files"), list)
            or not isinstance(lock.get("files"), list)
        ):
            raise ConfigError("ACL4SSR 清单与锁定文件不一致")
        mapping = {item["file"]: item["source"] for item in manifest["files"]}
        locked = {item["file"]: item for item in lock["files"]}
        if len(mapping) != len(manifest["files"]) or len(locked) != len(lock["files"]) or set(mapping) != set(locked):
            raise ConfigError("ACL4SSR 文件映射缺失或重复")
        used = {route["file"] for route in self.routes if "file" in route}
        for name, source in mapping.items():
            if name not in used or name not in self.rules or locked[name]["source"] != source:
                raise ConfigError(f"ACL4SSR 规则未引用或来源不符: {name}")
            digest = sha256((self.root / "rules" / name).read_bytes()).hexdigest()
            if locked[name]["sha256"] != digest:
                raise ConfigError(f"ACL4SSR 规则与锁定校验值不符: {name}")

    def _validate_dns(self):
        if self.dns.get("enable") is not True or self.dns.get("enhanced-mode") != "fake-ip":
            raise ConfigError("本项目 DNS 配置必须启用 fake-ip")
        for field in ("fake-ip-filter", "default-nameserver", "nameserver", "proxy-server-nameserver"):
            values = self.dns.get(field)
            if not isinstance(values, list) or not values or not all(isinstance(v, str) and v for v in values):
                raise ConfigError(f"DNS {field}: 预期非空字符串列表")
            if len(values) != len(set(values)):
                raise ConfigError(f"DNS {field}: 有重复条目")
        required = {"telegram.org", "*.telegram.org", "t.me", "*.t.me", "telegram-cdn.org", "*.telegram-cdn.org"}
        if not required <= set(self.dns["fake-ip-filter"]):
            raise ConfigError("缺少 Telegram Fake-IP 例外，可能影响 OpenClaw 媒体下载")

    def summary(self):
        return {
            "rule_files": len(self.rules),
            "rules": sum(len(value.rules) for value in self.rules.values()),
            "duplicates_removed": sum(value.duplicates for value in self.rules.values()),
            "groups": len(self.groups),
            "routes": len(self.routes),
            "external_sources": sum("url" in route for route in self.routes),
        }

"""Read the legacy plain-list, Surge and Clash payload rule formats."""

from dataclasses import dataclass
from ipaddress import ip_network
import re

import yaml


class ConfigError(ValueError):
    """An actionable configuration error, suitable for CLI display."""


SUPPORTED = {
    "DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "IP-CIDR", "IP-CIDR6",
    "PROCESS-NAME", "USER-AGENT", "URL-REGEX",
}


@dataclass(frozen=True)
class RuleList:
    rules: tuple[str, ...]
    duplicates: int


def normalize_rule(text: str, location: str) -> str:
    kind, separator, rest = text.strip().partition(",")
    if not separator or kind not in SUPPORTED:
        raise ConfigError(f"{location}: 不支持的规则类型 {kind!r}")
    # Regex values may themselves contain commas, so do not split them.
    if kind == "URL-REGEX":
        if not rest.strip():
            raise ConfigError(f"{location}: 正则表达式为空")
        return f"{kind},{rest.strip()}"
    fields = [part.strip() for part in rest.split(",")]
    if not fields[0] or len(fields) > 2:
        raise ConfigError(f"{location}: 规则字段数量或值错误")
    if len(fields) == 2 and (
        fields[1] != "no-resolve" or kind not in {"IP-CIDR", "IP-CIDR6"}
    ):
        raise ConfigError(f"{location}: 规则列表不应包含策略或未知选项")
    if kind in {"IP-CIDR", "IP-CIDR6"}:
        try:
            network = ip_network(fields[0], strict=False)
        except ValueError as exc:
            raise ConfigError(f"{location}: 无效 CIDR {fields[0]!r}") from exc
        if network.version != (6 if kind == "IP-CIDR6" else 4):
            raise ConfigError(f"{location}: CIDR 地址族与规则类型不符")
    elif kind in {"DOMAIN", "DOMAIN-SUFFIX"}:
        if re.search(r"[\s/:]", fields[0]):
            raise ConfigError(f"{location}: 无效域名 {fields[0]!r}")
    return ",".join([kind, *fields])


def parse_rules(text: str, location: str = "rules") -> RuleList:
    """Normalize and deduplicate within a file, preserving first-match order."""
    text = text.lstrip("\ufeff")
    if any(line.strip() == "payload:" for line in text.splitlines()):
        try:
            document = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ConfigError(f"{location}: payload YAML 无效: {exc}") from exc
        if not isinstance(document, dict) or set(document) != {"payload"}:
            raise ConfigError(f"{location}: 预期只包含 payload 的规则文档")
        payload = document["payload"]
        if not isinstance(payload, list) or not all(isinstance(x, str) for x in payload):
            raise ConfigError(f"{location}: payload 必须是规则字符串列表")
        lines = enumerate(payload, 1)
    else:
        lines = enumerate(text.splitlines(), 1)
    output: dict[str, None] = {}
    duplicates = 0
    for number, line in lines:
        line = line.strip()
        if not line or line.startswith(("#", ";", "//")) or line == "[Rule]":
            continue
        rule = normalize_rule(line, f"{location}:{number}")
        if rule in output:
            duplicates += 1
        output[rule] = None
    if not output:
        raise ConfigError(f"{location}: 规则列表为空")
    return RuleList(tuple(output), duplicates)

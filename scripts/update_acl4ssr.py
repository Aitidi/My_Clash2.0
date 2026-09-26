"""Refresh the vendored ACL4SSR rules from one pinned Git commit.

Use --commit SHA to move to a new upstream snapshot. Downloads and validates all
files before changing the repository. Run from any directory after installing
the project, then rebuild and inspect the diff before committing.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

import yaml

from my_clash.rules import ConfigError, parse_rules


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "settings/acl4ssr.yaml"
LOCK = ROOT / "settings/acl4ssr-lock.json"
RAW = "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR"
MAX_BYTES = 10_000_000


def download(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "My-Clash-Config/2.0"})
    with urlopen(request, timeout=30) as response:
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ConfigError(f"上游文件超过 10 MB: {url}")
    return data


def refresh(commit: str | None = None) -> dict:
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    target_commit = commit or manifest["commit"]
    if not re.fullmatch(r"[0-9a-f]{40}", target_commit):
        raise ConfigError("需要完整的 40 位上游提交 SHA")
    entries = manifest["files"]
    if not isinstance(entries, list) or len(entries) != len({item["file"] for item in entries}):
        raise ConfigError("上游文件清单为空或有重复目标路径")
    content = {}
    locked = []
    for item in entries:
        source = item["source"]
        destination = item["file"]
        path = ROOT / "rules" / destination
        if (
            not source.startswith("Clash/") or not source.endswith(".list")
            or not path.resolve().is_relative_to(ROOT / "rules")
            or not destination.endswith(".list")
        ):
            raise ConfigError(f"不合法的上游映射: {item}")
        data = download(f"{RAW}/{target_commit}/{source}")
        parsed = parse_rules(data.decode("utf-8-sig"), source)
        content[path] = data
        locked.append({"source": source, "file": destination, "sha256": sha256(data).hexdigest(), "rules": len(parsed.rules)})
    license_bytes = download(f"{RAW}/{target_commit}/LICENCE")
    content[ROOT / "third_party/ACL4SSR-LICENCE"] = license_bytes
    for path, data in content.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    if commit:
        manifest["commit"] = target_commit
        MANIFEST.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8", newline="\n")
    lock = {"repository": manifest["repository"], "commit": target_commit, "license": "CC-BY-SA-4.0", "files": locked}
    LOCK.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"commit": target_commit, "files": len(locked), "rules": sum(item["rules"] for item in locked)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", help="新的 ACL4SSR 完整提交 SHA；不指定则重取已锁定版本")
    args = parser.parse_args()
    print(json.dumps(refresh(args.commit), ensure_ascii=False))

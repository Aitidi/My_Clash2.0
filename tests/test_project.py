from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import yaml

from my_clash.build import build, render, render_ini
from my_clash.model import Project, expand_groups, load_yaml
from my_clash.rules import ConfigError, parse_rules


ROOT = Path(__file__).resolve().parents[1]


class RegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project = Project(ROOT)

    def test_all_legacy_groups_and_default_choices_preserved_exactly(self):
        original = (ROOT / "tests/fixtures/my_config.ini").read_text(encoding="utf-8-sig")
        old = [line for line in original.splitlines() if line.startswith("custom_proxy_group=")]
        new = [line for line in render_ini(self.project, self.project.base_url).splitlines() if line.startswith("custom_proxy_group=")]
        self.assertEqual(old, new)
        self.assertEqual(len(new), 27)

    def test_route_order_only_changes_documented_broken_and_duplicate_entries(self):
        old = (ROOT / "tests/fixtures/my_config.ini").read_text(encoding="utf-8-sig")
        manifest = load_yaml(ROOT / "settings/acl4ssr.yaml")
        imported = {"https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/" + item["source"]: item["file"] for item in manifest["files"]}
        normalized = []
        seen = set()
        for line in old.splitlines():
            if not line.startswith("ruleset="):
                continue
            line = line.replace("/refs/heads/", "/")
            if line.endswith("/Ruleset/aitidi.list"):
                continue
            source = line.split(",", 1)[1]
            if source in seen:
                continue
            seen.add(source)
            if source in imported:
                target = line.split("=", 1)[1].split(",", 1)[0]
                line = f"ruleset={target},{self.project.base_url}/{imported[source]}"
            else:
                line = line.replace("/Aitidi/My_Clash/main/", "/Aitidi/My_Clash2.0/main/")
            normalized.append(line)
        new = [line for line in render_ini(self.project, self.project.base_url).splitlines() if line.startswith("ruleset=")]
        self.assertEqual(normalized, new)

    def test_dns_only_removes_duplicate_entries(self):
        old = yaml.safe_load((ROOT / "tests/fixtures/dns_config.yaml").read_text(encoding="utf-8"))
        old["fake-ip-filter"] = list(dict.fromkeys(old["fake-ip-filter"]))
        self.assertEqual(old, self.project.dns)

    def test_only_referenced_files_remain_and_package_preserves_source(self):
        self.assertEqual(len(self.project.rules), 40)
        self.assertEqual(list(self.project.rules), sorted(self.project.rules))
        self.assertEqual(set(self.project.rules), {route["file"] for route in self.project.routes if "file" in route})
        output = render(self.project)
        for name, value in self.project.rules.items():
            with self.subTest(name=name):
                parsed = parse_rules(output[name].decode("utf-8"))
                self.assertEqual(parsed, value)
                self.assertEqual(output[name], (ROOT / name).read_bytes())
        catalog = json.loads(output["Config/catalog.json"])
        self.assertEqual(len(catalog["files"]), 40)
        self.assertEqual(catalog["summary"]["rules"], 55305)
        self.assertEqual(catalog["summary"]["external_sources"], 0)

    def test_build_is_deterministic_and_check_does_not_write(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            expected = render(self.project)
            self.assertEqual(len(build(self.project, path, check=True)), len(expected))
            self.assertEqual(list(path.iterdir()), [])
            build(self.project, path)
            self.assertEqual(build(self.project, path), [])
            self.assertEqual(build(self.project, path, check=True), [])
            changed = path / "Ruleset/Aitidi.list"
            changed.write_text("DOMAIN,tampered.example\n", encoding="utf-8")
            self.assertEqual(build(self.project, path, check=True), ["Ruleset/Aitidi.list"])
            self.assertIn("tampered", changed.read_text())

    def test_override_base_url_updates_all_rule_references(self):
        output = render_ini(self.project, "http://127.0.0.1:8000")
        self.assertIn("http://127.0.0.1:8000/Ruleset/Aitidi.list", output)
        self.assertIn("http://127.0.0.1:8000/Ruleset/ProxyGFWlist.list", output)
        self.assertNotIn("githubusercontent.com/Aitidi", output)
        self.assertNotIn("githubusercontent.com/ACL4SSR/", output)

    def test_vendored_rules_match_locked_upstream_snapshot(self):
        lock = json.loads((ROOT / "settings/acl4ssr-lock.json").read_text(encoding="utf-8"))
        self.assertEqual(len(lock["files"]), 23)
        self.assertTrue((ROOT / "third_party/ACL4SSR-LICENCE").is_file())
        self.assertEqual({entry["file"] for entry in lock["files"]} <= set(self.project.rules), True)

    def test_lock_rejects_modified_vendored_rule(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            shutil.copytree(ROOT / "settings", root / "settings")
            shutil.copytree(ROOT / "Ruleset", root / "Ruleset")
            shutil.copytree(ROOT / "BlockAD", root / "BlockAD")
            path = root / "Ruleset/Google.list"
            path.write_bytes(path.read_bytes() + b"\nDOMAIN,tampered.example\n")
            with self.assertRaisesRegex(ConfigError, "锁定校验值"):
                Project(root)

    def test_build_refuses_source_directory(self):
        for directory in ("Ruleset", "BlockAD", "settings", "tests", ".git"):
            with self.subTest(directory=directory), self.assertRaises(ConfigError):
                build(self.project, ROOT / directory)

    def test_stale_outputs_are_reported_without_deleting(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / "Ruleset").mkdir()
            stale = path / "Ruleset/Old.list"
            stale.write_text("DOMAIN,old.example")
            with self.assertRaisesRegex(ConfigError, "过期"):
                build(self.project, path)
            self.assertTrue(stale.exists())


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        shutil.copytree(ROOT / "settings", self.root / "settings")
        (self.root / "settings/acl4ssr.yaml").unlink()
        (self.root / "settings/acl4ssr-lock.json").unlink()
        self.policy = load_yaml(self.root / "settings/policy.yaml")
        self.policy["routes"] = [{"target": "加速", "file": "Ruleset/Test.list"}, {"target": "漏网之鱼", "rule": "FINAL"}]
        (self.root / "Ruleset").mkdir(parents=True)
        (self.root / "Ruleset/Test.list").write_text("DOMAIN,test.example\n", encoding="utf-8")

    def project(self):
        (self.root / "settings/policy.yaml").write_text(yaml.safe_dump(self.policy, allow_unicode=True), encoding="utf-8")
        return Project(self.root)

    def test_missing_or_wrong_case_local_file(self):
        self.policy["routes"][0]["file"] = "Ruleset/test.list"
        with self.assertRaisesRegex(ConfigError, "区分大小写"):
            self.project()

    def test_unused_rule_file_rejected(self):
        (self.root / "Ruleset/Unused.list").write_text("DOMAIN,unused.example\n", encoding="utf-8")
        with self.assertRaisesRegex(ConfigError, "未引用"):
            self.project()

    def test_route_requires_one_source(self):
        self.policy["routes"][0]["url"] = "https://example.com/a.list"
        with self.assertRaisesRegex(ConfigError, "只能选一个"):
            self.project()

    def test_missing_target(self):
        self.policy["routes"][0]["target"] = "不存在"
        with self.assertRaisesRegex(ConfigError, "目标分组不存在"):
            self.project()

    def test_duplicate_route(self):
        self.policy["routes"].insert(0, deepcopy(self.policy["routes"][0]))
        with self.assertRaisesRegex(ConfigError, "重复来源"):
            self.project()

    def test_final_must_be_last(self):
        self.policy["routes"].reverse()
        with self.assertRaisesRegex(ConfigError, "FINAL"):
            self.project()

    def test_group_cycles_and_missing_references(self):
        for choices in (["加速"], ["不存在"]):
            policy = deepcopy(self.policy)
            policy["groups"][0]["choices"] = choices
            with self.subTest(choices=choices), self.assertRaises(ConfigError):
                expand_groups(policy)

    def test_invalid_regex(self):
        self.policy["groups"][1]["filter"] = "("
        with self.assertRaisesRegex(ConfigError, "表达式"):
            self.project()

    def test_unknown_field_prevents_silent_typo(self):
        self.policy["groups"][0]["choice"] = ["DIRECT"]
        with self.assertRaisesRegex(ConfigError, "未知字段"):
            self.project()

    def test_non_string_group_type_is_an_actionable_error(self):
        self.policy["groups"][0]["type"] = []
        with self.assertRaisesRegex(ConfigError, "不支持的类型"):
            self.project()

    def test_duplicate_yaml_keys(self):
        path = self.root / "duplicate.yaml"
        path.write_text("groups: []\ngroups: []\n")
        with self.assertRaisesRegex(ConfigError, "字段重复"):
            load_yaml(path)

    def test_missing_telegram_exception(self):
        path = self.root / "settings/dns.yaml"
        dns = load_yaml(path)
        dns["fake-ip-filter"].remove("t.me")
        path.write_text(yaml.safe_dump(dns), encoding="utf-8")
        with self.assertRaisesRegex(ConfigError, "Telegram"):
            self.project()

    def test_invalid_base_url_rejected_before_any_output(self):
        for url in ("file:///tmp", "https://user:pass@example.com", "https://example.com?token=secret", "https://example.com\n[custom]"):
            with self.subTest(url=url), self.assertRaises(ConfigError):
                render(self.project(), url)

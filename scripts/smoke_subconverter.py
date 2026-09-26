"""Optional end-to-end check against a running local subconverter.

Run from the repository root after installing the project. Uses synthetic SOCKS5
nodes; no real subscription or proxy connection is needed. All referenced rules
are served from this repository's generated files.
"""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
from threading import Thread
from urllib.parse import urlencode
from urllib.request import urlopen

import yaml

from my_clash.build import build
from my_clash.model import Project


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:25500")
    args = parser.parse_args()
    project = Project(Path(__file__).resolve().parents[1])
    with tempfile.TemporaryDirectory(prefix="my-clash-smoke-") as folder:
        root = Path(folder)

        class QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=folder))
        base = f"http://127.0.0.1:{server.server_port}"
        build(project, root, base_url=base)
        names = ["香港", "日本", "美国", "台湾", "新加坡", "韩国", "法国", "英国", "其他测试"]
        proxies = [{"name": name, "type": "socks5", "server": "127.0.0.1", "port": 9} for name in names]
        (root / "subscription.yaml").write_text(yaml.safe_dump({"proxies": proxies}, allow_unicode=True), encoding="utf-8")
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            query = urlencode({
                "target": "clash", "new_name": "true", "emoji": "false", "expand": "true",
                "url": base + "/subscription.yaml", "config": base + "/Config/my_config.ini",
            })
            with urlopen(args.endpoint.rstrip("/") + "/sub?" + query, timeout=120) as response:
                result = yaml.safe_load(response.read().decode("utf-8-sig"))
            groups = result["proxy-groups"]
            assert [group["name"] for group in groups] == [group["name"] for group in project.groups]
            allowed = {group["name"] for group in groups} | {proxy["name"] for proxy in result["proxies"]} | {"DIRECT", "REJECT"}
            for group in groups:
                assert group["proxies"], f"Empty group: {group['name']}"
                assert set(group["proxies"]) <= allowed, f"Unresolved group: {group['name']}"
            rules = result["rules"]
            assert rules[-1] == "MATCH,漏网之鱼", rules[-1]
            for expected in ("DOMAIN,aitidi.fun,Aitidi", "DOMAIN-SUFFIX,linux.do,直连", "PROCESS-NAME,boghma-app.exe,直连"):
                assert expected in rules, f"Missing rule: {expected}"
            assert any(rule.endswith(",Google") for rule in rules)
            assert len(rules) > 40000, "External ad/privacy rules missing or truncated"
            print(json.dumps({"groups": len(groups), "proxies": len(result["proxies"]), "rules": len(rules), "result": "passed"}, ensure_ascii=False))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    main()

"""Command-line entry points; no tokens or subscription URLs are required."""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys

from .build import build
from .model import Project
from .network import check_sources
from .rules import ConfigError


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description="My_Clash 规则校验与配置生成工具")
    cli.add_argument("--root", type=Path, default=Path.cwd(), help="仓库根目录，默认当前目录")
    commands = cli.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="校验配置、分组引用和所有规则（离线）")
    commands.add_parser("stats", help="输出规则统计（JSON）")
    compiler = commands.add_parser("build", help="生成兼容原路径的 INI、DNS 和规则列表")
    compiler.add_argument("--output", type=Path, help="输出目录，默认仓库根目录")
    compiler.add_argument("--base-url", help="生成规则 URL 的根地址")
    compiler.add_argument("--check", action="store_true", help="检查产物是否过期，不写文件")
    server = commands.add_parser("serve", help="构建并在回环地址提供配置，供本机 subconverter 使用")
    server.add_argument("--port", type=int, default=8000)
    network = commands.add_parser("check-sources", help="联网检查所有外部规则地址及内容")
    network.add_argument("--timeout", type=float, default=15)
    return cli


def main(argv: list[str] | None = None) -> int:
    # Redirected Windows consoles may default to an ANSI code page. Keep CLI
    # output UTF-8 just like the configuration files, including argparse help.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parser().parse_args(argv)
    try:
        project = Project(args.root)
        if args.command in {"validate", "stats"}:
            print(json.dumps(project.summary(), ensure_ascii=False, indent=2))
        elif args.command == "build":
            changed = build(project, args.output or project.root, base_url=args.base_url, check=args.check)
            if args.check and changed:
                print("生成产物缺失或过期:\n" + "\n".join(changed), file=sys.stderr)
                return 1
            print(f"{'检查通过' if args.check else '生成完成'}；变更文件: {len(changed)}")
        elif args.command == "check-sources":
            if args.timeout <= 0:
                raise ConfigError("timeout 必须大于 0")
            results = check_sources(project, args.timeout)
            print(json.dumps(results, ensure_ascii=False, indent=2))
            return int(any(not result["ok"] for result in results))
        elif args.command == "serve":
            if not 1 <= args.port <= 65535:
                raise ConfigError("port 必须在 1 到 65535 之间")
            output = project.root / "dist/local"
            base = f"http://127.0.0.1:{args.port}"
            build(project, output, base_url=base)
            handler = partial(SimpleHTTPRequestHandler, directory=str(output))
            with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
                print(f"本机转换配置: {base}/Config/my_config.ini", flush=True)
                print("Ctrl+C 停止；修改源文件后请重启以重新生成。", flush=True)
                server.serve_forever()
    except (ConfigError, OSError, ValueError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0
    return 0

"""Explicit network checks; ordinary builds and tests remain offline."""

from concurrent.futures import ThreadPoolExecutor
from urllib.error import URLError
from urllib.request import Request, urlopen

from .model import Project
from .rules import ConfigError, parse_rules


def check_sources(project: Project, timeout: float = 15) -> list[dict]:
    urls = sorted({route["url"] for route in project.routes if "url" in route})

    def check(url):
        try:
            request = Request(url, headers={"User-Agent": "My-Clash-Config/2.0"})
            with urlopen(request, timeout=timeout) as response:
                content = response.read(10_000_001)
            if len(content) > 10_000_000:
                raise ConfigError("响应超过 10 MB 限制")
            parsed = parse_rules(content.decode("utf-8-sig"), url)
            return {"url": url, "ok": True, "rules": len(parsed.rules)}
        except (URLError, OSError, UnicodeError, ConfigError) as exc:
            return {"url": url, "ok": False, "error": str(exc)}

    with ThreadPoolExecutor(max_workers=6) as pool:
        return list(pool.map(check, urls))

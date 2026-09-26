import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ConsoleTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "my_clash", *args], cwd=ROOT,
            env={**os.environ, "PYTHONIOENCODING": "ascii"},
            capture_output=True, encoding="utf-8", timeout=30,
        )

    def test_help_works_with_legacy_console_encoding(self):
        result = self.run_cli("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("校验", result.stdout)

    def test_check_failure_is_readable_and_does_not_write(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.run_cli("build", "--check", "--output", folder)
            self.assertEqual(result.returncode, 1)
            self.assertIn("生成产物缺失或过期", result.stderr)
            self.assertNotIn("codec", result.stderr)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_success_message_works_with_legacy_console_encoding(self):
        result = self.run_cli("build", "--check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("检查通过", result.stdout)

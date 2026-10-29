#!/usr/bin/env python3
"""check-ui.mjs 的离线回归：用临时 fixture 验证阻塞项与通过项。

依赖本机 Chrome/Chromium 与 Node >= 22；缺失时跳过，不伪造 PASS。
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "check-ui.mjs")


def find_chrome():
    env = os.environ.get("CHROME")
    if env and os.path.isfile(env):
        return env
    for p in (
        "/home/ctyun/.local/bin/google-chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
    ):
        if os.path.isfile(p):
            return p
    return None


NODE = shutil.which("node")
CHROME = find_chrome()


@unittest.skipUnless(NODE and CHROME, "需要 Node >= 22 与本机 Chrome/Chromium")
class CheckUiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="dw-check-ui-test-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, name, body):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)
        return "file://" + path

    def run_check(self, *urls):
        cmd = [NODE, SCRIPT]
        for url in urls:
            cmd.extend(["--url", url])
        cmd.extend(["--tap", "48", "--font-min", "12", "--chrome", CHROME])
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return proc, json.loads(proc.stdout)

    def test_good_page_passes(self):
        url = self.write(
            "good.html",
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<style>body{margin:0;width:460px;font-size:16px}"
            "button{height:48px;width:120px}</style></head>"
            "<body><button>ok</button><p>正文</p></body></html>",
        )
        proc, data = self.run_check(url)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(data["unit"], "css-px")
        self.assertTrue(data["allPass"])
        self.assertTrue(data["reports"][0]["pass"])

    def test_bad_page_reports_all_blockers(self):
        url = self.write(
            "bad.html",
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<style>body{margin:0;width:460px}"
            ".bad{height:30px;width:120px}.tiny{font-size:10px}"
            ".wide{width:600px;height:20px}</style></head><body>"
            "<button class='bad'>矮按钮</button>"
            "<p class='tiny'>小字</p><div class='wide'>溢出</div>"
            "<script>console.error('boom')</script></body></html>",
        )
        proc, data = self.run_check(url)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        report = data["reports"][0]
        self.assertFalse(report["pass"])
        self.assertEqual(len(report["tap"]["failures"]), 1)
        self.assertEqual(len(report["font"]["failures"]), 1)
        self.assertTrue(report["overflow"]["fail"])
        self.assertTrue(report["consoleErrors"])

    def test_missing_file_is_not_a_pass(self):
        proc, data = self.run_check("file://" + os.path.join(self.tmp, "nope.html"))
        self.assertEqual(proc.returncode, 1, proc.stderr)
        report = data["reports"][0]
        self.assertFalse(report["pass"])
        self.assertTrue(report["loadError"])


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""check-ui.mjs 的离线回归：用临时 fixture 验证阻塞项、采集项与账本行为。

依赖本机 Chrome/Chromium 与 Node >= 22；缺失时跳过，不伪造 PASS。
账本一律写到临时 DESIGNWISE_HOME，不碰用户主目录。
"""
import base64
import functools
import http.server
import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "check-ui.mjs")

# 1x1 透明 PNG：用于「相对路径引图但加载成功」的黄灯用例
PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg=="
)


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


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    """测试用静态服务：不打印访问日志，避免污染用例输出。"""

    def log_message(self, *args):
        pass


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

    def run_check(self, *urls, extra=()):
        cmd = [NODE, SCRIPT]
        for url in urls:
            cmd.extend(["--url", url])
        cmd.extend(["--tap", "48", "--font-min", "12", "--chrome", CHROME])
        cmd.extend(extra)
        env = dict(os.environ)
        env["DESIGNWISE_HOME"] = os.path.join(self.tmp, "home")
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, env=env)
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

    def clean_page(self, name, body, style=""):
        return self.write(
            name,
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<style>body{margin:0;width:460px;font-size:16px;background:#fff;color:#111}"
            + style + "</style></head><body>" + body + "</body></html>",
        )

    def test_broken_image_blocks(self):
        url = self.clean_page("broken.html", "<p>正文</p><img src='missing.png' alt='破图'>")
        proc, data = self.run_check(url)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        report = data["reports"][0]
        self.assertFalse(report["pass"])
        self.assertEqual(report["images"]["broken"], 1)
        self.assertEqual(report["images"]["failures"][0]["alt"], "破图")
        self.assertIn("relative-asset", [w["code"] for w in report["warnings"]])

    def test_relative_image_is_yellow_only(self):
        with open(os.path.join(self.tmp, "px.png"), "wb") as fh:
            fh.write(PNG_1PX)
        url = self.clean_page("rel.html", "<p>正文</p><img src='px.png' alt='一像素'>")
        proc, data = self.run_check(url)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = data["reports"][0]
        self.assertTrue(report["pass"])
        self.assertEqual(report["images"]["loaded"], 1)
        self.assertTrue(report["images"]["anyRelativeRef"])
        self.assertIn("relative-asset", [w["code"] for w in report["warnings"]])

    def test_low_contrast_blocks(self):
        url = self.clean_page("lowcontrast.html", "<p class='low'>看不清的字</p>", ".low{color:#B9B9B9}")
        proc, data = self.run_check(url)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        report = data["reports"][0]
        self.assertFalse(report["pass"])
        failures = report["contrast"]["failures"]
        self.assertEqual(len(failures), 1)
        self.assertLess(failures[0]["ratio"], 4.5)
        self.assertEqual(failures[0]["required"], 4.5)
        self.assertFalse(failures[0]["large"])

    def test_contrast_uses_large_text_threshold(self):
        url = self.clean_page(
            "large.html",
            "<p class='mid'>正常字号</p><p class='mid big'>大字标题</p>",
            ".mid{color:#8C8C8C}.big{font-size:30px}",
        )
        proc, data = self.run_check(url)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        failures = data["reports"][0]["contrast"]["failures"]
        self.assertEqual(len(failures), 1)
        self.assertFalse(failures[0]["large"])
        self.assertEqual(failures[0]["label"], "正常字号")

    def test_fingerprint_is_stable_and_distinguishes(self):
        body = ("<h1>标题</h1><div class='card'><span>a</span><span>b</span></div>"
                "<p>正文</p><button style='height:48px;width:120px'>ok</button>")
        style = ".card{background:#F2F4F8;border-radius:12px;padding:8px}"
        first, data_first = self.run_check(self.clean_page("fp1.html", body, style))
        second, data_a = self.run_check(self.clean_page("fp2.html", body, style))
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        fp_a = data_a["reports"][0]["fingerprint"]
        # 同样的 DOM/CSS 换文件名 → 指纹必须一致（否则账本比较没有意义）
        self.assertEqual(fp_a, data_first["reports"][0]["fingerprint"])
        self.assertEqual(fp_a["bg"], "#FFFFFF")
        self.assertTrue(fp_a["palette"])
        self.assertIn("display", fp_a["fonts"])
        self.assertIsInstance(fp_a["skeleton"]["columns"], int)

        dark_url = self.write(
            "fp3.html",
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<style>body{margin:0;width:460px;font-size:16px;background:#0B0F19;color:#F5E663}"
            ".g{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;height:80vh}"
            ".g div{background:#1B2233;padding:8px}</style></head><body>"
            "<div class='g'><div><span>a</span><span>b</span></div><div>c</div><div>d</div></div>"
            "</body></html>",
        )
        proc, data_b = self.run_check(dark_url)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        fp_b = data_b["reports"][0]["fingerprint"]
        self.assertEqual(fp_b["bg"], "#0B0F19")
        self.assertEqual(fp_b["skeleton"]["columns"], 3)

    def test_ledger_warns_without_changing_exit_code(self):
        url = self.clean_page(
            "ledger.html",
            "<h1>标题</h1><p>正文</p><div class='card'><span>a</span><span>b</span></div>"
            "<button style='height:48px;width:120px'>ok</button>",
            ".card{background:#F2F4F8;border-radius:12px;padding:8px}",
        )
        added, data_add = self.run_check(url, extra=["--ledger-add", "probe"])
        self.assertEqual(added.returncode, 0, added.stderr)
        self.assertEqual(len(data_add["ledger"]["added"]), 1)

        again, data_same = self.run_check(url, extra=["--ledger-check"])
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn("ledger-family", [w["code"] for w in data_same["reports"][0]["warnings"]])
        self.assertTrue(data_same["ledger"]["matches"])

        other = self.write(
            "ledger-dark.html",
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<style>body{margin:0;width:460px;font-size:16px;background:#0B0F19;color:#F5E663}"
            ".g{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;height:80vh}"
            ".g div{background:#1B2233;padding:8px}</style></head><body>"
            "<div class='g'><div><span>a</span><span>b</span></div><div>c</div><div>d</div></div>"
            "</body></html>",
        )
        proc, data_other = self.run_check(other, extra=["--ledger-check"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("ledger-family", [w["code"] for w in data_other["reports"][0]["warnings"]])

    def test_ledger_query_without_url(self):
        proc, data = self.run_check(extra=["--ledger", "5"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(data["mode"], "ledger")
        self.assertIsNone(data["allPass"])
        self.assertEqual(data["reports"], [])

    def test_ledger_strips_query_and_hash(self):
        url = self.clean_page("ledger-url.html", "<h1>标题</h1><p>正文</p>")
        dirty = url + "?token=SECRET123&sig=abc#frag"
        proc, data = self.run_check(dirty, extra=["--ledger-add", "probe"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        path = os.path.join(self.tmp, "home", "ledger.jsonl")
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
        self.assertNotIn("SECRET123", raw, "账本不得保存查询串（可能含 token）")
        self.assertNotIn("sig=abc", raw)
        self.assertNotIn("frag", raw)
        entry = json.loads(raw.splitlines()[0])
        self.assertEqual(entry["url"], url)

        proc, data = self.run_check(extra=["--ledger", "5"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        shown = json.dumps(data, ensure_ascii=False)
        self.assertNotIn("SECRET123", shown, "查询输出同样不得回显查询串")

    def test_ledger_strips_url_credentials(self):
        # 账本只用来认交付：URL 里的 user:pass@（basic auth 凭据）不得落盘，
        # added 回显的也必须是实际写入的地址，而不是原始 URL。
        name = "ledger-cred.html"
        self.write(
            name,
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<style>body{margin:0;width:460px;font-size:16px}"
            "button{height:48px;width:120px}</style></head>"
            "<body><button>ok</button><p>正文</p></body></html>",
        )
        server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0),
            functools.partial(_QuietHandler, directory=self.tmp),
        )
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            base = f"http://127.0.0.1:{server.server_port}/{name}"
            dirty = (f"http://user-marker:pass-marker@127.0.0.1:{server.server_port}"
                     f"/{name}?token=SECRET123#frag")
            proc, data = self.run_check(dirty, extra=["--ledger-add", "probe"])
        finally:
            server.shutdown()
            server.server_close()
        self.assertEqual(proc.returncode, 0, proc.stderr)

        with open(os.path.join(self.tmp, "home", "ledger.jsonl"), encoding="utf-8") as fh:
            raw = fh.read()
        for secret in ("user-marker", "pass-marker", "SECRET123", "frag"):
            self.assertNotIn(secret, raw, f"账本不得保存 {secret}")
        self.assertEqual(json.loads(raw.splitlines()[0])["url"], base)

        added = json.dumps(data["ledger"]["added"], ensure_ascii=False)
        for secret in ("user-marker", "pass-marker", "SECRET123"):
            self.assertNotIn(secret, added, "added 回显的应是实际落盘的地址")
        self.assertEqual(data["ledger"]["added"][0]["url"], base)

    @unittest.skipUnless(os.name == "posix", "POSIX 权限位仅在 POSIX 平台可测")
    def test_ledger_file_and_dir_are_private(self):
        url = self.clean_page("ledger-perm.html", "<h1>标题</h1><p>正文</p>")
        home = os.path.join(self.tmp, "home")
        proc, _ = self.run_check(url, extra=["--ledger-add", "probe"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(os.stat(home).st_mode & 0o777, 0o700)
        self.assertEqual(os.stat(os.path.join(home, "ledger.jsonl")).st_mode & 0o777, 0o600)

        # 已存在的宽松权限也要被收紧
        path = os.path.join(home, "ledger.jsonl")
        os.chmod(path, 0o644)
        proc, _ = self.run_check(url, extra=["--ledger-add", "probe"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)

    def test_ledger_does_not_store_page_copy_or_screenshots(self):
        marker = "CONFIDENTIAL-MARKER-9f2"
        url = self.clean_page(
            "ledger-privacy.html",
            f"<h1>标题</h1><p>{marker}</p><button style='height:48px;width:120px'>ok</button>",
        )
        proc, data = self.run_check(url, extra=["--ledger-add", "probe"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        with open(os.path.join(self.tmp, "home", "ledger.jsonl"), encoding="utf-8") as fh:
            raw = fh.read()
        self.assertNotIn(marker, raw, "账本不得保存页面正文")
        entry = json.loads(raw.splitlines()[0])
        self.assertEqual(
            sorted(entry.keys()),
            ["fingerprint", "project", "title", "ts", "url"],
            "账本字段集应保持最小：时间/项目/地址/标题/指纹",
        )
        self.assertEqual(data["reports"][0].get("shot"), None,
                         "未指定 --shot 时不得落盘截图")

    def test_shot_writes_png_and_requires_single_url(self):
        url = self.clean_page("shot.html", "<h1>标题</h1><p>正文</p>")
        out = os.path.join(self.tmp, "shots", "page.png")
        proc, data = self.run_check(url, extra=["--shot", out])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(data["reports"][0]["shot"].get("error"))
        with open(out, "rb") as fh:
            self.assertEqual(fh.read(8), b"\x89PNG\r\n\x1a\n")

        second = self.clean_page("shot2.html", "<p>二</p>")
        cmd = [NODE, SCRIPT, "--url", url, "--url", second, "--shot", out, "--chrome", CHROME]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("--shot", proc.stderr)


if __name__ == "__main__":
    unittest.main()

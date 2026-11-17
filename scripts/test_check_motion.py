#!/usr/bin/env python3
"""check-motion.py 的离线回归：静态扫描的阻断项、提示项与加载指示例外。

只证明脚本能识别可机械核对的事实，不证明真实动效质量。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "check-motion.py")

REDUCE = "@media (prefers-reduced-motion: reduce){*,*::before,*::after{transition-duration:1ms !important;animation-duration:1ms !important}}"
TOKENS = ":root{--motion-duration-s:150ms;--motion-duration-xl:380ms}"

GOOD = f"""<!doctype html><html><head><style>
{TOKENS}
{REDUCE}
.card{{transition:transform var(--motion-duration-s) cubic-bezier(.2,0,0,1),opacity 120ms}}
.card:active{{transform:scale(.97)}}
.sheet{{transition:transform 300ms cubic-bezier(.05,.7,.1,1)}}
@keyframes enter{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:none}}}}
.enter{{animation:enter 200ms cubic-bezier(0,0,0,1) both}}
</style></head><body><div class="card">x</div></body></html>"""

BAD = f"""<!doctype html><html><head><style>
.card{{transition:width 800ms ease-in-out,opacity 200ms;animation:spin 2s infinite}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
</style></head><body><div class="card">x</div></body></html>"""

STATIC = """<!doctype html><html><head><style>.a{color:#111}</style></head><body>x</body></html>"""

COMMA = f"""<!doctype html><html><head><style>
{TOKENS}
{REDUCE}
.x{{transition:opacity 200ms,width 800ms}}
</style></head><body></body></html>"""

VAR_LONG = f"""<!doctype html><html><head><style>
:root{{--motion-duration-xl:900ms}}
{REDUCE}
.x{{transition:transform var(--motion-duration-xl) linear}}
</style></head><body></body></html>"""

INLINE = f"""<!doctype html><html><head><style>{REDUCE}</style></head><body>
<div style="transition: width 800ms"></div>
<script>const s={{transition:'width 800ms'}};</script>
</body></html>"""

LOADING = f"""<!doctype html><html><head><style>
{TOKENS}
{REDUCE}
.skeleton{{background:linear-gradient(90deg,#eee,#fff);animation:shimmer 900ms linear infinite}}
@keyframes shimmer{{0%{{background-position:100% 0}}100%{{background-position:-100% 0}}}}
</style></head><body><div class="skeleton"></div></body></html>"""

LOADING_1200 = f"""<!doctype html><html><head><style>
{TOKENS}
{REDUCE}
.skeleton{{animation:shimmer 1200ms linear infinite}}
@keyframes shimmer{{0%{{opacity:.4}}100%{{opacity:1}}}}
</style></head><body><div class="skeleton"></div></body></html>"""

KEYFRAME_LATE = f"""<!doctype html><html><head><style>
{TOKENS}
{REDUCE}
.x{{animation:move 200ms ease-out both}}
@keyframes move{{from{{opacity:1}}to{{width:100%}}}}
</style></head><body><div class="x"></div></body></html>"""

ALL_PROP = f"""<!doctype html><html><head><style>
{TOKENS}
{REDUCE}
.x{{transition:all 200ms ease}}
</style></head><body><div class="x"></div></body></html>"""


class CheckMotionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="dw-motion-test-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, name, body):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)
        return path

    def run_check(self, path, *extra):
        return subprocess.run([sys.executable, SCRIPT, path, "--json", *extra],
                              capture_output=True, text=True, timeout=60)

    def codes(self, proc):
        return {f["code"] for f in json.loads(proc.stdout)["findings"]}

    def test_good_motion_passes(self):
        proc = self.run_check(self.write("good.html", GOOD))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        data = json.loads(proc.stdout)
        self.assertTrue(data["has_reduced_motion"])
        self.assertTrue(data["has_motion"])
        self.assertEqual(data["errors"], 0)

    def test_missing_reduce_and_overlong_animation_blocks(self):
        proc = self.run_check(self.write("bad.html", BAD))
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        codes = self.codes(proc)
        self.assertIn("motion_no_reduce", codes)
        self.assertIn("motion_too_long", codes)
        self.assertIn("motion_infinite", codes)
        self.assertIn("motion_layout_property", codes)

    def test_comma_segments_and_vars_are_parsed(self):
        proc = self.run_check(self.write("comma.html", COMMA))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("motion_layout_property", self.codes(proc))
        proc = self.run_check(self.write("var.html", VAR_LONG))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("motion_long", self.codes(proc))

    def test_inline_and_js_style_objects_are_scanned(self):
        proc = self.run_check(self.write("inline.html", INLINE))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        data = json.loads(proc.stdout)
        self.assertGreaterEqual(data["motion_rules"], 2)
        self.assertIn("motion_layout_property", self.codes(proc))

    def test_loading_loop_is_info_not_blocking(self):
        proc = self.run_check(self.write("loading.html", LOADING), "--strict")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        codes = self.codes(proc)
        self.assertIn("motion_loading_loop", codes)
        self.assertNotIn("motion_infinite", codes)

    def test_loading_at_1200ms_is_allowed(self):
        proc = self.run_check(self.write("loading1200.html", LOADING_1200), "--strict")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("motion_loading_long", self.codes(proc))

    def test_layout_property_in_later_keyframe_step_is_detected(self):
        proc = self.run_check(self.write("keyframe-late.html", KEYFRAME_LATE))
        self.assertIn("motion_layout_property", self.codes(proc))

    def test_transition_all_is_warned(self):
        proc = self.run_check(self.write("all.html", ALL_PROP))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("motion_all_property", self.codes(proc))

    def test_static_page_warns_but_passes(self):
        proc = self.run_check(self.write("static.html", STATIC))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        data = json.loads(proc.stdout)
        self.assertFalse(data["has_motion"])
        self.assertIn("motion_none", {f["code"] for f in data["findings"]})

    def test_strict_turns_warnings_into_failure(self):
        proc = self.run_check(self.write("static.html", STATIC), "--strict")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)

    def test_missing_file_is_usage_error(self):
        proc = self.run_check(os.path.join(self.tmp, "nope.html"))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("找不到文件", proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python3
"""test_render_narration.py — render-narration.sh 的离线行为测试。

不调用真实渲染 / ffmpeg：把脚本复制到临时目录，用 stub 的 render-video.js 与
mix-voiceover.sh 验证参数解析、路径引用、中间产物保护与退出码。
运行：python3 scripts/test_render_narration.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "render-narration.sh")

RENDER_STUB = r'''
const fs = require("fs");
const path = require("path");
const html = process.argv[2];
if (!html) process.exit(9);
const base = path.basename(html, ".html");
fs.writeFileSync(path.join(path.dirname(html), base + ".mp4"), "silent");
'''

MIX_STUB = r'''#!/usr/bin/env bash
set -e
out=""
for a in "$@"; do
  case "$a" in --out=*) out="${a#*=}" ;; esac
done
[ -n "$out" ] || { echo "missing --out" >&2; exit 9; }
printf 'final' > "$out"
'''


class NarrationScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp(prefix="render_narration_test_")
        cls.bin = os.path.join(cls.root, "bin")
        os.makedirs(cls.bin)
        cls.script = os.path.join(cls.bin, "render-narration.sh")
        shutil.copyfile(SCRIPT, cls.script)
        with open(os.path.join(cls.bin, "render-video.js"), "w", encoding="utf-8") as fh:
            fh.write(RENDER_STUB)
        with open(os.path.join(cls.bin, "mix-voiceover.sh"), "w", encoding="utf-8") as fh:
            fh.write(MIX_STUB)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def project(self, name="proj", duration=2, timeline_name="timeline.json",
                voiceover=True):
        path = os.path.join(self.root, name)
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, "demo.html"), "w", encoding="utf-8") as fh:
            fh.write("<html></html>")
        timeline = os.path.join(path, timeline_name)
        with open(timeline, "w", encoding="utf-8") as fh:
            json.dump({"totalDuration": duration}, fh)
        if voiceover:
            with open(os.path.join(path, "voiceover.mp3"), "wb") as fh:
                fh.write(b"fake")
        return path, timeline

    def run_script(self, *args, cwd=None):
        return subprocess.run(
            ["bash", self.script] + list(args), cwd=cwd or self.root,
            text=True, capture_output=True, timeout=30,
        )

    def test_missing_html_exits_1(self):
        r = self.run_script()
        self.assertEqual(r.returncode, 1)
        self.assertIn("Usage", r.stderr)

    def test_missing_timeline_exits_1(self):
        path, _ = self.project("no_timeline")
        r = self.run_script(os.path.join(path, "demo.html"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("--timeline", r.stderr)

    def test_invalid_timeline_json_exits_1(self):
        path, timeline = self.project("bad_json")
        with open(timeline, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        r = self.run_script(os.path.join(path, "demo.html"), f"--timeline={timeline}")
        self.assertEqual(r.returncode, 1)
        self.assertIn("无法解析", r.stderr)

    def test_invalid_duration_exits_1(self):
        path, timeline = self.project("bad_duration", duration="abc")
        r = self.run_script(os.path.join(path, "demo.html"), f"--timeline={timeline}")
        self.assertEqual(r.returncode, 1)
        self.assertIn("totalDuration 非法", r.stderr)

    def test_zero_duration_exits_1(self):
        path, timeline = self.project("zero_duration", duration=0)
        r = self.run_script(os.path.join(path, "demo.html"), f"--timeline={timeline}")
        self.assertEqual(r.returncode, 1)
        self.assertIn("totalDuration 非法", r.stderr)

    def test_boolean_and_array_duration_exit_1(self):
        for name, value in (("bool_duration", True), ("array_duration", [10])):
            path, timeline = self.project(name, duration=value)
            r = self.run_script(os.path.join(path, "demo.html"), f"--timeline={timeline}")
            self.assertEqual(r.returncode, 1, name)
            self.assertIn("totalDuration 类型非法", r.stderr)

    def test_numeric_string_duration_is_accepted(self):
        path, timeline = self.project("string_duration", duration="10")
        r = self.run_script(os.path.join(path, "demo.html"), f"--timeline={timeline}")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_missing_voiceover_exits_1(self):
        path, timeline = self.project("no_voice", voiceover=False)
        r = self.run_script(os.path.join(path, "demo.html"), f"--timeline={timeline}")
        self.assertEqual(r.returncode, 1)
        self.assertIn("voiceover.mp3 不存在", r.stderr)

    def test_existing_intermediate_is_refused_and_preserved(self):
        path, timeline = self.project("existing")
        silent = os.path.join(path, "demo.mp4")
        with open(silent, "wb") as fh:
            fh.write(b"OLD")
        r = self.run_script(os.path.join(path, "demo.html"), f"--timeline={timeline}")
        self.assertEqual(r.returncode, 1)
        self.assertIn("中间产物已存在", r.stderr)
        with open(silent, "rb") as fh:
            self.assertEqual(fh.read(), b"OLD")

    def test_out_equal_to_intermediate_is_refused(self):
        path, timeline = self.project("same_out")
        r = self.run_script(os.path.join(path, "demo.html"), f"--timeline={timeline}",
                            f"--out={os.path.join(path, 'demo.mp4')}")
        self.assertEqual(r.returncode, 1)
        self.assertIn("不能覆盖输入或中间文件", r.stderr)

    def test_out_cannot_overwrite_inputs(self):
        path, timeline = self.project("overwrite_inputs")
        for target in (os.path.join(path, "voiceover.mp3"),
                       os.path.join(path, "demo.html"),
                       timeline):
            r = self.run_script(os.path.join(path, "demo.html"),
                                f"--timeline={timeline}", f"--out={target}")
            self.assertEqual(r.returncode, 1, target)
            self.assertIn("不能覆盖输入或中间文件", r.stderr)
        bgm = os.path.join(path, "bgm.mp3")
        with open(bgm, "wb") as fh:
            fh.write(b"fake bgm")
        r = self.run_script(os.path.join(path, "demo.html"),
                            f"--timeline={timeline}", f"--bgm={bgm}", f"--out={bgm}")
        self.assertEqual(r.returncode, 1)
        self.assertIn("不能覆盖输入或中间文件", r.stderr)

    def test_symlinked_output_dir_cannot_bypass_protection(self):
        path, timeline = self.project("symlink_out")
        link = os.path.join(self.root, "link_to_symlink_out")
        os.symlink(path, link)
        r = self.run_script(os.path.join(path, "demo.html"), f"--timeline={timeline}",
                            f"--out={os.path.join(link, 'demo.mp4')}")
        self.assertEqual(r.returncode, 1)
        self.assertIn("不能覆盖输入或中间文件", r.stderr)

    def test_symlink_output_is_refused(self):
        path, timeline = self.project("symlink_file_out")
        link = os.path.join(path, "out-link.mp4")
        os.symlink(os.path.join(path, "demo.mp4"), link)  # 悬空链接
        r = self.run_script(os.path.join(path, "demo.html"), f"--timeline={timeline}",
                            f"--out={link}")
        self.assertEqual(r.returncode, 1)
        self.assertIn("不能是符号链接", r.stderr)

    def test_missing_output_dir_exits_1(self):
        path, timeline = self.project("missing_outdir")
        r = self.run_script(os.path.join(path, "demo.html"), f"--timeline={timeline}",
                            "--out=no-such-dir/out.mp4")
        self.assertEqual(r.returncode, 1)
        self.assertIn("输出目录不存在", r.stderr)

    def test_unknown_argument_exits_1(self):
        path, timeline = self.project("unknown_arg")
        r = self.run_script(os.path.join(path, "demo.html"), f"--timeline={timeline}",
                            "--bogus")
        self.assertEqual(r.returncode, 1)
        self.assertIn("未知参数", r.stderr)

    def test_success_exit_code_and_output(self):
        path, timeline = self.project("success")
        r = self.run_script(os.path.join(path, "demo.html"), f"--timeline={timeline}")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isfile(os.path.join(path, "demo-narrated.mp4")))
        self.assertFalse(os.path.exists(os.path.join(path, "demo.mp4")),
                         "默认应清理本次创建的中间产物")

    def test_keep_silent_preserves_intermediate(self):
        path, timeline = self.project("keep_silent")
        r = self.run_script(os.path.join(path, "demo.html"), f"--timeline={timeline}",
                            "--keep-silent")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isfile(os.path.join(path, "demo.mp4")))
        self.assertTrue(os.path.isfile(os.path.join(path, "demo-narrated.mp4")))

    def test_custom_out_path(self):
        path, timeline = self.project("custom_out")
        out = os.path.join(path, "custom.mp4")
        r = self.run_script(os.path.join(path, "demo.html"), f"--timeline={timeline}",
                            f"--out={out}")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isfile(out))

    def test_paths_with_spaces_and_quotes(self):
        path, timeline = self.project("proj with space", timeline_name="timeline'quote.json")
        r = self.run_script(os.path.join(path, "demo.html"), f"--timeline={timeline}")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isfile(os.path.join(path, "demo-narrated.mp4")))

    def test_timeline_name_cannot_inject_javascript(self):
        # 旧实现把 $TIMELINE 拼进 node -e 字符串；这里用带 JS 片段的文件名回归。
        name = "x');require('fs').writeFileSync('pwned','x');x='.json"
        path, timeline = self.project("injection", timeline_name=name)
        r = self.run_script(os.path.join(path, "demo.html"), f"--timeline={timeline}",
                            cwd=path)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(os.path.join(path, "pwned")),
                         "timeline 路径不得被当作 JS 代码执行")


if __name__ == "__main__":
    unittest.main(verbosity=2)

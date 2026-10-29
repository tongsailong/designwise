#!/usr/bin/env python3
"""design-gate-hook-hyperframes.sh 的离线回归（不执行渲染）。"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "design-gate-hook-hyperframes.sh")


class HyperframesHookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp(prefix="design_gate_hf_test_")
        cls.logdir = tempfile.mkdtemp(prefix="design_gate_hf_log_")
        cls.long = os.path.join(cls.root, "long")
        cls.gate = os.path.join(cls.root, "gate")
        cls.short = os.path.join(cls.root, "short")
        for path, duration, has_gate in (
            (cls.long, "60", False),
            (cls.gate, "60", True),
            (cls.short, "30", False),
        ):
            os.makedirs(path)
            with open(os.path.join(path, "index.html"), "w", encoding="utf-8") as fh:
                fh.write('<html data-duration="%s"></html>' % duration)
            if has_gate:
                with open(os.path.join(path, "direction-approved.md"), "w",
                          encoding="utf-8") as fh:
                    fh.write("用户确认：方向 C\n")
        with open(os.path.join(cls.long, "run-hf.sh"), "w", encoding="utf-8") as fh:
            fh.write("#!/bin/bash\nnpx hyperframes render --duration=60\n")

        # Scaffolded HyperFrames projects pin the CLI in package.json scripts;
        # `npm run render` is an official invocation path.
        def pkg(name, duration, gate=False, body="npx hyperframes@0.8.33 render --fps 60"):
            path = os.path.join(cls.root, name)
            os.makedirs(path)
            with open(os.path.join(path, "index.html"), "w", encoding="utf-8") as fh:
                fh.write('<html data-duration="%s"></html>' % duration)
            with open(os.path.join(path, "package.json"), "w", encoding="utf-8") as fh:
                json.dump({"scripts": {
                    "render": body,
                    "check": "npx hyperframes check",
                    "build": "echo hi",
                }}, fh)
            if gate:
                with open(os.path.join(path, "direction-approved.md"), "w",
                          encoding="utf-8") as fh:
                    fh.write("用户确认：方向 C\n")
            return path

        cls.pkg = pkg("pkg", "60")
        cls.pkg_gate = pkg("pkg_gate", "60", gate=True)
        cls.pkg_short = pkg("pkg_short", "30")
        cls.pkg_local = pkg("pkg_local", "60",
                            body="node scripts/render-video.js")
        cls.mono_sub = pkg("mono/sub", "60")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)
        shutil.rmtree(cls.logdir, ignore_errors=True)

    def run_hook(self, command, cwd=None):
        payload = json.dumps({"cwd": cwd or self.long,
                              "tool_input": {"command": command}})
        env = dict(os.environ, DESIGN_GATE_LOG_DIR=self.logdir)
        proc = subprocess.run(["bash", HOOK], input=payload, text=True,
                              capture_output=True, timeout=20, env=env)
        self.last_stderr = proc.stderr
        return proc.returncode

    def check(self, command, expected, note, cwd=None):
        actual = self.run_hook(command, cwd)
        print(f"{'PASS' if actual == expected else 'FAIL'} exp={expected} "
              f"got={actual} :: {note} :: {command!r}")
        self.assertEqual(actual, expected, note)

    def test_normal_commands_pass(self):
        self.check("for f in *.png; do echo \"$f\"; done", 0, "plain loop")
        self.check("while read -r n r; do npx playwright screenshot "
                   "--viewport-size=460,960 \"file:///tmp/$n\" \"$r\"; done",
                   0, "screenshot loop")
        self.check("for f in a b; do node scripts/check-ui.mjs --url "
                   "\"file:///tmp/$f.html\"; done", 0, "check-ui loop")
        self.check("APK=$(ls -t app/build/outputs/apk/debug/*.apk | head -1); "
                   "bash ~/.zcode/skills/app-testing/runtime/mi6-verify/"
                   "adb-auto-install.sh \"$APK\"", 0, "APK install")
        self.check("while true; do npm test; break; done", 0, "npm test loop")
        self.check("npm test", 0, "test runner")
        self.check("git status", 0, "git status")
        self.check("echo hyperframes render", 0,
                   "the words in an echo are not a render")
        self.check("node scripts/render-video.js out.html --duration=60", 0,
                   "designwise renderer is entry-layer protected")

    def test_read_only_script_inspection_passes(self):
        """Reading or searching a .sh is data access, not an execution request."""
        for command in (
            f"cat {HOOK}",
            "cat run-hf.sh",
            "head -n 5 run-hf.sh",
            "tail -n 5 run-hf.sh",
            "grep -n render run-hf.sh",
            "rg render run-hf.sh",
            "sed -n '1,5p' run-hf.sh",
            "awk '/render/' run-hf.sh",
        ):
            self.check(command, 0, "read-only inspection", cwd=self.long)

    def test_unclassified_file_commands_stay_conservative(self):
        """Non-read-only commands keep the fail-closed content scan."""
        self.check("cp run-hf.sh /tmp/out.sh", 2,
                   "unclassified file operation is still scanned", cwd=self.long)

    def test_hyperframes_long_render_blocks(self):
        self.check("npx hyperframes render --duration=60", 2, "direct npx")
        self.check("hyperframes render", 2, "global binary")
        self.check("hyperframes@0.8.33 render", 2, "pinned global binary")
        self.check("timeout 120 hyperframes render", 2, "timeout wrapper")
        self.check("cd . && hyperframes render", 2, "cd chain")
        self.check("bash -c 'npx hyperframes render --duration=60'", 2,
                   "bash -c wrapper")
        self.check("npm exec hyperframes -- render --duration=60", 2,
                   "npm exec")
        self.check("bash run-hf.sh", 2, "local wrapper script")
        self.check("sh run-hf.sh", 2, "sh wrapper script")
        self.check("source run-hf.sh", 2, "source wrapper script")
        self.check(". run-hf.sh", 2, "dot-source wrapper script")
        self.check("./run-hf.sh", 2, "direct invocation")
        self.check("cat run-hf.sh && hyperframes render --duration=60", 2,
                   "read-only prefix does not bypass a render chain")

    def test_npm_script_paths(self):
        """Scaffolded projects use `npm run render` to invoke hyperframes."""
        self.check("npm run render", 2, "npm run render -> hyperframes",
                   cwd=self.pkg)
        self.check("npm run render", 0, "gate present", cwd=self.pkg_gate)
        self.check("npm run render", 0, "short render", cwd=self.pkg_short)
        self.check("npm run check", 0, "check script is not a render",
                   cwd=self.pkg)
        self.check("npm run build", 0, "unrelated script", cwd=self.pkg)
        self.check("yarn render", 2, "yarn short form", cwd=self.pkg)
        self.check("pnpm render", 2, "pnpm short form", cwd=self.pkg)
        self.check("yarn install", 0, "unrelated yarn command", cwd=self.pkg)
        mono = os.path.dirname(self.mono_sub)
        self.check("npm --prefix sub run render", 2,
                   "npm --prefix resolves the target package.json", cwd=mono)
        self.check("pnpm -C sub run render", 2,
                   "pnpm -C resolves the target package.json", cwd=mono)
        self.check("npm run render", 0,
                   "designwise renderer is entry-layer protected",
                   cwd=self.pkg_local)

    def test_short_and_gate_pass(self):
        self.check("npx hyperframes render --duration=30", 0, "short render")
        self.check("npx hyperframes render --duration=60", 0, "gate present",
                   cwd=self.gate)

    def test_unknown_duration(self):
        no_index = os.path.join(self.root, "no-index")
        os.makedirs(no_index, exist_ok=True)
        self.check("npx hyperframes render", 2, "unknown duration no gate",
                   cwd=no_index)
        self.check("grep hyperframes docs/render.md", 0,
                   "mention in a read-only grep")

    def test_skip_env(self):
        for command in (
            "SKIP_DESIGN_GATE=1 npx hyperframes render --duration=60",
            "env SKIP_DESIGN_GATE=1 npx hyperframes render --duration=60",
            "export SKIP_DESIGN_GATE=1; npx hyperframes render --duration=60",
        ):
            payload = json.dumps({"cwd": self.long,
                                  "tool_input": {"command": command}})
            env = dict(os.environ, DESIGN_GATE_LOG_DIR=self.logdir)
            proc = subprocess.run(["bash", HOOK], input=payload, text=True,
                                  capture_output=True, timeout=20, env=env)
            self.assertEqual(proc.returncode, 0,
                             f"explicit skip must pass: {command!r}")
        self.check("npx hyperframes render --duration=60 # SKIP_DESIGN_GATE=1",
                   2, "skip in a comment is not honored")


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""design-gate-hook.sh 的离线回归测试（不执行任何渲染）。

运行：
    python3 scripts/test_design_gate_hook.py
    DESIGN_GATE_HOOK=/path/to/old-hook python3 scripts/test_design_gate_hook.py

每个 PASS/FAIL 行都记录实际被测 Hook 的 SHA-256；测试只创建临时目录，
不修改项目文件，不联网，不调用 Copilot，不安装依赖。
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_HOOK = os.path.join(HERE, "design-gate-hook.sh")
HOOK = os.environ.get("DESIGN_GATE_HOOK", DEFAULT_HOOK)


def hook_sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class GateHookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hook_sha = hook_sha(HOOK)
        cls.root = tempfile.mkdtemp(prefix="design_gate_hook_test_")
        cls.fixtures = {}

        def mk(name, duration="60", gate=False):
            path = os.path.join(cls.root, name)
            os.makedirs(path, exist_ok=True)
            if duration is not None:
                with open(os.path.join(path, "index.html"), "w", encoding="utf-8") as fh:
                    fh.write('<html data-duration="%s"></html>' % duration)
            if gate:
                with open(os.path.join(path, "direction-approved.md"), "w", encoding="utf-8") as fh:
                    fh.write("approved\n")
            return path

        cls.long = mk("long")
        cls.gate = mk("gate", gate=True)
        cls.short = mk("short", "30")
        cls.noindex = mk("noindex", None)
        cls.other = mk("other")
        cls.rootdir = mk("rootdir")
        # Gate in the current dir / one / two / three levels up.
        cls.parent_gate = mk("parent_gate", gate=True)
        cls.nested1 = os.path.join(cls.parent_gate, "sub")
        cls.nested2 = os.path.join(cls.nested1, "deep")
        cls.nested3 = os.path.join(cls.nested2, "deeper")
        for p in (cls.nested1, cls.nested2, cls.nested3):
            os.makedirs(p, exist_ok=True)
        cls.gate_space = mk("gate with space", gate=True)
        cls.gate_quote = mk("gate'quote", gate=True)
        cls.fixtures.update(long=cls.long, gate=cls.gate, short=cls.short,
                            noindex=cls.noindex, other=cls.other, rootdir=cls.rootdir)

        def write(name, text):
            path = os.path.join(cls.root, name)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            return path

        cls.wrap = write("wrap.sh", "npm run render\n")
        cls.text_script = write("text.sh", "echo npm run render\n")
        cls.t60 = write("t60.json", json.dumps({"totalDuration": 60}))
        cls.t30 = write("t30.json", json.dumps({"totalDuration": 30}))
        cls.t44 = write("t44.json", json.dumps({"totalDuration": 44.2}))
        cls.tbad = write("tbad.json", json.dumps({"totalDuration": "bad"}))
        cls.npm = shutil.which("npm") or "npm"
        cls.node = shutil.which("node") or "node"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def run_hook(self, command, cwd):
        payload = {"cwd": cwd, "tool_input": {"command": command}}
        return self.run_raw(json.dumps(payload))

    def run_raw(self, raw):
        proc = subprocess.run(
            ["bash", HOOK], input=raw, text=True,
            capture_output=True, timeout=20,
        )
        self.last_stderr = proc.stderr
        return proc.returncode

    def check(self, command, cwd, expected, note="", reason=None):
        actual = self.run_hook(command, cwd)
        ok = actual == expected
        status = "PASS" if ok else "FAIL"
        print(f"{status} sha256={self.hook_sha[:16]} exp={expected} got={actual} "
              f":: {note} :: {command!r}")
        self.assertEqual(actual, expected,
                         f"{note}: expected {expected}, got {actual}; command={command!r}")
        if reason is not None:
            self.assertIn(reason, self.last_stderr or "",
                          f"{note}: missing reason substring {reason!r}")

    # ---- Independent regression matrix: false positives / paths / malformed input ----
    def test_readonly_composites_are_not_blocked(self):
        self.check(
            f'for d in "." "{self.long}" "{self.gate}"; do echo "== $d =="; '
            f'(cd "$d" && find . -type f -print0 | xargs -0 sha256sum); done',
            self.long, 0, "read-only hash loop with cd must not block")
        self.check(f'for f in a b; do cd "{self.long}"; sha256sum "$f"; done',
                   self.long, 0, "read-only for loop with cd")
        self.check('python3 - <<PY\nfor i in range(3):\n    print(i)\nPY',
                   self.long, 0, "for inside python heredoc")
        self.check('echo "# npm run render"', self.long, 0, "quoted render text")
        self.check('# npm run render\necho hi', self.long, 0, "comment-only render text")
        self.check('grep -R "npm run render" .', self.long, 0, "grep text")
        self.check('find . -name "*.md" -print0 | xargs -0 sha256sum',
                   self.long, 0, "find/xargs read-only")
        self.check('printf "%s\\n" "npm run render"', self.long, 0, "printf text")

    def test_gate_paths_and_quoting(self):
        self.check(f'cd "{self.gate}" && npm run render', self.long, 0,
                   "quoted gated cd")
        self.check(f'cd "{self.long}" && npm run render', self.gate, 2,
                   "quoted ungated cd")
        self.check('cd sub && npm run render', self.parent_gate, 0,
                   "gate one level up")
        self.check('cd deep && npm run render', self.nested1, 0,
                   "gate two levels up")
        self.check('cd deeper && npm run render', self.nested2, 2,
                   "gate three levels up is outside the search range")
        self.check(f'cd "{self.gate_space}" && npm run render', self.long, 0,
                   "gate path with space")
        self.check(f"cd '{self.gate_quote}' && npm run render", self.long, 0,
                   "gate path with quote")

    def test_skip_scope_and_comments(self):
        self.check("SKIP_DESIGN_GATE=1 npm run render", self.long, 0,
                   "leading assignment skip")
        self.check("env SKIP_DESIGN_GATE=1 npm run render", self.long, 0,
                   "env skip")
        self.check("SKIP_DESIGN_GATE=1; npm run render", self.long, 2,
                   "standalone assignment is not exported")
        self.check("npm run render; SKIP_DESIGN_GATE=1", self.long, 2,
                   "skip after render does not apply")
        self.check("npm run render # SKIP_DESIGN_GATE=1", self.long, 2,
                   "skip in a comment is not honored")
        self.check("echo SKIP_DESIGN_GATE=1; npm run render", self.long, 2,
                   "skip as text is not honored")

    def test_control_flow_still_blocks_when_render_reachable(self):
        self.check(
            f'for d in "{self.long}" "{self.gate}"; do cd "$d"; npm run render; done',
            self.rootdir, 2, "unresolved loop that can render blocks")
        self.check(f'if [ -d x ]; then cd "{self.gate}"; fi; npm run render',
                   self.long, 2, "nonliteral branch cd blocks")

    def test_malformed_input(self):
        self.assertEqual(self.run_raw("not json"), 2, "invalid JSON must fail closed")
        self.assertEqual(self.run_raw(json.dumps({"cwd": self.long})), 0,
                         "missing command is empty input")
        self.assertEqual(self.run_raw(json.dumps({"cwd": self.long,
                                                  "tool_input": {"command": 123}})), 0,
                         "non-string command is treated as empty/non-render")

    # ---- P1-1: explicit duration and renderer defaults ----
    def test_duration_explicit_after_flags(self):
        self.check(f"{self.node} scripts/render-video.js out.html --fps=60 --duration=60",
                   self.short, 2, "node fps then explicit long")
        self.check("npm run render -- --fps=60 --duration=60", self.short, 2,
                   "npm fps then explicit long")
        self.check(f"{self.node} scripts/render-video-seek.js out.html --width=1920 --duration=60",
                   self.noindex, 2, "seek width then explicit long")
        self.check(f"{self.node} scripts/render-video.js out.html --width=1920 --duration=60",
                   self.noindex, 2, "width then explicit long")
        self.check(f"{self.node} scripts/render-video.js out.html --keep-chrome --duration=60",
                   self.noindex, 2, "keep-chrome then explicit long")

    def test_duration_priority_and_defaults(self):
        self.check("npm run render -- --duration=60", self.short, 2,
                   "explicit long wins over short data-duration")
        self.check("npm run render -- --duration=30", self.long, 0,
                   "explicit short wins over long data-duration")
        self.check("npm run render -- --fps=60 --duration=30", self.short, 0,
                   "explicit short after fps")
        self.check('npm run render -- --label "--duration=10"', self.long, 0,
                   "renderer scans --duration= inside label value")
        self.check("npm run render -- -- --duration=10", self.long, 0,
                   "explicit short after --")
        self.check(f"{self.node} scripts/render-video.js out.html", self.noindex, 0,
                   "render-video.js source default 30s")
        self.check(f"{self.node} scripts/render-video.js out.html", self.long, 0,
                   "render-video.js ignores data-duration; default 30s")
        self.check(f"{self.node} scripts/render-video.js out.html --duration=60",
                   self.long, 2, "explicit render-video duration")
        for form in ("1e2", "+60", "60abc", "' 60'"):
            self.check(f"{self.node} scripts/render-video.js out.html --duration={form}",
                       self.long, 2, f"parseFloat duration form {form}")
        for form in ("$((60))", "$(echo 60)"):
            self.check(f"{self.node} scripts/render-video.js out.html --duration={form}",
                       self.long, 2, f"unresolved duration form {form}")
        self.check('node "$JS" out.html --duration=60', self.long, 2,
                   "dynamic node script path")
        self.check('bash "$SCRIPT"', self.long, 2,
                   "dynamic bash script path")
        self.check('source "$SCRIPT"', self.long, 2,
                   "dynamic sourced script path")
        self.check('"$C" out.html; npm run render', self.gate, 2,
                   "dynamic command name fails closed")
        self.check('node scripts/render-video.js out.html "$ARGS"', self.long, 2,
                   "dynamic render args")
        self.check("npm run render", self.noindex, 2,
                   "unknown npm script duration is fail-closed")
        self.check("hyperframes render", self.noindex, 2,
                   "hyperframes unknown duration is fail-closed")
        self.check("npm run render -- --duration=30", self.noindex, 0,
                   "explicit short with no index")

    def test_narration_timeline(self):
        self.check("bash render-narration.sh demo.html", self.long, 0,
                   "missing timeline does not render")
        self.check(f"bash render-narration.sh demo.html --timeline={self.t60}",
                   self.long, 2, "timeline 60 + 1s buffer")
        self.check(f"bash render-narration.sh demo.html --timeline={self.t30}",
                   self.long, 0, "timeline 30 + 1s buffer")
        self.check(f"bash render-narration.sh demo.html --timeline={self.t44}",
                   self.long, 2, "timeline 44.2 -> record 46")
        self.check(f"bash render-narration.sh demo.html --timeline={self.tbad}",
                   self.long, 2, "invalid timeline fails closed")
        self.check(f"source render-narration.sh demo.html --timeline={self.t60}",
                   self.long, 2, "source narration timeline")
        self.check(f"./render-narration.sh demo.html --timeline={self.t60}",
                   self.long, 2, "direct narration timeline")

    # ---- P1-2: npm/pnpm/yarn target directories ----
    def test_npm_workspace_targets(self):
        self.check("npm run render --workspace other", self.gate, 2,
                   "workspace after script is unresolved")
        self.check("npm run render -w other", self.gate, 2,
                   "-w after script is unresolved")
        self.check("npm run render -wother", self.gate, 2,
                   "attached -w after script is unresolved")
        self.check("npm run render --workspace=other", self.gate, 2,
                   "workspace= after script is unresolved")
        self.check("npm run render --workspaces", self.gate, 2,
                   "all workspaces is unresolved")
        self.check("npm run render -ws", self.gate, 2,
                   "npm -ws shorthand is unresolved")
        self.check("npm run -- render --workspace other", self.gate, 0,
                   "npm run -- script args are not npm workspace")
        self.check(f"npm run -- render --prefix {self.long}", self.gate, 0,
                   "npm run -- script args are not npm prefix")
        self.check("npm run render --workspaces=true", self.gate, 2,
                   "npm boolean workspaces assignment is unresolved")
        self.check("npm run render --include-workspace-root=true", self.gate, 2,
                   "npm boolean include-workspace-root is unresolved")
        self.check("npm -- run render", self.long, 2,
                   "npm -- before command still runs render")
        self.check(f"npm --prefix {self.other} -- run render", self.gate, 2,
                   "npm -- before command with ungated prefix")
        self.check("pnpm -- run render", self.long, 2,
                   "pnpm -- before command")
        self.check(f"npm run render --workspace other --prefix {self.gate}",
                   self.long, 2, "workspace unresolved even with gated prefix")
        self.check("npm run render --dry-run --workspace other", self.gate, 2,
                   "npm run does not honor dry-run; workspace still unresolved")
        self.check("npm run render --dry-run", self.long, 2,
                   "npm run ignores dry-run")

    def test_npm_prefix_targets(self):
        self.check(f"npm run render --prefix {self.other}", self.gate, 2,
                   "prefix after script targets ungated dir")
        self.check(f"npm run render --prefix {self.gate}", self.long, 0,
                   "prefix after script targets gated dir")
        self.check(f"npm run render --prefix {self.gate} --duration=60",
                   self.long, 0, "prefix gate + explicit long")
        self.check(f"npm run render -C{self.gate} --duration=60",
                   self.long, 2, "npm attached -C is not prefix; render stays in cwd")
        self.check(f"npm run render -C{self.gate} --duration=60",
                   self.gate, 0, "npm attached -C ignored; cwd gate allows")
        self.check(f"npm -C{self.gate} run render", self.long, 2,
                   "npm attached -C before command is not prefix")
        self.check(f"npm run render --prefix {self.long} --duration=60",
                   self.gate, 2, "prefix ungated + explicit long")
        self.check(f"npm --prefix {self.other} run render", self.gate, 2,
                   "npm --prefix before run")
        self.check(f"npm run render --cwd {self.gate}", self.long, 2,
                   "npm --cwd is not a target directory; current cwd is checked")

    def test_pnpm_yarn_targets(self):
        self.check(f"pnpm -C {self.gate} run render", self.long, 0,
                   "pnpm -C before script")
        self.check(f"pnpm --dir {self.gate} run render", self.long, 0,
                   "pnpm --dir before script")
        self.check(f"pnpm -C{self.gate} run render", self.long, 0,
                   "pnpm attached -C before script")
        self.check(f"pnpm -C{self.long} run render", self.gate, 2,
                   "pnpm attached -C to ungated target")
        self.check("pnpm -w run render", self.long, 2,
                   "pnpm workspace-root unresolved")
        self.check("pnpm --filter other run render", self.long, 2,
                   "pnpm filter unresolved")
        self.check(f"yarn --cwd {self.gate} render", self.long, 2,
                   "yarn target semantics unverified -> fail closed")
        self.check("yarn render --cwd /tmp/other", self.gate, 2,
                   "yarn post-script target flags fail closed (not tested)")

    # ---- P1-3: control flow and state pollution ----
    def test_control_flow_bypasses(self):
        self.check(f"cd {self.long} || cd {self.gate}; npm run render",
                   self.rootdir, 2, "successful left cd must not apply right cd")
        self.check(f"false && cd {self.gate}; npm run render", self.long, 2,
                   "dead && branch cd")
        self.check(f"true || cd {self.gate}; npm run render", self.long, 2,
                   "short-circuited || branch cd")
        self.check(f"if false; then cd {self.gate}; fi; npm run render",
                   self.long, 2, "dead if branch cd")
        self.check(f"while false; do cd {self.gate}; done; npm run render",
                   self.long, 2, "zero-iteration while cd")
        self.check(f"f() {{ cd {self.gate}; }}; npm run render",
                   self.long, 2, "uncalled function body cd")
        self.check("false && export SKIP_DESIGN_GATE=1; npm run render",
                   self.long, 2, "dead && export skip")
        self.check("if false; then export SKIP_DESIGN_GATE=1; fi; npm run render",
                   self.long, 2, "dead if export skip")
        self.check("export SKIP_DESIGN_GATE=1; export -n SKIP_DESIGN_GATE; npm run render",
                   self.long, 2, "export -n removes child env")
        self.check("export SKIP_DESIGN_GATE=1; env -uSKIP_DESIGN_GATE npm run render",
                   self.long, 2, "attached env -u removes child env")
        self.check(f"eval 'cd {self.long}'; npm run render", self.gate, 2,
                   "eval cd persists in current shell")
        self.check("eval 'export SKIP_DESIGN_GATE=1'; npm run render",
                   self.long, 0, "eval export persists in current shell")
        self.check(f"command cd {self.long}; npm run render", self.gate, 2,
                   "command cd persists in current shell")
        self.check("command export SKIP_DESIGN_GATE=1; npm run render",
                   self.long, 0, "command export persists in current shell")
        self.check(f"pushd {self.long}; npm run render", self.gate, 2,
                   "pushd changes current shell cwd")
        self.check(f"pushd {self.gate}; npm run render", self.long, 0,
                   "pushd to gated cwd")
        self.check(f"pushd {self.long}; popd; npm run render", self.gate, 0,
                   "popd restores gated cwd")
        self.check(f"g() {{ cd {self.long}; }}; f() {{ g; }}; f; npm run render",
                   self.gate, 2, "transitive function call is dangerous")
        for body in ("command npm run render", f"{self.npm} run render",
                     "timeout 10 npm run render", "X=1 npm run render",
                     '"npm" run render', "$NPM run render"):
            self.check(f"f() {{ {body}; }}; f", self.long, 2,
                       f"function body wrapper render: {body}")
        self.check(
            f"f() {{ command node scripts/render-video.js out.html --duration=60; }}; f",
            self.long, 2, "function body absolute node render")
        self.check(
            f"g() {{ command cd {self.long}; }}; f() {{ g; }}; f; npm run render",
            self.gate, 2, "wrapped transitive function cd")
        self.check("declare -x SKIP_DESIGN_GATE=1; npm run render",
                   self.long, 0, "declare -x exports skip")
        self.check("declare -x SKIP_DESIGN_GATE; SKIP_DESIGN_GATE=1; npm run render",
                   self.long, 0, "declare -x name-only exports later assignment")
        self.check("export SKIP_DESIGN_GATE=1; declare +x SKIP_DESIGN_GATE; npm run render",
                   self.long, 2, "declare +x unexports skip")
        self.check(f"HOME={self.gate}; cd ~ && npm run render", self.long, 0,
                   "cd ~ uses command HOME, not Hook process HOME")
        self.check(f"HOME={self.long}; cd ~ && npm run render", self.gate, 2,
                   "cd ~ to ungated command HOME")

    def test_control_flow_gate_legal(self):
        self.check(f"if false; then cd {self.long}; fi; npm run render",
                   self.gate, 0, "dead branch must not block gated cwd")
        self.check(f"while false; do cd {self.long}; done; npm run render",
                   self.gate, 0, "zero-iteration while must not block")
        self.check(f"f() {{ cd {self.long}; }}; npm run render", self.gate, 0,
                   "uncalled function must not block")
        self.check(f"for i in; do cd {self.long}; done; npm run render",
                   self.gate, 0, "empty for must not block")
        self.check(f"false && cd {self.gate}; npm run render", self.gate, 0,
                   "dead && branch leaves gated cwd")
        self.check(f"true || cd {self.gate}; npm run render", self.gate, 0,
                   "short-circuited || leaves gated cwd")
        self.check(f"cd {self.gate} && npm run render", self.long, 0,
                   "normal gated cd && render")
        self.check(f"cd {self.long} && npm run render", self.gate, 2,
                   "normal ungated cd && render")
        self.check("false && npm run render", self.long, 0,
                   "dead && render does not execute")
        self.check("true || npm run render", self.long, 0,
                   "short-circuited || render does not execute")
        self.check("if [ -d foo ]; then echo render; fi; npm run render",
                   self.gate, 0, "text render in unexecuted branch does not block")
        self.check("if [ -d foo ]; then echo cd; fi; npm run render",
                   self.gate, 0, "text cd argument in unexecuted branch does not block")
        self.check("function f() { echo hi; }; npm run render", self.gate, 0,
                   "function f() syntax is a definition, not a block")
        self.check(
            f"if true; then cd {self.gate}; else echo fi; cd {self.long}; fi; npm run render",
            self.gate, 0, "fi as an argument does not close the if block")

    def test_control_flow_cd_status(self):
        self.check(f"cd {self.gate} || cd {self.long}; npm run render",
                   self.gate, 0, "successful left cd skips right")
        self.check(f"cd /no/such/dir || cd {self.gate}; npm run render",
                   self.long, 0, "failed left cd executes gated right")
        self.check(f"cd /no/such/dir && cd {self.gate}; npm run render",
                   self.long, 2, "failed left cd skips right")
        self.check(f"cd {self.gate} && cd {self.long}; npm run render",
                   self.gate, 2, "both cd succeed; final is ungated")
        self.check(f"cd {self.gate} && cd /no/such/dir; npm run render",
                   self.long, 0, "failed second cd keeps gated cwd")

    def test_control_flow_literal_true(self):
        self.check(f"if true; then cd {self.gate}; fi; npm run render",
                   self.long, 0, "executed true branch cd")
        self.check(f"if true; then cd {self.long}; fi; npm run render",
                   self.gate, 2, "executed true branch cd to ungated")
        self.check(f"for i in; do cd {self.gate}; done; npm run render",
                   self.long, 2, "empty for leaves base cwd")
        self.check(f"case x in y) cd {self.gate};; esac; npm run render",
                   self.long, 2, "unresolved case fails closed")
        self.check("if [ -d foo ]; then echo hi; fi; npm run render",
                   self.long, 2, "nonliteral condition with plain body still checks render")
        self.check(f"if [ -d foo ]; then cd {self.gate}; fi; npm run render",
                   self.long, 2, "nonliteral condition with cd fails closed")
        self.check(f"if [ -d foo ]; then echo hi; fi; npm run render",
                   self.gate, 0, "nonliteral plain branch does not block Gate cwd")

    # ---- P1 final-review regressions ----
    def test_until_and_quoted_for_semantics(self):
        self.check(
            f"until false; do cd {self.long}; break; done; npm run render",
            self.gate, 2, "until false executes its body", reason="控制流")
        self.check(
            f"until true; do cd {self.long}; break; done; npm run render",
            self.gate, 0, "until true is a zero-iteration loop")
        for loop in (
            f'for i in ""; do cd {self.long}; break; done; npm run render',
            f"for i in ''; do cd {self.long}; break; done; npm run render",
            f'for i in "$X"; do cd {self.long}; break; done; npm run render',
        ):
            self.check(loop, self.gate, 2,
                       "quoted empty word is still one iteration", reason="控制流")
        self.check(f"for i in; do cd {self.long}; done; npm run render",
                   self.gate, 0, "truly empty for list is zero iterations")

    def test_quoted_and_sourced_function_calls(self):
        defs = os.path.join(self.root, "defs.sh")
        with open(defs, "w", encoding="utf-8") as fh:
            fh.write(f"f() {{ cd {self.long}; }}\n")
        self.check(f'f() {{ cd {self.long}; }}; "f"; npm run render',
                   self.gate, 2, "quoted function call")
        self.check(f"f() {{ cd {self.long}; }}; \\f; npm run render",
                   self.gate, 2, "escaped function call")
        self.check(f"source {defs}; f; npm run render",
                   self.gate, 2, "source-defined function call", reason="函数")
        self.check('echo "f"', self.gate, 0, "function name as text argument")

    def test_ansi_c_escapes(self):
        reason = "direction-approved.md"
        self.check(r"npm run $'\x72ender'", self.long, 2,
                   "hex escape in script name", reason=reason)
        self.check(r"npm run $'\u0072ender'", self.long, 2,
                   "unicode escape in script name", reason=reason)
        self.check(r"$'\x6e\x70\x6d' run render", self.long, 2,
                   "hex escapes in command name", reason=reason)
        self.check(r"npm run $'\x6e\x70\x6d' run render", self.long, 0,
                   "listed form runs script 'npm', not a render command")
        self.check(r"""bash -c "npm run \$'\x72ender'" """.strip(),
                   self.long, 2, "nested bash ANSI-C escape", reason=reason)
        self.check(r"npm run $'\qrender'", self.long, 2,
                   "unsupported ANSI-C escape fails closed", reason="ANSI-C")

    def test_command_substitution_dynamic_targets(self):
        reason = "命令替换"
        self.check("X=$(echo render); npm run $X", self.long, 2,
                   "assignment command substitution can become render", reason=reason)
        self.check("$(echo npm) run render", self.long, 2,
                   "command-position substitution can become render", reason=reason)
        self.check("""eval "$(echo 'npm run render')" """.strip(),
                   self.long, 2, "eval command substitution", reason=reason)
        self.check('echo "$(echo render)"', self.long, 0,
                   "text command substitution is not a command")

    # ---- P2 regressions ----
    def test_absolute_wrappers(self):
        self.check('/bin/bash -c "npm run render"', self.long, 2,
                   "absolute bash path")
        self.check(f"{self.npm} run render", self.long, 2,
                   "absolute npm path")
        self.check(f"{self.node} scripts/render-video.js out.html --duration=60",
                   self.long, 2, "absolute node path")
        self.check(f"builtin source {self.wrap}", self.long, 2,
                   "builtin source script")
        self.check(f"source {self.text_script}", self.long, 0,
                   "text-only sourced script")

    def test_background_isolation(self):
        self.check(f"cd {self.gate} && npm run render & npm run render",
                   self.long, 2, "background list must not change parent cwd")
        self.check(f"cd {self.gate} && npm run render & echo hi; npm run render",
                   self.long, 2, "background then foreground render")
        self.check(f"cd {self.gate} && npm run render & npm run render",
                   self.gate, 0, "background isolation from gated cwd")

    # ---- Existing behavior and false-positive guards ----
    def test_legacy_key_commands(self):
        self.check('npm run "render"', self.long, 2, "quoted npm script")
        self.check('npm run ren"der"', self.long, 2, "concatenated npm script")
        self.check('node render-vid"eo.js" --duration=60', self.long, 2,
                   "quoted node script")
        self.check("npm run $'render'", self.long, 2, "ANSI-C quoted script")
        self.check("npm run --silent render", self.long, 2, "npm option before script")
        self.check("npm --silent run render", self.long, 2, "npm option before run")
        self.check("nohup npm run render", self.long, 2, "nohup wrapper")
        self.check("timeout -s KILL 600 npm run render", self.long, 2,
                   "timeout value option")
        self.check("sudo -u user -E npm run render", self.long, 2, "sudo wrapper")
        self.check("command npm run render", self.long, 2, "command wrapper")
        self.check("xargs -n1 npm run render", self.long, 2, "xargs wrapper")
        self.check("npx --yes hyperframes render", self.long, 2, "npx wrapper")
        self.check("npx -p pkg hyperframes render", self.long, 2, "npx package")
        self.check("npm run render:docs", self.long, 2, "render-prefixed script")
        self.check("bash -lc \"npm run render\"", self.long, 2, "bash -lc")
        self.check("bash -c \"bash -c 'npm run render'\"", self.long, 2,
                   "nested bash -c")
        self.check('eval "npm run render"', self.long, 2, "literal eval")
        self.check('eval "echo npm run render"', self.long, 0, "text eval")
        self.check(f"source {self.wrap}", self.long, 2, "source script")
        self.check(f". {self.text_script}", self.long, 0, "dot text script")
        self.check("npm run render 2>&1", self.long, 2, "redirection")
        self.check("npm run render > /dev/null", self.long, 2, "stdout redirect")
        self.check("echo x | npm run render", self.long, 2, "pipeline right side")
        self.check("npm run render || true", self.long, 2, "render before ||")
        self.check("false || npm run render", self.long, 2, "render after false ||")
        self.check("for i in 1; do npm run render; done", self.long, 2,
                   "executed for body")
        self.check("while false; do npm run render; done", self.long, 0,
                   "zero-iteration while body")
        self.check("if false; then npm run render; fi", self.long, 0,
                   "dead if body")
        self.check("bash -n render-narration.sh", self.long, 0, "bash -n")
        self.check("bash -nc 'npm run render'", self.long, 0, "bash -nc")
        self.check("command -v npm run render", self.long, 0, "command -v")
        self.check("type npm run render", self.long, 0, "type lookup")
        self.check("which npm run render", self.long, 0, "which lookup")
        self.check("cat <<EOF\nnpm run render\nEOF", self.long, 0, "cat heredoc")
        self.check("bash <<EOF\nnpm run render\nEOF", self.long, 2, "bash heredoc")
        self.check("npm run render -- --duration=30 --duration=60", self.long, 0,
                   "first explicit duration wins, matching renderer find")
        self.check("npm run render -- --duration=60 --duration=30", self.long, 2,
                   "first explicit long wins")
        self.check("npm run render -- --duration 10 --duration=60", self.long, 2,
                   "equals-form duration wins over space-form candidate")
        self.check("npm run render -- --duration=0", self.long, 0,
                   "explicit zero is short")
        self.check("npm run render -- --duration=abc", self.long, 2,
                   "invalid explicit falls back to long HTML")
        self.check("npm run render -- --duration 10", self.long, 2,
                   "space form is not a renderer duration; long HTML fallback blocks")
        self.check(f"{self.node} scripts/render-video.js out.html --duration 60",
                   self.long, 0, "render-video ignores space-form duration; default 30s")
        self.check("npm run render -- -- --duration 10", self.long, 2,
                   "space form is not a duration; npm unknown uses long HTML fallback")
        self.check(f"{self.node} scripts/render-video.js out.html -- --duration 10",
                   self.long, 0, "space form is ignored by render-video; default 30s")
        self.check("npm --workspace other run render", self.gate, 2,
                   "workspace before run is unresolved")
        self.check("npm -wother run render", self.gate, 2,
                   "attached -w before run is unresolved")
        self.check("npm --workspaces run render", self.gate, 2,
                   "all workspaces before run is unresolved")

    def test_baseline(self):
        self.check("npm run render", self.long, 2, "long no gate")
        self.check("npm run render", self.gate, 0, "long with gate")
        self.check("npm run render", self.short, 0, "short")
        self.check("npm run render", self.noindex, 2, "unknown duration fail-closed")
        self.check("npm run render", self.gate, 0, "unknown duration with Gate")
        self.check("hyperframes render", self.gate, 0, "unknown duration with Gate")
        self.check("npm run build", self.long, 0, "non-render npm script")
        self.check("npm test", self.long, 0, "non-render npm test")
        self.check('echo "npm run render"', self.long, 0, "plain text")
        self.check("echo if npm run render", self.long, 0,
                   "non-command-position control word is text")
        self.check("git status", self.long, 0, "ordinary command")
        self.check("python3 -c \"print('npm run render')\"", self.long, 0,
                   "python -c text")
        self.check("n'm'p run render", self.long, 0, "nmp is not npm")
        self.check("cat <<EOF\nnpm run render\nEOF", self.long, 0,
                   "cat heredoc is data")
        self.check("bash <<EOF\nnpm run render\nEOF", self.long, 2,
                   "bash heredoc is executable")
        self.check("bash -n render-narration.sh", self.long, 0,
                   "bash -n does not execute")
        self.check("bash -c \"echo npm run render\"", self.long, 0,
                   "shell -c text")
        self.check(f"bash -c \"cd {self.gate} && npm run render\"", self.long, 0,
                   "shell -c gated cd")
        self.check("SKIP_DESIGN_GATE=1 npm run render", self.long, 0,
                   "explicit skip")
        self.check("SKIP_DESIGN_GATE=1; npm run render", self.long, 2,
                   "standalone assignment does not export")
        self.check("export SKIP_DESIGN_GATE=1; npm run render", self.long, 0,
                   "exported skip")
        self.check("env -i SKIP_DESIGN_GATE=1 npm run render", self.long, 0,
                   "env -i with explicit skip")
        self.check("export SKIP_DESIGN_GATE=1; env -i npm run render", self.long, 2,
                   "env -i clears skip")
        self.check(f"cd {self.gate} && npm run render", self.long, 0,
                   "gated cd")
        self.check(f"cd {self.long} && npm run render", self.gate, 2,
                   "ungated cd")
        self.check("command -v npm run render", self.long, 0,
                   "command -v lookup")
        self.check("npm run render -- --duration=30", self.long, 0,
                   "explicit short in long project")
        self.check("npm run render -- --duration=60", self.short, 2,
                   "explicit long in short project")

    def test_fail_closed_inputs(self):
        self.check("npm run render", None, 2, "missing cwd with long/unknown")
        self.check("npm run render -- --duration=30", None, 0,
                   "missing cwd with explicit short")
        self.check(f"cd {self.gate} && npm run render", None, 0,
                   "missing cwd but cd to gated target")
        self.check(f"cd {self.long} && npm run render", None, 2,
                   "missing cwd but cd to ungated target")
        self.check(f"npm run render --prefix {self.gate}", None, 0,
                   "missing cwd but gated prefix")
        self.check(f"npm run render --prefix {self.long}", None, 2,
                   "missing cwd but ungated prefix")
        self.check(f"{self.node} scripts/render-video.js out.html --duration=60",
                   None, 2, "missing cwd with explicit long")
        self.check(f"{self.node} scripts/render-video.js out.html --duration=30",
                   None, 0, "missing cwd with explicit short")


if __name__ == "__main__":
    print(f"hook={HOOK}")
    print(f"hook_sha256={hook_sha(HOOK)}")
    unittest.main(verbosity=2)

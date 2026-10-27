#!/usr/bin/env python3
"""test_verify_status.py — verify.py 退出码判定的纯函数测试。

不需要 Playwright：只验证“page error 或 console error 都必须让门禁失败”。
运行：python3 scripts/test_verify_status.py
"""

import os
import sys
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import verify  # noqa: E402


class ExitStatusTests(unittest.TestCase):
    def test_clean_page_passes(self):
        self.assertEqual(verify.exit_status([], []), 0)

    def test_page_error_fails(self):
        self.assertEqual(verify.exit_status(["ReferenceError"], []), 1)

    def test_console_error_fails(self):
        self.assertEqual(verify.exit_status([], ["[error] boom"]), 1)

    def test_both_fail(self):
        self.assertEqual(verify.exit_status(["err"], ["[error] boom"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)

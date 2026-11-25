#!/usr/bin/env python3
"""check-visual-identity.py 的回归：事实提取、逐维度比较、记录/账本、边界与「不裁决」。

用临时生成的图片做 fixture，不依赖仓库里的真实成品图。
缺少 Pillow 时跳过并说明原因，不伪造通过。
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "check-visual-identity.py")

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    Image = None

W, H = 360, 640
PAPER = (244, 241, 232)
PAPER2 = (250, 245, 234)


def run(args, env=None, cwd=None):
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    return subprocess.run([sys.executable, SCRIPT] + args,
                          capture_output=True, text=True, env=full_env, cwd=cwd)


def parse_json(stdout: str) -> dict:
    """脚本先把 JSON 打到 stdout，再打摘要行；从头部精确解出 JSON 对象。"""
    return json.JSONDecoder().raw_decode(stdout)[0]


def frame(top_heavy: bool, accent: bool = True, paper=PAPER):
    """造一张「版式化成品」：纸底 + 文字块 + 图版。

    top_heavy=True  → 文字块在 20–40% 高度（下段留白，图版从 55% 开始）
    top_heavy=False → 文字块紧贴顶部（10–20%），图版从 30% 开始
    """
    im = Image.new("RGB", (W, H), paper)
    d = ImageDraw.Draw(im)
    if top_heavy:
        band = (int(H * 0.20), int(H * 0.34))
        card_top = int(H * 0.55)
    else:
        band = (int(H * 0.10), int(H * 0.18))
        card_top = int(H * 0.30)
    # 两行标题
    for i in range(2):
        y = band[0] + i * 34
        d.rectangle([32, y, W - 32, y + 26], fill=(24, 32, 29))
    if accent:
        d.rectangle([32, band[0] - 18, 46, band[0] - 4], fill=(176, 0, 0))
    # 图版：带内容纹理的大块
    d.rectangle([44, card_top, W - 44, H - 20], fill=(250, 250, 250))
    for i in range(14):
        y = card_top + 14 + i * 24
        d.rectangle([60, y, W - 60, y + 12], fill=(140, 146, 150))
    return im


@unittest.skipIf(Image is None, "缺少 Pillow：无法生成 fixture，跳过视觉身份脚本回归")
class VisualIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = cls.tmp.name
        cls.a = os.path.join(d, "a.png")
        cls.b = os.path.join(d, "b.png")
        cls.same = os.path.join(d, "same.png")
        cls.nobg = os.path.join(d, "nobg.png")
        frame(True).save(cls.a)
        frame(False, paper=PAPER2).save(cls.b)
        frame(True).save(cls.same)                 # 与 a 完全相同
        frame(True, accent=False).save(cls.nobg)   # 无强调色

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    # ── 事实提取 ─────────────────────────────────────────────
    def test_01_facts_schema_and_fingerprint(self):
        r = run(["--image", self.a])
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = parse_json(r.stdout)
        self.assertEqual(payload["schema"], "designwise-visual-identity/v1")
        img = payload["images"][0]
        for key in ("file", "sha256", "size", "bg_rgb", "dominant_text_band",
                    "text_left_frac", "accent_share", "accent_y",
                    "dark_bands", "edge_bands", "left_bands"):
            self.assertIn(key, img)
        self.assertEqual(len(img["dark_bands"]), 10)
        self.assertEqual(img["size"], [W, H])
        self.assertEqual(len(img["sha256"]), 64)

    def test_02_background_read_from_border_not_subject(self):
        r = run(["--image", self.a])
        img = parse_json(r.stdout)["images"][0]
        # 边框是纸底，主体里的大块白/灰不得把底色拉偏
        for got, want in zip(img["bg_rgb"], PAPER):
            self.assertLessEqual(abs(got - want), 6, f"底色 {img['bg_rgb']} 偏离 {PAPER}")

    def test_03_text_band_tracks_vertical_position(self):
        r_top = run(["--image", self.a])
        r_low = run(["--image", self.b])
        got_top = parse_json(r_top.stdout)["images"][0]
        got_low = parse_json(r_low.stdout)["images"][0]
        # 文字块越靠上，主文字带下标越小
        self.assertLess(got_low["dominant_text_band"], got_top["dominant_text_band"])

    # ── 比较 ─────────────────────────────────────────────────
    def test_04_identical_frames_have_zero_difference(self):
        r = run(["--image", self.a, "--label", "A", "--image", self.same, "--label", "A2"])
        payload = parse_json(r.stdout)
        pair = payload["pairs"][0]
        self.assertEqual(pair["bg_distance_rgb"], 0.0)
        self.assertEqual(pair["dark_bands_l1"], 0.0)
        self.assertEqual(pair["edge_bands_l1"], 0.0)
        self.assertTrue(pair["same_dominant_text_band"])

    def test_05_different_composition_is_reported_as_different_bands(self):
        r = run(["--image", self.a, "--image", self.b])
        pair = parse_json(r.stdout)["pairs"][0]
        self.assertGreater(pair["dark_bands_l1"], 0.10)
        self.assertFalse(pair["same_dominant_text_band"])
        self.assertTrue(pair["bands_differing_dark"])

    def test_06_near_bg_is_reported_as_shared_dimension(self):
        # 同样的纸底与左边距 → 这两维应当几乎一致，即使构图不同
        r = run(["--image", self.a, "--image", self.b])
        pair = parse_json(r.stdout)["pairs"][0]
        self.assertLess(pair["bg_distance_rgb"], 40)
        self.assertIsNotNone(pair["text_left_delta_frac"])
        self.assertLess(pair["text_left_delta_frac"], 0.02)

    # ── 不裁决（硬边界）────────────────────────────────────────
    def test_07_no_verdict_field_and_exit_zero_even_when_similar(self):
        r = run(["--image", self.a, "--image", self.same])
        self.assertEqual(r.returncode, 0, "相似度不得改变退出码")
        payload = parse_json(r.stdout)
        self.assertNotIn("verdict", payload)
        for pair in payload["pairs"]:
            self.assertNotIn("verdict", pair)
            self.assertNotIn("passed", pair)
        self.assertIn("不设阈值", payload["note"])

    def test_08_no_threshold_flag_accepted(self):
        # 明确拒绝「设一个相似度阈值」的用法
        r = run(["--image", self.a, "--image", self.b, "--skeleton-threshold", "0.5"])
        self.assertEqual(r.returncode, 2)

    # ── 记录 / 账本 ───────────────────────────────────────────
    def test_09_record_writes_facts_without_image_and_tight_perms(self):
        with tempfile.TemporaryDirectory() as home:
            r = run(["--image", self.a, "--label", "P", "--record"],
                    env={"DESIGNWISE_HOME": home})
            self.assertEqual(r.returncode, 0, r.stderr)
            path = os.path.join(home, "identity-frames.jsonl")
            self.assertTrue(os.path.isfile(path))
            with open(path, encoding="utf-8") as f:
                lines = [json.loads(x) for x in f if x.strip()]
            self.assertEqual(len(lines), 1)
            self.assertEqual(lines[0]["label"], "P")
            self.assertIn("sha256", lines[0])
            self.assertIn("recorded_at", lines[0])
            # 只存事实与指纹，不存图片路径与像素
            self.assertNotIn("pixels", lines[0])
            self.assertNotIn("path", lines[0])
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)

    def test_10_compare_ledger_reports_cross_entry_pairs(self):
        with tempfile.TemporaryDirectory() as home:
            self.assertEqual(run(["--image", self.a, "--label", "P", "--record"],
                                 env={"DESIGNWISE_HOME": home}).returncode, 0)
            r = run(["--image", self.b, "--label", "Q", "--compare-ledger", "5"],
                    env={"DESIGNWISE_HOME": home})
            self.assertEqual(r.returncode, 0, r.stderr)
            payload = parse_json(r.stdout)
            self.assertEqual(len(payload["ledger_pairs"]), 1)
            self.assertEqual(payload["ledger_pairs"][0]["a"], "Q")
            self.assertEqual(payload["ledger_pairs"][0]["b"], "P")

    def test_11_empty_ledger_is_not_an_error(self):
        with tempfile.TemporaryDirectory() as home:
            r = run(["--image", self.a, "--compare-ledger", "5"],
                    env={"DESIGNWISE_HOME": home})
            self.assertEqual(r.returncode, 0, r.stderr)
            payload = parse_json(r.stdout)
            self.assertEqual(payload["ledger_pairs"], [])

    # ── 边界 ─────────────────────────────────────────────────
    def test_12_missing_image_is_usage_error(self):
        self.assertEqual(run([]).returncode, 2)

    def test_13_label_count_must_match(self):
        r = run(["--image", self.a, "--image", self.b, "--label", "only-one"])
        self.assertEqual(r.returncode, 2)

    def test_14_unreadable_image_is_error_not_placeholder(self):
        with tempfile.TemporaryDirectory() as d:
            bad = os.path.join(d, "bad.png")
            with open(bad, "wb") as f:
                f.write(b"not an image")
            r = run(["--image", bad])
            self.assertEqual(r.returncode, 2)
            self.assertIn("无法解码", r.stderr)

    def test_15_reference_documents_the_false_negative(self):
        """边界说明必须写清「不用于跨产品骨架判定」，否则下一个人会误用。"""
        doc = os.path.join(os.path.dirname(HERE), "references",
                           "cross-product-differentiation.md")
        with open(doc, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("假阴性", text)
        self.assertIn("skeleton_correlation", text)


if __name__ == "__main__":
    unittest.main()

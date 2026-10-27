#!/usr/bin/env python3
"""test_zcode_image_fit.py — zcode_image.py 尺寸适配的零费用测试。

全部使用本地合成图片，不请求上游生图接口，不产生任何模型费用。
运行：python3 test_zcode_image_fit.py   （退出码 0 = 全部通过）
覆盖：三模式语义、精确尺寸、灰度/调色板/透明输入、JPEG 落盘 alpha 合成、
      非法尺寸与损坏输入、比例提示词构造。
"""

import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True  # 不在 scripts/ 留 __pycache__

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import zcode_image as zi  # noqa: E402

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))


def px(im, x, y):
    return im.convert("RGBA").getpixel((x, y))


def make(path, size, mode="RGB", painter=None):
    im = Image.new(mode, size)
    if painter:
        painter(im)
    im.save(path)
    return Image.open(path)


def quad_painter(im):
    """四象限色块 + 中心标记，用于验证裁剪/保留方位。"""
    w, h = im.size
    for (x0, y0, color) in [(0, 0, (255, 0, 0)), (w // 2, 0, (0, 255, 0)),
                            (0, h // 2, (0, 0, 255)), (w // 2, h // 2, (255, 255, 0))]:
        for y in range(y0, y0 + h // 2):
            for x in range(x0, x0 + w // 2):
                im.putpixel((x, y), color + ((255,) if im.mode == "RGBA" else ()))


def main():
    tmp = tempfile.mkdtemp(prefix="zcode_image_fit_test_")
    S = lambda *p: os.path.join(tmp, *p)  # noqa: E731

    # ---- 场景 1：输入与目标一致 → 不改写、内容不变
    src = S("sq.png")
    make(src, (100, 100), painter=quad_painter)
    before = Image.open(src).tobytes()
    for mode in ("cover", "contain", "stretch"):
        out = S(f"same_{mode}.png")
        shutil.copyfile(src, out)
        note = zi.fit_to_size(out, "100x100", mode)
        im = Image.open(out)
        check(f"1/{mode} 尺寸不变", im.size == (100, 100), str(im.size))
        if mode == "cover":
            check("1/cover 内容未改写", Image.open(out).tobytes() == before)
            check("1/cover 提示无需适配", "无需适配" in note, note)

    # ---- 场景 2：正方形 → 竖图（100x100 → 100x200）
    for mode in ("cover", "contain", "stretch"):
        out = S(f"sq2tall_{mode}.png")
        make(out, (100, 100), painter=quad_painter)
        zi.fit_to_size(out, "100x200", mode)
        im = Image.open(out)
        check(f"2/{mode} 精确 100x200", im.size == (100, 200), str(im.size))
        if mode == "cover":
            # scale=2 → 200x200 → 左右各裁 50%：中心列仍是左上红/左下蓝
            check("2/cover 中心列保留原色", px(im, 25, 25)[:3] == (255, 0, 0) and px(im, 25, 150)[:3] == (0, 0, 255), f"{px(im,25,25)}/{px(im,25,150)}")
            check("2/cover 满幅无留白", all(px(im, x, y)[3] == 255 for x, y in [(1, 1), (98, 198)]))
        elif mode == "contain":
            # scale=1 → 100x100 居中贴到 100x200：上下各 50px 透明留白
            check("2/contain 内容完整（中心色不变）", px(im, 50, 100)[:3] == (255, 255, 0), str(px(im, 50, 100)))
            check("2/contain 上下透明留白", px(im, 50, 10)[3] == 0 and px(im, 50, 190)[3] == 0, f"{px(im,50,10)}/{px(im,50,190)}")
        else:
            # stretch：目标 (50,10) 对应源 (50,5)
            src_im = Image.open(src)
            check("2/stretch 纵向拉伸映射", px(im, 50, 10) == px(src_im, 50, 5), f"{px(im,50,10)} vs {px(src_im,50,5)}")

    # ---- 场景 3：竖图 → 横图（80x160 → 160x80）
    tall = S("tall.png")
    make(tall, (80, 160), painter=quad_painter)
    for mode in ("cover", "contain", "stretch"):
        out = S(f"t2w_{mode}.png")
        shutil.copyfile(tall, out)
        zi.fit_to_size(out, "160x80", mode)
        check(f"3/{mode} 精确 160x80", Image.open(out).size == (160, 80), str(Image.open(out).size))
        if mode == "cover":
            im = Image.open(out)
            check("3/cover 横向满幅", px(im, 2, 40)[3] == 255 and px(im, 157, 40)[3] == 255)
        if mode == "contain":
            im = Image.open(out)
            check("3/contain 左右透明留白", px(im, 5, 40)[3] == 0 and px(im, 154, 40)[3] == 0)
            check("3/contain 中心内容在", px(im, 80, 40)[:3] != (0, 0, 0) or px(im, 80, 40)[3] == 255)

    # ---- 场景 4：横图 → 不同宽高比竖图（160x80 → 90x160），检查告警
    wide = S("wide.png")
    make(wide, (160, 80), painter=quad_painter)
    out = S("w2t_cover.png")
    shutil.copyfile(wide, out)
    note = zi.fit_to_size(out, "90x160", "cover")
    check("4/cover 精确 90x160", Image.open(out).size == (90, 160))
    check("4/cover 重大裁剪告警", "🔴" in note and "左右裁掉" in note, note)
    out = S("w2t_contain.png")
    shutil.copyfile(wide, out)
    note = zi.fit_to_size(out, "90x160", "contain")
    check("4/contain 精确 90x160", Image.open(out).size == (90, 160))
    check("4/contain 留白告警", "留白" in note and "未被裁" in note, note)
    out = S("w2t_stretch.png")
    shutil.copyfile(wide, out)
    note = zi.fit_to_size(out, "90x160", "stretch")
    check("4/stretch 精确 90x160", Image.open(out).size == (90, 160))
    check("4/stretch 变形告警", "变形" in note, note)

    # ---- 场景 5：RGBA / 灰度 / 调色板输入
    rgba = S("rgba.png")
    make(rgba, (100, 100), mode="RGBA", painter=quad_painter)
    out = S("rgba_contain.png")
    shutil.copyfile(rgba, out)
    zi.fit_to_size(out, "200x100", "contain")
    im = Image.open(out)
    check("5/RGBA contain 精确 200x100", im.size == (200, 100))
    check("5/RGBA 透明区保留 alpha=0", px(im, 2, 50)[3] == 0, str(px(im, 2, 50)))
    check("5/RGBA 不出现黑底", px(im, 2, 50)[:3] == (255, 255, 255) or px(im, 2, 50)[3] == 0, str(px(im, 2, 50)))

    gray = S("gray.png")
    make(gray, (100, 100), mode="L", painter=lambda im: [im.putpixel((x, y), 200) for y in range(40, 60) for x in range(40, 60)])
    out = S("gray_cover.png")
    shutil.copyfile(gray, out)
    zi.fit_to_size(out, "100x100", "cover")  # 同尺寸 → 早退分支
    check("5/灰度 同尺寸直通", Image.open(out).getpixel((45, 45)) == 200)

    out = S("gray_stretch.png")
    shutil.copyfile(gray, out)
    zi.fit_to_size(out, "50x50", "stretch")
    im = Image.open(out)
    check("5/灰度 stretch 精确 50x50", im.size == (50, 50))
    check("5/灰度 灰度值保留", im.convert("L").getpixel((25, 25)) >= 190, str(im.convert("L").getpixel((25, 25))))

    pal = S("pal.png")
    make(pal, (100, 100), painter=quad_painter).quantize(16).save(pal)
    out = S("pal_cover.png")
    shutil.copyfile(pal, out)
    zi.fit_to_size(out, "50x100", "cover")
    im = Image.open(out)
    check("5/调色板 cover 精确 50x100", im.size == (50, 100))
    colors = {px(im, 12, 25)[:3], px(im, 37, 25)[:3]}
    check("5/调色板 四象限色块保留", len(colors) >= 2, str(colors))

    # JPEG 落盘（alpha 合成到白底）
    out = S("rgba_to_jpg.jpg")
    shutil.copyfile(rgba, out)
    note = zi.fit_to_size(out, "200x100", "contain")
    im = Image.open(out)
    check("5/JPEG contain 精确 200x100", im.size == (200, 100))
    check("5/JPEG 无 alpha 通道", im.mode == "RGB", im.mode)
    check("5/JPEG 留白合成白底（无黑底）", px(im, 2, 50)[:3] == (255, 255, 255), str(px(im, 2, 50)))

    # ---- 场景 6：非法目标尺寸、损坏图片 → 明确失败
    out = S("bad_input.png")
    with open(out, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + os.urandom(256))
    try:
        zi.fit_to_size(out, "50x50", "cover")
        check("6/损坏图片明确失败", False, "未抛 FitError")
    except zi.FitError:
        check("6/损坏图片明确失败", True)
    for bad in ("abc", "100", "100x", "x100", "0x100", "100x0", "-5x100", "100×0"):
        try:
            zi.fit_to_size(S("sq.png"), bad, "cover") if bad != "abc" else zi.fit_to_size(S("sq.png"), bad, "cover")
            check(f"6/非法尺寸 {bad!r} 明确失败", False, "未抛 FitError")
        except zi.FitError:
            check(f"6/非法尺寸 {bad!r} 明确失败", True)
    # CLI 错误路径：不触网、不留文件
    r = subprocess.run([sys.executable, os.path.join(HERE, "zcode_image.py"),
                        "--prompt", "t", "--out", S("never.png"), "--size", "abc"],
                       capture_output=True, text=True, timeout=30)
    check("6/CLI 非法尺寸退出码 1", r.returncode == 1, f"rc={r.returncode} out={r.stdout[-120:]}")
    check("6/CLI 非法尺寸报错信息", "无效的目标尺寸" in r.stdout)
    check("6/CLI 非法尺寸未触网未留文件", not os.path.exists(S("never.png")))

    # ---- 场景 7：小尺寸与大尺寸均精确
    out = S("small.png")
    shutil.copyfile(src, out)
    zi.fit_to_size(out, "3x5", "cover")
    check("7/小尺寸 3x5 精确", Image.open(out).size == (3, 5), str(Image.open(out).size))
    out = S("large.png")
    shutil.copyfile(src, out)
    zi.fit_to_size(out, "2048x1152", "cover")
    check("7/大尺寸 2048x1152 精确", Image.open(out).size == (2048, 1152), str(Image.open(out).size))

    # ---- 场景 8：比例提示词构造（不发送任何请求）
    hint = zi._ratio_hint("1410x600")
    check("8/非整比用小数", "2.35:1" in hint and "1410x600" in hint, hint)
    check("8/不声称强制精确尺寸", "再适配到" in hint, hint)
    hint = zi._ratio_hint("1024x1024")
    check("8/方形 1:1", "1:1" in hint and "方形构图" in hint, hint)
    hint = zi._ratio_hint("768x1024")
    check("8/竖图 3:4", "3:4" in hint and "竖构图" in hint, hint)
    check("8/None 不产生 hint", zi._ratio_hint(None) == "")
    p = "一只猫"
    hint = zi._ratio_hint("1536x1024")
    check("8/原提示词保留", (p + "\n" + hint).startswith(p) and hint.startswith("构图约束"))

    shutil.rmtree(tmp, ignore_errors=True)  # 测试临时目录收尾，不留意外文件
    failed = [n for n, ok, _ in RESULTS if not ok]
    print(f"\n共 {len(RESULTS)} 项，通过 {len(RESULTS) - len(failed)}，失败 {len(failed)}")
    if failed:
        print("失败项：", *failed, sep="\n  - ")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

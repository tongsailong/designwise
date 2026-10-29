#!/usr/bin/env python3
"""把「已经写好的视觉稿 HTML」直接转成可编辑 PPTX —— 不要求 HTML 满足任何硬约束。

和 html2pptx.js 的分工（别混用，见 references/editable-pptx.md 顶部的决策表）：

  html2pptx.js          HTML 还没写 → 按 4 条硬约束写出来，导出的文本框结构最干净
  本脚本                HTML 已经写好且是视觉驱动的（flex / 居中 / 裸文字 / 背景图）
                        → 零改造直接转；要继承甲方官方模板母版时也只能走这条

为什么能绕开那 4 条硬约束：它读的不是源码，是**浏览器渲染完之后**的
getBoundingClientRect。flex、居中、自动换行浏览器都已经算成绝对坐标了，
所以「div 里有裸文字」「用了 flex」这些写法根本不构成问题。

四类元素对应 PowerPoint 的四种对象：
  text  → 文本框（按 <br> 分段，每段一个框，各带自己的 runs 和行高）
  shape → 矩形 / 圆角矩形（卡片底、色条、分隔线、行内装饰块）
  img   → 图片（CSS 圆角会烤进 alpha 通道）
  svg   → 截成 PNG 的图片（图表拆成几百个矩形反而没法编辑，留图更实用）

用法：
    python3 pptx_from_rendered.py deck.html -o deck.pptx
    python3 pptx_from_rendered.py deck.html -o deck.pptx \\
        --template 客户模板.pptx --layout "内页" --skip-class logo

退出码：0 正常（含「没有丢字」）；1 文本完整性校验失败（页数不一致或存在非预期缺字）。

依赖：playwright（含 chromium）、python-pptx、Pillow
"""
import argparse, asyncio, json, os, re, sys, tempfile

from PIL import Image, ImageDraw
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

EMU_PER_PT = 12700

# ─────────────────────────────────────────────────────────────
# 一、在浏览器里量：把渲染结果拆成元素清单
# ─────────────────────────────────────────────────────────────

JS = r"""
({selector, skipClass}) => {
  const INLINE = ['em','b','i','strong','span','small','br','sup','sub','a','code','mark'];
  const px = v => parseFloat(v) || 0;
  // 元素自己的 opacity（opacity 不继承，祖先链要由调用方累乘传进来）
  const opOf = (cs) => { const o = parseFloat(cs.opacity); return Number.isFinite(o) ? o : 1; };

  // CSS capitalize 用的是 Unicode titlecase（ǳ→ǲ），与 toUpperCase（ǳ→Ǳ）不同。
  // 手写映射表会长期失准，所以让浏览器自己算：探针挂在 body 下的离屏宿主里，
  // 不能用隐藏量具容器（那里的 innerText 拿不到转换结果）。
  let probeHost = null;
  const titlecase = (ch, lang) => {
    if (!probeHost) {
      probeHost = document.createElement('div');
      probeHost.style.cssText =
        'position:fixed;left:-100000px;top:0;visibility:visible;pointer-events:none';
      document.body.appendChild(probeHost);
    }
    const box = document.createElement('div');
    box.style.textTransform = 'capitalize';
    if (lang) box.lang = lang;
    box.textContent = ch;
    probeHost.appendChild(box);
    const rendered = box.innerText;
    box.remove();
    return rendered || ch.toUpperCase();   // 取不到就退回大写，绝不让字符变空
  };

  // 词首位置只对确实需要 capitalize 的文本计算。Intl.Segmenter 对非法语言标签会抛
  // RangeError（例如 lang="en_US"），所以构造失败时先退回默认 locale，再退回空白分词。
  let segmenter = null, segmenterLang = null, segmenterBroken = false;
  const wordStarts = (text) => {
    const lang = document.documentElement.lang || null;
    if (!segmenterBroken && (segmenter === null || segmenterLang !== lang)) {
      try {
        segmenter = new Intl.Segmenter(lang || undefined, {granularity: 'word'});
      } catch (e) {
        try { segmenter = new Intl.Segmenter(undefined, {granularity: 'word'}); }
        catch (e2) { segmenter = null; segmenterBroken = true; }
      }
      segmenterLang = lang;
    }
    const starts = new Set();
    if (segmenter) {
      for (const part of segmenter.segment(text)) if (part.isWordLike) starts.add(part.index);
      return starts;
    }
    let offset = 0;
    for (const ch of text) {
      if (offset === 0 || /\s/.test(text[offset - 1])) starts.add(offset);
      offset += ch.length;
    }
    return starts;
  };

  // 把一组**原始**节点拆成 runs（每段连续同样式的文字一个 run）。
  //
  // 直接读原始节点，不做克隆：克隆到临时量具容器里会让 display:none /
  // visibility:hidden 的子元素重新进入导出（量具自身也是隐藏的，没法用计算样式判断），
  // 也会改变 `p > span`、`:first-child` 这类选择器的计算值。
  //
  // ⚠️ 必须在这里做 HTML 的空白折叠。源码里的换行和缩进会变成真实的文本节点，
  // 浏览器按 white-space:normal 折叠掉（连续空白→一个空格，行首行尾丢弃），
  // 但 PPTX 没有这套规则——原样搬过去，那个 \n 在 PowerPoint 里就是一个真换行，
  // 会把后面的内容整段推到下一行去压住别的元素。
  const runsOf = (rootNodes, op) => {
    const out = [];
    const flush = (items) => {
      if (!items.length) return;
      const chars = [];
      for (const {text, styleEl, parentOp} of items) {
        const cs = getComputedStyle(styleEl);
        for (const ch of text.replace(/\s+/g, ' ')) {
          if (ch === ' ' && (!chars.length || chars[chars.length - 1].ch === ' ')) continue;
          chars.push({ch, cs, op: parentOp, lang: styleEl.closest('[lang]')?.lang || document.documentElement.lang});
        }
      }
      while (chars[0]?.ch === ' ') chars.shift();
      while (chars[chars.length - 1]?.ch === ' ') chars.pop();
      if (!chars.length) return;

      const text = chars.map(c => c.ch).join('');
      let needStarts = false;
      for (const item of chars) { if (item.cs.textTransform === 'capitalize') { needStarts = true; break; } }
      const starts = needStarts ? wordStarts(text) : null;

      let offset = 0;
      let run = null;
      const emit = () => { if (run?.t) out.push(run); run = null; };
      for (const item of chars) {
        const tt = item.cs.textTransform;
        let rendered = item.ch;
        if (tt === 'uppercase') rendered = item.ch.toUpperCase();
        else if (tt === 'lowercase') rendered = item.ch.toLowerCase();
        else if (tt === 'capitalize' && starts && starts.has(offset)) rendered = titlecase(item.ch, item.lang);
        const style = {
          fs: px(item.cs.fontSize), fw: item.cs.fontWeight, color: item.cs.color,
          ls: item.cs.letterSpacing === 'normal' ? 0 : px(item.cs.letterSpacing),
          italic: item.cs.fontStyle === 'italic', under: item.cs.textDecorationLine.includes('underline'),
          op: item.op,
        };
        const same = run && Object.keys(style).every(k => run[k] === style[k]);
        if (!same) { emit(); run = {...style, t: ''}; }
        run.t += rendered;
        offset += item.ch.length;
      }
      emit();
    };

    // 视觉上的隐藏（display:none / visibility:hidden）在这里整棵排除；opacity:0 也排除。
    // 检查的是原始节点，所以不会受量具容器自身 visibility 的影响。
    const collectList = (list, parentOp, items) => {
      for (const n of list) {
        if (n.nodeType === 3) {
          items.push({text: n.textContent, styleEl: n.parentElement, parentOp});
        } else if (n.nodeType === 1) {
          if (skipClass && n.classList && n.classList.contains(skipClass)) continue;
          if (n.tagName.toLowerCase() === 'br') {
            flush(items); items.length = 0; out.push({br: true});
            continue;
          }
          const cs = getComputedStyle(n);
          const nextOp = parentOp * opOf(cs);
          if (cs.display === 'none' || cs.visibility === 'hidden' || nextOp === 0) continue;
          collectList(n.childNodes, nextOp, items);
        }
      }
    };
    const items = [];
    collectList(rootNodes, op, items);
    flush(items);
    return out.filter(r => r.br || r.t);
  };

  // 量一组节点占的位置和行数。
  // 数行数不能拿每个矩形的 top 去重——同一行里字号不同的 run（一个 132px 的数字挨着
  // 62px 的说明）基线对齐、顶边却差一大截，会被当成两行。按 y 区间是否重叠来聚类。
  const measure = (nodes) => {
    const rng = document.createRange();
    rng.setStartBefore(nodes[0]);
    rng.setEndAfter(nodes[nodes.length - 1]);
    const bb = rng.getBoundingClientRect();
    const rects = [...rng.getClientRects()]
                    .filter(q => q.width > 0.5 && q.height > 0.5)
                    .sort((a, b) => a.top - b.top);
    const rows = [];
    for (const q of rects) {
      const last = rows[rows.length - 1];
      if (last && q.top < last.bottom - 2) last.bottom = Math.max(last.bottom, q.bottom);
      else rows.push({top: q.top, bottom: q.bottom});
    }
    return {bb, lines: Math.max(1, rows.length)};
  };

  const pages = [...document.querySelectorAll(selector)];
  const result = pages.map((pg) => {
    const pb = pg.getBoundingClientRect();
    const out = [];
    const tagSeq = {};                 // svg 与 canvas 各自计数：截图按标签分别取 nth

    // 一组相邻节点 → 一个文本框。
    // own=true 表示这段是「块级子元素之间的裸文字」：位置必须用文字自己的包围盒，
    // 套容器的 x/w 会盖到旁边的 svg/图标上，也不能沿用容器的居中语义。
    const emitText = (el, cs, base, g, op, own) => {
      const nodes = g.filter(n => n.nodeType !== 3 || n.textContent.trim());
      if (!nodes.length) return;
      const {bb, lines} = measure(nodes);
      if (!bb.height) return;
      // 直接读原始节点；隐藏子树与 opacity:0 在 runsOf 内部按原始 DOM 排除。
      const rs = runsOf(nodes, op);
      if (!rs.length) return;
      const fsMax = Math.max(px(cs.fontSize), ...rs.filter(r => !r.br).map(r => r.fs));
      out.push({
        tag: base.tag, cls: base.cls, kind: 'text',
        // x/w 用容器的：居中的段落要靠容器宽度维持居中语义，
        // 用段落自己收缩后的宽度会在换字体后左右飘。
        x: own ? bb.left - pb.left : base.x, w: own ? bb.width : base.w,
        y: bb.top - pb.top, h: bb.height,
        fs: px(cs.fontSize), fsMax, fw: cs.fontWeight, color: cs.color,
        ls: cs.letterSpacing === 'normal' ? 0 : px(cs.letterSpacing),
        ta: own ? 'left' : cs.textAlign,
        lhEff: bb.height / lines, lines,
        wrap: lines > 1,
        runs: rs, op,
      });
    };

    const walk = (el, parentOp = 1) => {
      // --skip-class 在 DOM 遍历阶段整棵跳过：HTML 与 SVG 都走 classList，
      // 只跳过该类元素本身（含子树），与参考文本的排除口径一致。
      if (skipClass && el.classList && el.classList.contains(skipClass)) return;
      const cs = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      const tag = el.tagName.toLowerCase();
      // op：祖先链 opacity 的累乘。CSS 的 opacity 作用到整棵子树，PPTX 的填充/透明度
      // 却是逐个对象设的——不累乘，淡出层和半透明文字全部导出成不透明。
      const op = parentOp * opOf(cs);
      if (cs.display === 'none' || cs.visibility === 'hidden' || op === 0) return;

      const cls = (typeof el.className === 'string' ? el.className : '');
      const base = {tag, cls, x: r.left - pb.left, y: r.top - pb.top, w: r.width, h: r.height};

      if (tag === 'img') {
        out.push({...base, kind: 'img', src: el.getAttribute('src'), op,
                  radius: px(cs.borderRadius), shadow: cs.boxShadow});
        return;
      }
      if (tag === 'svg' || tag === 'canvas') {
        const seq = tagSeq[tag] = (tagSeq[tag] ?? -1) + 1;
        out.push({...base, kind: 'svg', seq, tagName: tag, op});
        return;
      }

      const hasText = el.innerText && el.innerText.trim().length > 0;
      const onlyInline = [...el.children].every(c => INLINE.includes(c.tagName.toLowerCase()));

      const bg = cs.backgroundColor;
      const painted = (bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent');
      const bdw = px(cs.borderTopWidth);
      if (painted || bdw > 0) {          // 背景/描边先出矩形，画在文字之下
        out.push({...base, kind: 'shape', bg, bdw, bdc: cs.borderTopColor, op,
                  radius: px(cs.borderRadius), shadow: cs.boxShadow, rot: 0});
      }

      if (hasText && onlyInline) {
        // 按 <br> 分段，每段单独出一个文本框。
        //
        // 为什么不整块出一个框：PowerPoint 的行距是段落级的，而视觉稿经常把不同字号的行
        // 放进同一个 div。整块套一个行距，小字那几行会被撑开、大字那行会被压，
        // 实测会出现相邻两行直接叠在一起。分段之后每段用自己的实际行高，就不会互相牵连。
        const groups = [[]];
        for (const n of el.childNodes) {
          if (n.nodeType === 1 && n.tagName.toLowerCase() === 'br') groups.push([]);
          else groups[groups.length - 1].push(n);
        }
        for (const g of groups) emitText(el, cs, base, g, op, false);

        // 行内的纯装饰色块（压在字上的删除线、高亮条）不能跟着文字被吞掉，
        // 单独出形状，且要画在文字之上。
        for (const c of el.children) {
          const ccs = getComputedStyle(c);
          const cbg = ccs.backgroundColor;
          if (c.textContent.trim() === '' &&
              cbg !== 'rgba(0, 0, 0, 0)' && cbg !== 'transparent') {
            const cr = c.getBoundingClientRect();
            let rot = 0;
            const m = ccs.transform.match(/matrix\(([^)]+)\)/);
            if (m) {
              const [a, b] = m[1].split(',').map(parseFloat);
              rot = Math.round(Math.atan2(b, a) * 180 / Math.PI * 10) / 10;
            }
            out.push({tag: c.tagName.toLowerCase(), cls: '', kind: 'shape',
                      x: cr.left - pb.left, y: cr.top - pb.top, w: cr.width, h: cr.height,
                      bg: cbg, bdw: px(ccs.borderTopWidth), bdc: ccs.borderTopColor,
                      radius: px(ccs.borderRadius), shadow: ccs.boxShadow, rot,
                      op: op * opOf(ccs)});
          }
        }
        return;
      }
      // 混合内容：既有块级/替换子元素（svg、div…）又有裸文字。el.children 看不到文本节点，
      // 只递归 children 会让这些裸文字被静默丢掉（导出后凭空少字）。
      // 连续文本节点攒成一组，交给同一个 emitText 出框。
      let run = [];
      const flush = () => { if (run.length) emitText(el, cs, base, run, op, true); run = []; };
      for (const n of el.childNodes) {
        if (n.nodeType === 3) run.push(n);
        else if (n.nodeType === 1) { flush(); walk(n, op); }
      }
      flush();
    };

    // 页面容器之上的祖先（wrapper）也有 opacity：CSS 的 opacity 作用于整棵子树，
    // 所以初始值要把 pg 到 documentElement 的 opacity 全部乘进来，且只乘一次。
    const ancestorOpacity = (el) => {
      let o = 1;
      for (let n = el; n; n = n.parentElement) o *= opOf(getComputedStyle(n));
      return o;
    };
    for (const c of pg.children) walk(c, ancestorOpacity(pg));
    // 独立的浏览器参考文本：把导出器不会产出的对象临时隐藏（svg/canvas 截图、显式跳过、
    // display:none / visibility:hidden / opacity:0 子树），保证参考范围与导出范围一致。
    const hidden = [];
    for (const el of pg.querySelectorAll('*')) {
      const tagName = el.tagName.toLowerCase();
      let excluded = tagName === 'svg' || tagName === 'canvas';
      if (!excluded && skipClass && el.classList && el.classList.contains(skipClass)) excluded = true;
      if (!excluded) {
        let opacity = 1;
        for (let node = el; node; node = node.parentElement) {
          const cs = getComputedStyle(node);
          if (cs.display === 'none' || cs.visibility === 'hidden') { excluded = true; break; }
          opacity *= opOf(cs);
          if (opacity === 0) { excluded = true; break; }
        }
      }
      if (excluded) hidden.push(el);
    }
    const prior = hidden.map((el) => el.style.display);
    hidden.forEach((el) => { el.style.display = 'none'; });
    const ref = pg.innerText;
    hidden.forEach((el, i) => { el.style.display = prior[i]; });
    return {w: pb.width, h: pb.height, els: out, ref};
  });
  if (probeHost) probeHost.remove();   // 不能把探针留在页面上，后面的 SVG 截图会用原页面
  return result;
}
"""


async def render(html, selector, asset_dir, scale, skip_class=None):
    from playwright.async_api import async_playwright
    os.makedirs(asset_dir, exist_ok=True)
    async with async_playwright() as p:
        br = await p.chromium.launch()
        pg = await br.new_page(viewport={"width": 1920, "height": 1080},
                               device_scale_factor=scale)
        await pg.goto("file://" + os.path.abspath(html))
        await pg.wait_for_timeout(2500)
        pages = await pg.evaluate(JS, {"selector": selector, "skipClass": skip_class})
        for pi, page in enumerate(pages):          # SVG / canvas 单独截成 PNG
            for e in page["els"]:
                if e["kind"] == "svg":
                    name = f"p{pi+1:02d}_{e['tagName']}{e['seq']}.png"
                    await pg.locator(selector).nth(pi).locator(e["tagName"]).nth(e["seq"]) \
                            .screenshot(path=os.path.join(asset_dir, name), omit_background=True)
                    e["file"] = os.path.join(asset_dir, name)
        await br.close()
    return pages


# ─────────────────────────────────────────────────────────────
# 二、翻译成 PowerPoint 对象
# ─────────────────────────────────────────────────────────────

ALIGN = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "start": PP_ALIGN.LEFT,
         "right": PP_ALIGN.RIGHT, "end": PP_ALIGN.RIGHT, "justify": PP_ALIGN.JUSTIFY}


def parse_color(css):
    """'rgb(r,g,b)' / 'rgba(r,g,b,a)' → (RGBColor, alpha)。"""
    m = re.findall(r"[\d.]+", css or "")
    if len(m) < 3:
        return None, 0.0
    r, g, b = (int(float(v)) for v in m[:3])
    return RGBColor(r, g, b), (float(m[3]) if len(m) > 3 else 1.0)


def _alpha(clr_el, alpha):
    a = clr_el.makeelement(qn("a:alpha"), {})
    a.set("val", str(int(alpha * 100000)))
    clr_el.append(a)


class Builder:
    def __init__(self, cfg):
        self.cfg = cfg
        self.round_dir = os.path.join(cfg.asset_dir, "_round")

    # ── 文本 ──────────────────────────────────────────────
    def set_run_font(self, run, r):
        f = run.font
        f.size = Pt(r["fs"] * self.k)
        fw = str(r["fw"])
        f.bold = int(fw) >= 600 if fw.isdigit() else fw in ("bold", "bolder")
        f.italic = r.get("italic", False)
        f.underline = r.get("under", False)
        f.name = self.cfg.font_latin           # 只设了 latin，中文要另外指定
        col, alpha = parse_color(r["color"])
        alpha *= r.get("op", 1)              # 祖先链累乘的 CSS opacity
        if col:
            f.color.rgb = col
        rPr = run._r.get_or_add_rPr()
        for tag, val in (("a:ea", self.cfg.font_ea), ("a:cs", self.cfg.font_latin)):
            el = rPr.find(qn(tag))
            if el is None:
                el = rPr.makeelement(qn(tag), {})
                rPr.append(el)
            el.set("typeface", val)
        if r.get("ls"):
            rPr.set("spc", str(int(round(r["ls"] * self.k * 100))))   # 单位 1/100 pt
        if col and alpha < 1:
            solid = rPr.find(qn("a:solidFill"))
            if solid is not None and solid.find(qn("a:srgbClr")) is not None:
                _alpha(solid.find(qn("a:srgbClr")), alpha)

    def add_text(self, slide, e):
        """一个段落 → 一个文本框。

        宽度要放余量：视觉稿里这些框常是 flex 收缩包裹的，宽度恰好等于文字宽度，
        换到 PowerPoint 只要字体度量差一点点，最后一个字就会被挤到下一行。
        本来就是单行的段落直接关掉自动换行，从根上不可能折行。
        """
        k = self.k
        wrap = e.get("wrap", True)
        fs = e.get("fsMax") or e["fs"]     # 容器字号常常是继承来的小值，余量要按最大的字算
        pad = (fs * 0.25) if wrap else max(12.0, fs * 0.8)
        x, w = e["x"], e["w"] + pad
        ta = e.get("ta")
        if ta in ("center",):
            x -= pad / 2                   # 居中框两边一起放，视觉中心不动
        elif ta in ("right", "end"):
            x -= pad

        box = slide.shapes.add_textbox(Pt(x * k), Pt(e["y"] * k), Pt(w * k), Pt(e["h"] * k))
        tf = box.text_frame
        tf.word_wrap = wrap
        tf.auto_size = None
        tf.vertical_anchor = MSO_ANCHOR.TOP
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0

        paras = [[]]
        for r in e["runs"]:
            paras.append([]) if r.get("br") else paras[-1].append(r)
        paras = [p for p in paras if p] or [[]]

        for i, runs in enumerate(paras):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = ALIGN.get(ta, PP_ALIGN.LEFT)
            # 行距只对「这一段自己折了行」的框设。单行段落不设：量到的行盒高度比实际行间距
            # 大（那是字体行盒不是 CSS 行距），拿它当精确行距会把文字整体压下去；
            # 单行时交给 PowerPoint 按字号自然排，文字紧贴框顶，位置最准。
            if e.get("lines", 1) > 1 and e.get("lhEff"):
                p.line_spacing = Pt(e["lhEff"] * k)
            for r in runs:
                run = p.add_run()
                run.text = r["t"]
                self.set_run_font(run, r)
        return box

    # ── 形状 ──────────────────────────────────────────────
    def add_shape(self, slide, e):
        k = self.k
        rounded = e.get("radius", 0) >= 4
        shp = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE,
            Pt(e["x"] * k), Pt(e["y"] * k), Pt(e["w"] * k), Pt(e["h"] * k))
        shp.shadow.inherit = False
        opacity = e.get("op", 1)              # 祖先链累乘的 CSS opacity
        col, alpha = parse_color(e.get("bg"))
        alpha *= opacity
        if col and alpha > 0:
            shp.fill.solid()
            shp.fill.fore_color.rgb = col
            if alpha < 1:
                sf = shp.fill._xPr.find(qn("a:solidFill"))
                _alpha(sf.find(qn("a:srgbClr")), alpha)
        else:
            shp.fill.background()

        bcol, balpha = parse_color(e.get("bdc"))
        balpha *= opacity
        if e.get("bdw", 0) > 0 and bcol and balpha > 0:
            shp.line.color.rgb = bcol
            if balpha < 1:
                # python-pptx 没有描边透明度的公开 API，只能取 a:ln 元素；
                # 私有方法缺失时明确报告并保持不透明，不静默吞掉。
                try:
                    ln = shp.line._get_or_add_ln()
                except AttributeError:
                    ln = shp._element.spPr.find(qn("a:ln"))
                solid = ln.find(qn("a:solidFill")) if ln is not None else None
                if solid is not None and solid.find(qn("a:srgbClr")) is not None:
                    _alpha(solid.find(qn("a:srgbClr")), balpha)
                else:
                    print("   ⚠️ 无法给描边写透明度（python-pptx 结构变化），该描边按不透明导出")
            shp.line.width = Pt(e["bdw"] * k)
        else:
            shp.line.fill.background()

        if e.get("rot"):
            shp.rotation = -e["rot"]       # CSS 逆时针为负，PowerPoint 顺时针为正
        if rounded and e["w"] and e["h"]:
            # PowerPoint 的圆角是「短边的百分比」，换算回 CSS 的 px 半径
            shp.adjustments[0] = min(0.5, e["radius"] / min(e["w"], e["h"]))
        return shp

    # ── 图片 ──────────────────────────────────────────────
    def round_corners(self, path, radius_px, box_w):
        """PowerPoint 的图片没有圆角，把圆角烤进 PNG 的 alpha 通道。"""
        os.makedirs(self.round_dir, exist_ok=True)
        out = os.path.join(self.round_dir, f"{abs(hash((path, radius_px, box_w))) % 10**10}.png")
        if os.path.exists(out):
            return out
        im = Image.open(path).convert("RGBA")
        scale = im.width / box_w if box_w else 1
        r = int(min(radius_px * scale, min(im.size) / 2))
        mask = Image.new("L", im.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, im.width - 1, im.height - 1],
                                               radius=r, fill=255)
        im.putalpha(mask)
        im.save(out)
        return out

    def add_img(self, slide, e):
        k = self.k
        src = e.get("file") or e["src"]
        if not src or src.startswith("data:"):
            return None
        path = src if os.path.isabs(src) else os.path.normpath(os.path.join(self.html_dir, src))
        if not os.path.exists(path):
            print(f"   ⚠️ 找不到图片 {src}")
            return None
        if e.get("radius", 0) >= 2:
            path = self.round_corners(path, e["radius"], e["w"])
        pic = slide.shapes.add_picture(path, Pt(e["x"] * k), Pt(e["y"] * k),
                                       Pt(e["w"] * k), Pt(e["h"] * k))
        opacity = e.get("op", 1)
        # 截图型图片（svg/canvas）的 CSS 透明度已经在截图时烤进 PNG alpha，
        # 再写 alphaModFix 会二次相乘；只有真实 <img> 需要写 OOXML 透明度。
        if e.get("kind") == "img" and opacity < 1:
            blip = pic._element.blipFill.blip
            effect = blip.makeelement(qn("a:alphaModFix"), {"amt": str(int(opacity * 100000))})
            ext = blip.find(qn("a:extLst"))
            if ext is not None:
                ext.addprevious(effect)
            else:
                blip.append(effect)
        # box-shadow: rgba(...) 0 0 0 Npx 在视觉稿里通常是硬描边，翻译成图片边框
        m = re.match(r"rgba?\(([^)]+)\)\s+0px\s+0px\s+0px\s+([\d.]+)px", e.get("shadow") or "")
        if m:
            col, alpha = parse_color("rgba(" + m.group(1) + ")")
            if col and alpha > 0:
                pic.line.color.rgb = col
                pic.line.width = Pt(float(m.group(2)) * k)
        return pic

    # ── 装配 ──────────────────────────────────────────────
    def run(self, pages):
        cfg = self.cfg
        self.html_dir = os.path.dirname(os.path.abspath(cfg.html))

        if cfg.template:
            prs = Presentation(cfg.template)
            strip_slides(prs)                       # 模板自带的示例页删掉，母版/版式一个不动
        else:
            prs = Presentation()
            pw, ph = pages[0]["w"], pages[0]["h"]
            prs.slide_width, prs.slide_height = Pt(pw), Pt(ph)   # 1 CSS px = 1 pt

        # HTML 画布宽 → 幻灯片宽 的比例。画布 1920px 配 26.667in(=1920pt) 时正好是 1.0。
        self.k = (prs.slide_width / EMU_PER_PT) / pages[0]["w"]

        if cfg.layout:
            layout = next((l for l in prs.slide_layouts if l.name == cfg.layout), None)
            if layout is None:
                names = " / ".join(l.name for l in prs.slide_layouts)
                sys.exit(f"❌ 模板里没有版式「{cfg.layout}」。可选：{names}")
            killed = unblock_layout(layout, prs.slide_width, prs.slide_height)
        else:
            layout = prs.slide_layouts[6] if len(prs.slide_layouts) > 6 else prs.slide_layouts[0]
            killed = []

        n_text = n_shape = n_img = 0
        for page in pages:
            slide = prs.slides.add_slide(layout)
            for sh in list(slide.shapes):           # 版式带来的空占位符不留在页面上
                sh._element.getparent().remove(sh._element)
            if cfg.bg:
                set_bg(slide, cfg.bg)
            for e in page["els"]:
                if cfg.skip_class and cfg.skip_class in (e.get("cls") or "").split():
                    continue
                if e["kind"] == "shape":
                    self.add_shape(slide, e); n_shape += 1
                elif e["kind"] == "text":
                    self.add_text(slide, e); n_text += 1
                else:
                    if self.add_img(slide, e) is not None:
                        n_img += 1

        prs.save(cfg.out)
        return {"slides": len(prs.slides), "text": n_text, "shape": n_shape, "img": n_img,
                "killed": killed, "mb": os.path.getsize(cfg.out) / 1024 / 1024,
                "w": prs.slide_width / 914400, "h": prs.slide_height / 914400, "k": self.k}


# ─────────────────────────────────────────────────────────────
# 二点五、丢字校验（对照源 = 浏览器渲染后的 innerText）
# ─────────────────────────────────────────────────────────────

def _norm(t):
    return re.sub(r"\s+", " ", t or "").strip()


_DIFF_TOKEN_MAX = 64      # 单个 token 的上限，避免中文长段把一次比较放大成整段比较


def _tokens(t):
    """归一化文本 → token 序列；超长 token 切块，保证差异定位的成本与词数同阶。"""
    out = []
    for tok in t.split(" "):
        while len(tok) > _DIFF_TOKEN_MAX:
            out.append(tok[:_DIFF_TOKEN_MAX])
            tok = tok[_DIFF_TOKEN_MAX:]
        if tok:
            out.append(tok)
    return out


def _page_diff(want, got, window=12):
    """一页的差异：完全一致时 O(n) 返回；有差异才做有界的 token 级对齐。

    返回 (missing, extra)：missing 是参考文本里有、PPTX 里没有的片段；
    extra 是 PPTX 里有、参考文本里没有的片段（重复、意外增加、顺序错乱都会产生）。
    """
    if want == got:
        return [], []
    wt, gt = _tokens(want), _tokens(got)
    missing, extra = [], []

    def find(seq, token, start, stop):
        for k in range(start, min(stop, len(seq))):
            if seq[k] == token:
                return k
        return -1

    i = j = 0
    while i < len(wt) and j < len(gt):
        if wt[i] == gt[j]:
            i += 1; j += 1
            continue
        # 小窗口内重新对齐：哪一侧的锚点更近就先记哪一侧的差异
        del_at = find(gt, wt[i], j, j + window)      # wt[i] 出现在后面 → 中间是多余
        ins_at = find(wt, gt[j], i, i + window)      # gt[j] 出现在后面 → 中间是缺失
        if del_at != -1 and (ins_at == -1 or del_at - j <= ins_at - i):
            extra.append(" ".join(gt[j:del_at]))
            j = del_at
        elif ins_at != -1:
            missing.append(" ".join(wt[i:ins_at]))
            i = ins_at
        else:
            missing.append(wt[i])
            extra.append(gt[j])
            i += 1; j += 1
    if i < len(wt):
        missing.append(" ".join(wt[i:]))
    if j < len(gt):
        extra.append(" ".join(gt[j:]))
    missing = [m for m in missing if m]
    extra = [e for e in extra if e]
    if not missing and not extra:
        # want != got，但 token 化恰好把 64 字符块边界上的分隔符抹平了。
        # 完整文本不相等就绝不能判通过。
        return [want], [got]
    return missing, extra


def verify_text(refs, pptx_path):
    """逐页比对浏览器渲染文本与 PPTX 文本框：缺失、多余/重复、页数都要报。

    比较口径：空白归一化（连续空白→单空格、去首尾），大小写敏感。
    """
    prs = Presentation(pptx_path)
    page_count = None
    if len(refs) != len(prs.slides):
        page_count = {"reference": len(refs), "pptx": len(prs.slides)}
    missing, extra, reordered = [], [], []
    for ref, slide in zip(refs, prs.slides):
        want = _norm(ref)
        got = _norm(" ".join(sh.text_frame.text for sh in slide.shapes if sh.has_text_frame))
        m, e = _page_diff(want, got)
        missing.append(m)
        extra.append(e)
        # 同一页同时出现缺失和新增，通常就是文字顺序变了（也可能是一段被另一段替换）
        reordered.append(bool(m and e and len(" ".join(m)) >= 4 and len(" ".join(e)) >= 4))
    return {"missing": missing, "extra": extra, "reordered": reordered, "page_count": page_count}


def report_missing(result):
    missing, extra = result["missing"], result["extra"]
    count_error = result["page_count"]
    n_missing = sum(len(m) for m in missing)
    n_extra = sum(len(e) for e in extra)
    failed = bool(count_error or n_missing or n_extra)
    if count_error:
        print(f"❌ 验收失败：参考页数 {count_error['reference']}，PPTX 页数 {count_error['pptx']}")
    if n_missing:
        print(f"❌ 验收失败：{n_missing} 处参考文本未出现在 PPTX（空白已归一化，区分大小写）")
        for pi, segs in enumerate(missing):
            for sg in segs:
                print(f"   第 {pi+1} 页缺：{sg[:60]}{'…' if len(sg) > 60 else ''}")
    if n_extra:
        print(f"❌ 验收失败：{n_extra} 处 PPTX 文本不在参考文本中（重复/意外增加/顺序错乱）")
        for pi, segs in enumerate(extra):
            for sg in segs:
                print(f"   第 {pi+1} 页多：{sg[:60]}{'…' if len(sg) > 60 else ''}")
    if any(result.get("reordered") or []):
        pages = [str(i + 1) for i, r in enumerate(result.get("reordered") or []) if r]
        print(f"   第 {'、'.join(pages)} 页同时存在缺失与新增，请优先核对文字顺序")
    if not failed:
        print("🔍 文本完整性校验通过：没有丢字")
    return 1 if failed else 0


# ─────────────────────────────────────────────────────────────
# 三、模板相关的三个小手术
# ─────────────────────────────────────────────────────────────

def strip_slides(prs):
    """删掉模板自带的示例页；母版、版式、主题、色板一个不动。"""
    lst = prs.slides._sldIdLst
    for sld in list(lst):
        prs.part.drop_rel(sld.rId)
        lst.remove(sld)


def unblock_layout(layout, W, H):
    """删掉版式里铺满全屏的纯色矩形。

    有些官方模板的版式里放着一个和版式底色同色同尺寸的全屏矩形（冗余遮罩）。
    留着它，页面上任何放在它下面的东西都会被挡住；删掉不改变版式的外观。
    """
    killed = []
    for sp in list(layout.shapes):
        full = (sp.left == 0 and sp.top == 0 and sp.width and sp.height
                and sp.width >= W and sp.height >= H)
        if full and b"<a:solidFill>" in sp._element.xml.encode():
            sp._element.getparent().remove(sp._element)
            killed.append(sp.name)
    return killed


def set_bg(slide, rgb_hex):
    bg = slide._element.makeelement(qn("p:bg"), {})
    pr = slide._element.makeelement(qn("p:bgPr"), {})
    fill = slide._element.makeelement(qn("a:solidFill"), {})
    clr = slide._element.makeelement(qn("a:srgbClr"), {"val": rgb_hex.lstrip("#").upper()})
    fill.append(clr); pr.append(fill)
    pr.append(slide._element.makeelement(qn("a:effectLst"), {}))
    bg.append(pr)
    slide._element.find(qn("p:cSld")).insert(0, bg)


# ─────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="视觉稿 HTML → 可编辑 PPTX（读渲染后坐标，不改 HTML）")
    ap.add_argument("html")
    ap.add_argument("-o", "--out", required=True, help="输出 .pptx")
    ap.add_argument("--selector", default=".slide, .s, section",
                    help="每一页的 CSS 选择器（默认 '.slide, .s, section'）")
    ap.add_argument("--template", help="以这个 .pptx 为基底，继承它的母版/版式/主题/色板")
    ap.add_argument("--layout", help="每页套用的版式名（配合 --template）")
    ap.add_argument("--skip-class", help="跳过带这个 class 的元素，例如 logo 由版式提供时填 logo")
    ap.add_argument("--font-latin", default="Microsoft YaHei", help="西文字体名")
    ap.add_argument("--font-ea", default="微软雅黑", help="东亚字体名")
    ap.add_argument("--bg", help="每页底色，如 05070B；不给则用版式底色")
    ap.add_argument("--asset-dir", help="SVG/圆角图的落地目录（默认 输出同级 _pptx_assets/）")
    ap.add_argument("--scale", type=int, default=3, help="SVG 截图倍数（默认 3）")
    ap.add_argument("--dump-json", help="把量到的元素清单写出来，便于排查")
    cfg = ap.parse_args()

    cfg.out = os.path.abspath(cfg.out)
    cfg.asset_dir = cfg.asset_dir or os.path.join(os.path.dirname(cfg.out), "_pptx_assets")
    if cfg.layout and not cfg.template:
        sys.exit("❌ --layout 需要配合 --template 使用")

    pages = asyncio.run(render(cfg.html, cfg.selector, cfg.asset_dir, cfg.scale, cfg.skip_class))
    if not pages:
        sys.exit(f"❌ 选择器 '{cfg.selector}' 一页都没匹配到")
    if cfg.dump_json:
        json.dump(pages, open(cfg.dump_json, "w"), ensure_ascii=False, indent=1)

    kinds = {}
    for p in pages:
        for e in p["els"]:
            kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    print(f"📐 量到 {len(pages)} 页　{kinds}")
    # 先写目标目录下的临时文件，校验通过后才原子替换到正式路径：
    # 失败时既不留下"看起来成功"的产物，也不会覆盖已有的有效文件。
    publish = cfg.out
    fd, tmp_out = tempfile.mkstemp(prefix=".pptx-tmp-", suffix=".pptx",
                                   dir=os.path.dirname(publish) or ".")
    os.close(fd)
    try:
        cfg.out = tmp_out
        stats = Builder(cfg).run(pages)
        status = report_missing(verify_text([p["ref"] for p in pages], tmp_out))
        if status:
            print(f"   未发布：{os.path.basename(publish)} 保持原状")
            return status
        os.replace(tmp_out, publish)      # 同一目录内原子替换
        tmp_out = None
    finally:
        if tmp_out and os.path.exists(tmp_out):
            os.remove(tmp_out)

    print(f"✅ {stats['slides']} 页 → {os.path.basename(publish)}（{stats['mb']:.1f}MB）")
    print(f"   文本框 {stats['text']} · 形状 {stats['shape']} · 图片 {stats['img']}"
          + (f" · 清掉版式遮罩 {stats['killed']}" if stats["killed"] else ""))
    print(f"   画布 {stats['w']:.3f}×{stats['h']:.3f} inch（缩放 {stats['k']:.4f}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

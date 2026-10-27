#!/usr/bin/env bash
# render-narration.sh · 一条龙：HTML 解说动画 → 最终 MP4（带人声）
#
# 流水线：
#   1. render-video.js  录无声 MP4（按 timeline.totalDuration）
#   2. mix-voiceover.sh 混入 voiceover.mp3（可选 BGM）
#   3. 输出 <basename>-narrated.mp4
#
# Usage:
#   bash render-narration.sh <html> --timeline=<path> [options]
#
# Required:
#   <html>                解说动画的 HTML（应内嵌 NarrationStage + recording 模式 rAF 自驱）
#   --timeline=<path>     timeline.json 路径（自动读 totalDuration 和 voiceover.mp3 路径）
#
# Optional:
#   --bgm-mood=<name>     BGM 预设（educational / tech / tutorial / ...）
#   --bgm=<path>          自定义 BGM 文件
#   --bgm-volume=<0-1>    BGM 静态音量，默认 0.18
#   --no-ducking          关 sidechain ducking
#   --keep-silent         保留中间产物（无声 MP4），便于 debug
#   --seek                用 render-video-seek.js 逐帧 seek 渲染（真 60fps·确定性·无黑帧）
#   --seek-fps=<n>        seek 渲染帧率，默认 60，需配合 --seek
#   --out=<path>          输出路径，默认 <html-basename>-narrated.mp4
#   --width=<px>          视频宽度（默认 1920）
#   --height=<px>         视频高度（默认 1080）
#
# Examples:
#   bash render-narration.sh demo.html --timeline=_narration/timeline.json
#   bash render-narration.sh demo.html --timeline=_narration/timeline.json --bgm-mood=educational
#
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_ROOT="$SCRIPT_DIR/.."

HTML=""
TIMELINE=""
BGM_MOOD=""
BGM=""
BGM_VOLUME="0.18"
NO_DUCKING=""
KEEP_SILENT=""
USE_SEEK=""
SEEK_FPS="60"
OUT=""
WIDTH="1920"
HEIGHT="1080"

for arg in "$@"; do
  case "$arg" in
    --timeline=*)    TIMELINE="${arg#*=}" ;;
    --bgm-mood=*)    BGM_MOOD="${arg#*=}" ;;
    --bgm=*)         BGM="${arg#*=}" ;;
    --bgm-volume=*)  BGM_VOLUME="${arg#*=}" ;;
    --no-ducking)    NO_DUCKING="--no-ducking" ;;
    --keep-silent)   KEEP_SILENT="1" ;;
    --seek)          USE_SEEK="1" ;;
    --seek-fps=*)    SEEK_FPS="${arg#*=}" ;;
    --out=*)         OUT="${arg#*=}" ;;
    --width=*)       WIDTH="${arg#*=}" ;;
    --height=*)      HEIGHT="${arg#*=}" ;;
    -*)              echo "未知参数：$arg" >&2; exit 1 ;;
    *)               HTML="$arg" ;;
  esac
done

if [ -z "$HTML" ] || [ ! -f "$HTML" ]; then
  echo "Usage: bash render-narration.sh <html> --timeline=<path> [options]" >&2
  exit 1
fi
if [ -z "$TIMELINE" ] || [ ! -f "$TIMELINE" ]; then
  echo "✗ 缺 --timeline=<path>（timeline.json 由 narrate-pipeline.mjs 生成）" >&2
  exit 1
fi

# ── 从 timeline.json 读 totalDuration 和 voiceover 路径 ──
# 路径与数值只作为数据传给 node（argv），不拼进 JS 源码；totalDuration 必须是
# 有限正数且落在业务上限内，避免把任意字符串当表达式执行。
TIMELINE_DIR="$(cd "$(dirname "$TIMELINE")" && pwd)"
TOTAL_DURATION=$(node -e '
const fs = require("fs");
let t;
try { t = JSON.parse(fs.readFileSync(process.argv[1], "utf8")).totalDuration; }
catch (e) { console.error("timeline.json 无法解析：" + e.message); process.exit(2); }
const n = Number(t);
if (!Number.isFinite(n) || n <= 0 || n > 7200) {
  console.error("totalDuration 非法（要求 0 < n <= 7200）：" + JSON.stringify(t));
  process.exit(2);
}
process.stdout.write(String(n));
' "$TIMELINE") || exit 1
VOICEOVER_REL=$(node -e '
const fs = require("fs");
const v = JSON.parse(fs.readFileSync(process.argv[1], "utf8")).voiceover;
process.stdout.write(typeof v === "string" && v.trim() ? v : "voiceover.mp3");
' "$TIMELINE") || exit 1
case "$VOICEOVER_REL" in
  /*) VOICEOVER="$VOICEOVER_REL" ;;                 # 绝对路径按原样使用
  *)  VOICEOVER="$TIMELINE_DIR/$VOICEOVER_REL" ;;
esac

if [ ! -f "$VOICEOVER" ]; then
  echo "✗ voiceover.mp3 不存在: $VOICEOVER" >&2
  exit 1
fi

# 录制时长 = 总时长 + 1s 安全缓冲
RECORD_DURATION=$(node -e '
const n = Number(process.argv[1]);
if (!Number.isFinite(n) || n <= 0) process.exit(2);
process.stdout.write(String(Math.ceil(n + 1)));
' "$TOTAL_DURATION") || exit 1

HTML_ABS="$(cd "$(dirname "$HTML")" && pwd)/$(basename "$HTML")"
HTML_DIR="$(dirname "$HTML_ABS")"
HTML_BASE="$(basename "$HTML" .html)"
SILENT_MP4="$HTML_DIR/$HTML_BASE.mp4"

if [ -z "$OUT" ]; then
  OUT="$HTML_DIR/$HTML_BASE-narrated.mp4"
fi

# 中间产物是渲染器按 HTML 基名固定写出的文件。它若已存在，我们无法证明归属，
# 覆盖或清理都会毁掉用户文件；直接拒绝并让用户先移走。--out 与它同路径同样拒绝。
if [ -e "$SILENT_MP4" ]; then
  echo "✗ 中间产物已存在，拒绝覆盖/删除: $SILENT_MP4（请先移走再重跑）" >&2
  exit 1
fi
OUT_DIR="$(dirname "$OUT")"
if [ ! -d "$OUT_DIR" ]; then
  echo "✗ 输出目录不存在: $OUT_DIR" >&2
  exit 1
fi
OUT_ABS="$(cd "$OUT_DIR" && pwd)/$(basename "$OUT")"
if [ "$OUT_ABS" = "$SILENT_MP4" ]; then
  echo "✗ --out 不能与中间产物同路径: $OUT_ABS" >&2
  exit 1
fi

echo "═══ render-narration ═══════════════════"
echo "  HTML:        $HTML_ABS"
echo "  Timeline:    $TIMELINE"
echo "  Voiceover:   $VOICEOVER"
echo "  Total dur:   ${TOTAL_DURATION}s (录 ${RECORD_DURATION}s)"
echo "  尺寸:        ${WIDTH}×${HEIGHT}"
[ -n "$BGM_MOOD" ] && echo "  BGM mood:    $BGM_MOOD"
[ -n "$BGM" ] && echo "  BGM:         $BGM"
echo "  最终输出:    $OUT"
echo "════════════════════════════════════════"

# ── Step 1: 录无声 MP4 ──────────────────────
echo ""
if [ -n "$USE_SEEK" ]; then
  echo "▸ Step 1/2 · 逐帧 seek 渲染 HTML 动画 (无声 · ${SEEK_FPS}fps 确定性)"
  NODE_PATH=$(npm root -g) node "$SCRIPT_DIR/render-video-seek.js" "$HTML_ABS" \
    --duration="$RECORD_DURATION" \
    --fps="$SEEK_FPS" \
    --width="$WIDTH" \
    --height="$HEIGHT"
else
  echo "▸ Step 1/2 · 录制 HTML 动画 (无声)"
  NODE_PATH=$(npm root -g) node "$SCRIPT_DIR/render-video.js" "$HTML_ABS" \
    --duration="$RECORD_DURATION" \
    --width="$WIDTH" \
    --height="$HEIGHT"
fi

if [ ! -f "$SILENT_MP4" ]; then
  echo "✗ 无声 MP4 没生成: $SILENT_MP4" >&2
  exit 1
fi

# ── Step 2: 混入人声 ──────────────────────
echo ""
echo "▸ Step 2/2 · 混入人声"
MIX_ARGS=("$SILENT_MP4" "--voiceover=$VOICEOVER" "--out=$OUT")
[ -n "$BGM_MOOD" ] && MIX_ARGS+=("--bgm-mood=$BGM_MOOD")
[ -n "$BGM" ]      && MIX_ARGS+=("--bgm=$BGM")
[ -n "$BGM_MOOD$BGM" ] && MIX_ARGS+=("--bgm-volume=$BGM_VOLUME")
[ -n "$NO_DUCKING" ] && MIX_ARGS+=("$NO_DUCKING")

bash "$SCRIPT_DIR/mix-voiceover.sh" "${MIX_ARGS[@]}"

if [ ! -f "$OUT" ]; then
  echo "✗ 混音完成但最终输出不存在: $OUT" >&2
  exit 1
fi

# 只清理本次创建的中断产物（运行前已确认它不存在）。
if [ -z "$KEEP_SILENT" ]; then
  rm -f "$SILENT_MP4"
fi

echo ""
echo "✓ 完成: $OUT"
if [ -n "$KEEP_SILENT" ]; then
  echo "  (中间产物保留: $SILENT_MP4)"
fi
exit 0

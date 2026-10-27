# Security & Data-Flow Statement

This document exhaustively declares every network destination, credential touchpoint, subprocess, and deletion this skill can perform, so that users and automated security reviewers can verify the claims against the code.

**TL;DR: the core pipeline (HTML design → render → MP4/PDF/PPTX export) runs locally with zero network calls and zero API keys. Network access exists only in explicit optional paths: `scripts/cloud/*` (vendor APIs, own keys, consent gate), `scripts/fetch_images.py` (Wikimedia/brand assets), and the optional ZCode adapters `scripts/zcode_image.py` / `scripts/zcode_vision.py` (local CPA proxy, default `http://127.0.0.1:8317`; the adapter follows the configured `baseUrl`, key read from ZCode's provider config or `ZCODE_CPA_BASE_URL` / `ZCODE_CPA_API_KEY`). Other runtimes do not need these adapters or any `~/.zcode` path. There is no telemetry. No data is ever sent to any server controlled by the skill author.**

## Complete list of network destinations

| Host | Where | What is sent | When |
|---|---|---|---|
| `ark.cn-beijing.volces.com` (Volcengine Ark, ByteDance official API) | `scripts/cloud/ai-review-video.py` | Compressed segments of **your own rendered video**, for AI quality review, authenticated with **your own** `ARK_API_KEY` | Only when you run it, and only after the consent gate |
| `openspeech.bytedance.com` (ByteDance official TTS API) | `scripts/cloud/tts-doubao.mjs` (also invoked by `scripts/narrate-pipeline.mjs`) | The narration text you want synthesized, with **your own** key. The endpoint is validated against a hardcoded hostname allowlist (`*.bytedance.com` / `*.volces.com`) — a tampered `.env` cannot redirect your key or text elsewhere | Only when you run it, and only after the consent gate |
| `commons.wikimedia.org` (official Wikimedia API) | `scripts/fetch_images.py` | Image search keywords; downloads CC/public-domain images with license info printed for review | Only when the agent fetches stock imagery for a content design |
| Brand official websites, `simpleicons.org`, Google favicon service | `references/brand-asset-protocol.md` (instructions, no script) | Plain GET requests to download publicly served logos/brand assets | Only when you ask for a brand-specific design |
| `fonts.googleapis.com`, `unpkg.com` and similar CDNs | Static `<link>`/`<script>` tags inside demo/output HTML | Standard browser font/library fetches when *you* open a generated HTML file | Browser-side only; render scripts work offline-first |
| **Local CPA proxy** (default `http://127.0.0.1:8317`; follows configured `baseUrl`; OpenAI-compatible images endpoint) | `scripts/zcode_image.py` | Your image prompt, size/quality parameters, and any `--ref` reference images (base64) | Only when you explicitly run the script; no consent flag because it targets the local proxy |
| **Local CPA proxy** (default `http://127.0.0.1:8317/v1/responses`; follows configured `baseUrl`) | `scripts/zcode_vision.py` | The image you pass for visual review plus your review prompt | Only when you explicitly run the script; no consent flag because it targets the local proxy |
| **OpenAI image generation** — *methodology path via the separate `huashu-gpt-image` skill* | `references/gpt-visual-workflow.md` + `scripts/zcode_image.py` | Your image prompts, sent to the local CPA proxy (or the external skill's configured endpoint) | Only in the optional GPT visual-concept path, on the same principle as any normal paid-LLM call made within an agreed design task (see *Image generation* below) |

That is the entire list. `grep -rn "urlopen\|requests\.\|fetch(" --include="*.py" --include="*.mjs" --include="*.js" --include="*.sh" scripts/` to verify; every hit must map to a row above.

## API keys

- No key is hardcoded anywhere; the repo ships only `.env.example` placeholders (`.env` is gitignored).
- Cloud scripts read keys from the **skill's own root `.env`** or process environment. The two ZCode adapters (`zcode_image.py`, `zcode_vision.py`) are host-specific and optional: they read the local CPA key from ZCode's provider config (`~/.zcode/v2/provider_config.json`, path overridable with `ZCODE_PROVIDER_CONFIG`) unless both `ZCODE_CPA_BASE_URL` and `ZCODE_CPA_API_KEY` are set, in which case no local config file is needed. They never print, copy, or persist the key. `ai-review-video.py` extracts only the single `ARK_API_KEY` variable; it does not load the rest of the file into the environment.
- Cloud-script keys are transmitted only to the corresponding vendor endpoint listed above, over HTTPS, as auth headers. The ZCode adapters send the CPA key to the configured proxy (default loopback HTTP), not to a public host.
- `references/react-setup.md` option B (pasting an Anthropic key into a demo page input) is explicitly marked local-demo-only and not recommended; the default options require no key at all.

## Explicit consent gate

Both cloud scripts print exactly what will be sent to which host and exit before any network call unless you pass `--yes` or set `HUASHU_CLOUD_OK=1`. Local render/export paths never need the gate because they do not leave your machine. The ZCode adapters talk only to the configured local CPA proxy (default loopback `127.0.0.1:8317`) and are invoked explicitly (no hidden background calls).

## Image generation (GPT visual-concept workflow)

`references/gpt-visual-workflow.md` adds an **optional** GPT visual-concept path that generates concept images, HTML validation assets, and production image assets. The actual call is made by `scripts/zcode_image.py` (local CPA proxy adapter) or by the separate `huashu-gpt-image` skill; this skill defines *when* it may be used. Three boundaries apply:

- **Scope & cost.** Image generation is a **normal model capability**, used on the same principle as an everyday coding agent calling a paid LLM: when the task is a `needs-new-visual-direction` design task (or a verification/production-asset need within an already-agreed task), the agent **generates directly — no per-call paid approval is required**. It states which model, which route and whether it is billed (a *notice*, not an *approval*), records the model / image count / usage for traceability, and keeps cost sane: one image per direction by default, no "just to probe" generation, no unconditional retries, reference-image editing (`--ref`) for tweaks, reuse of already-generated assets. A genuinely larger scope (e.g. batch production assets) is handled as a **normal task-scope change** with the user — **not** by restoring per-image approval. The zero-cost probe (`--health`) still runs freely. If the generation path is unavailable the skill must **report the technical limit and pause that step** (and may hand over the finished prompts to run elsewhere) — it must **not** silently substitute placeholder images or code-drawn stand-ins for visuals the design depends on (which would silently corrupt the visual review).
- **Credentials.** This skill never stores, echoes, or commits image-generation keys. `scripts/zcode_image.py` reads the CPA key from ZCode's provider config or the `ZCODE_CPA_BASE_URL` / `ZCODE_CPA_API_KEY` environment pair at call time (it does not print or persist it); the external `huashu-gpt-image` path supplies its own credentials through its environment / local proxy configuration. Keys are never printed in reports and never embedded in generated HTML, images, or deliverables.
- **What is NOT relaxed.** Removing per-call approval does **not** permit changing CPA credentials, model routing or account-billing configuration, opening new paid services, widening file/system/network permissions, or bypassing any other authorization rule (Git push, release, production changes still require their own authorization — see the repo's Git and high-risk rules).

## Subprocesses

All subprocess calls invoke local media tools only: `ffmpeg`, `ffprobe`, `ffplay`, Playwright/Chromium for HTML rendering and screenshots. No shell-to-network combinations, no curl-pipe-sh patterns.

## File deletion

Recursive deletion is limited to temp directories the scripts themselves create with unique timestamp+PID names (`.video-tmp-*`, `.seek-tmp-*`, `_narration/.tmp`, Python `tempfile.TemporaryDirectory`). No script ever deletes user data or anything outside its own scratch space.

## Dependencies

Mainstream registry packages only (`playwright`, `sharp`, `pptxgenjs`, `pdf-lib`, `requests`), installed via standard `npm`/`pip`/`uv` — no binary downloads from arbitrary URLs. One documented exception to be aware of: `npx hyperframes init` (optional animation backend, see `references/hyperframes-backend.md`) installs 19 hyperframes documentation skills into `~/.claude/skills/`. This is called out with a warning in the docs before the command.

## Hooks

`scripts/design-gate-hook.sh` is **never installed automatically** — nothing in this skill writes to `settings.json`. If you manually opt in, it is a **preventive gate for recognizable common local render commands**: it parses the Bash tool command with `python3` and exits 2 when it recognizes a long (≥45s) render whose project has no `direction-approved.md`, unless the same command carries a leading/exported `SKIP_DESIGN_GATE=1`.

- **Coverage**: direct render entry points (`render-video.js`, `render-video-seek.js`, `render-narration.sh`), `npm/pnpm/yarn run render*`, `npx hyperframes render`, `node` render scripts; quoting, common wrappers, absolute shell/npm/node paths, `bash -c`, subshells/braces, unconditional `cd` chains, definite `&&`/`||` outcomes, literal `if true/false`, truly empty `for i in;`, `while false`, `until true`, uncalled function definitions, and readable local shell scripts. Duration: JS entry points use the first explicit `--duration=<num>` > the known 30s default and do not read HTML; the space form `--duration 60` is not a renderer-supported duration; unknown npm/hyperframes use explicit > project `data-duration` > fail; `render-narration.sh` reads `--timeline`'s `totalDuration` plus the 1s recording buffer. Plain text commands are not blocked merely for containing render words.
- **Fail-closed, not guaranteed**: control flow that can reach a render and may change its context (non-literal conditions/loops, executable `until` including `until false`, `while`, non-empty or quoted-empty `for`, `case`, function calls including quoted/escaped calls and source-defined functions, command substitution that can affect an assignment, command position, or `eval` target), `--workspace`/`-w`/`--filter`/`--workspaces`/multiple workspaces, unverified yarn target flags, npm `--cwd` (not a supported target mapping), dynamic directories, or unknown duration. Commands with **no recognizable render entry** (for example a read-only `for ...; do cd ...; sha256sum ...; done`) are not blocked merely for containing control flow. The cases above are not treated as safely covered or allowed.
- **Not guaranteed**: commands piped into a shell (`... | bash`, `bash -s`, `bash < file`, `cat <<EOF | bash`); SSH/container/remote execution; commands assembled inside Python/Node or other interpreters; unresolved `eval`/variables; command/process substitution (`eval "$(...)"`, `source <(...)`); environment shell functions/aliases; `make`, build scripts, or other indirect renderers; symlinked/renamed non-shell renderers; dynamic `cd $(...)`; other execution paths that cannot be reliably parsed.
- **Exit semantics**: `python3` missing, unparseable JSON input, invalid/unknown cwd, an unresolved target/workspace, control flow that may change the render context, an unresolvable duration without a confirmed Gate, or a resolved duration ≥45s without a Gate → fail closed (exit 2). Only an explicit short duration, a readable short `data-duration`, the known 30s render-video default, or an unresolvable duration with a confirmed Gate is allowed (exit 0). **Exit 0 does not mean every execution path passed the Gate.** An unexpected parser exception exits non-zero (not guaranteed to be exactly 2) and must not be treated as a pass; such cases are not individually enumerated in the test matrix.
- **No relaxation**: these limits describe enforcement only. The Gate protocol in `SKILL.md` remains mandatory; hook limitations are not an exemption.
- **Side effects**: it reads the tool JSON, `index.html` for `data-duration` in the current directory or up to two parent directories, `--timeline` JSON for `totalDuration`, and readable local shell scripts (up to 1 MB; larger scripts are conservatively blocked). It makes no network calls, writes nothing, deletes nothing.

## Proxy handling note

`fetch_images.py` and `ai-review-video.py` disable inheriting proxy environment variables (`trust_env = False` / clearing `ALL_PROXY` etc.) for their own requests. This exists to survive stale local proxy configurations that break TLS — not to evade monitoring. If you need these requests to go through your proxy, set it explicitly in the script invocation.

## Reporting

Found something that contradicts this document? Please open an issue — a mismatch between this file and the code is treated as a bug.

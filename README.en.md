<sub>🌐 <a href="README.md">中文</a> · <b>English</b></sub>

<div align="center">

# DesignWise

### App UI design and delivery for AI agents

[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Agent](https://img.shields.io/badge/Agent-Agnostic-blueviolet)](https://skills.sh)
[![skills.sh](https://img.shields.io/badge/skills.sh-Compatible-green)](https://skills.sh)

One job, end to end: take an App UI requirement from **product understanding** to **on-device acceptance** — GPT generates three real concept directions, Copilot picks the best one from real pixels, an HTML high-fidelity prototype validates the experience, and the result is translated into a native app and verified on a real device.

```bash
npx skills add tongsailong/designwise
```

[Standard flow](#the-one-standard-flow) · [Product principles](#product-principles) · [Image generation & assets](#gpt-image-generation-and-asset-reuse) · [Scope](#scope) · [Install](#install) · [Dependencies](#supported-platforms-and-dependencies) · [Upstream & credits](#upstream-project-and-credits)

</div>

> **TL;DR**
> **What it is** — a design skill that serves **App UI only**: information architecture, navigation, layout, visual and interaction specs, HTML high-fidelity prototype, native translation, image asset generation and reuse, on-device acceptance.
> **How it runs** — one standard flow, no L1/L2/L3 tiers: product understanding → 3 GPT concept directions → Copilot direction selection → HTML prototype → assets → native implementation → on-device acceptance.
> **What cannot be skipped** — the three real concept images and Copilot's selection based on real pixels. Local iteration reuses the chosen direction and does not re-explore.
> **What it does not do** — slides, video, audio, infographics, posters, production web apps, backend systems.

> ℹ️ **This project is an independent fork of [huashu-design](https://github.com/alchaincyf/huashu-design) (by [@alchaincyf](https://github.com/alchaincyf), MIT License).** It keeps the upstream visual methodology, style library, asset protocol and delivery chain, and preserves `LICENSE` and attribution as MIT requires (see [Upstream & credits](#upstream-project-and-credits) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)). **The fork is maintained independently**: it does not follow upstream releases, and at runtime it depends on neither upstream nor any other skill.

---

## The one standard flow

**There are no task tiers.** Every new App UI task runs the same flow, gated by **evidence**, not by approval ceremony.

| Stage | Goal | Evidence gate |
|---|---|---|
| **0 Intake & product understanding** | Pin down the real need and constraints | Facts and constraints have sources; native feasibility recorded |
| **1 Design goal & assumptions** | Fix the inputs for direction exploration | Three directions can be generated from it; no unlabelled assumptions |
| **2 Three GPT concept directions** | Explore 3 structurally different directions in real pixels | 3 real, decodable, same-ratio images with distinguishable structure and unbroken hard constraints |
| **3 Copilot direction selection** | Pick the best direction from real pixels | All 3 images in the request; identity check passed; verdict includes per-image differences and rationale |
| **4 HTML high-fidelity prototype** | Turn the chosen direction into real interactive visuals | Real render; zero console errors; states/contrast/touch targets pass |
| **5 Design refinement & asset generation** | Complete the visual assets, keep them reusable | Every asset has provenance, sha256, consumers; no unresolved temp images |
| **6 Native App implementation** | Translate the design into native UI | Build succeeds, install succeeds, app launches, key flows work |
| **7 On-device acceptance** | Prove the result on a real device | Every acceptance item has fresh real evidence; verdict is one of three states |

### Three rules that never bend

1. **The three directions must be real, structurally different, and share one set of product constraints.** All three prompts reuse the same **task block** (product / users / the page's core problem / hard constraints / prohibitions) and the same **principle translation block** (turning "useful → understandable → comfortable → meaningful" into checkable requirements for this page, not restating the principle names); only the direction block differs — layout skeleton / information organisation / visual motif. Swapping colours, spacing or corner radii is not a direction, and neither is adding or removing business behaviour. One prompt per direction, one real generation each, portrait `1024x1536` by default for App, same ratio/size/model across the three so they can be compared side by side.
2. **Copilot judges eligibility first, then selects the direction from real pixels.** The executing agent may not pick a direction and then claim a Copilot verdict, and may not substitute text summaries, filenames or thumbnails for real images. The evidence bridge puts all three images inside the request; `CONSULT` first returns a pass/fail eligibility verdict per direction, then recommends one of the eligible directions with per-image differences, rationale, opportunity cost and risks. If all three violate key product principles or necessary constraints, Copilot **may reject them all** and give concrete prompt fixes; ZCode then regenerates only the affected directions. **Fail closed** — missing image, image not actually in the request, failed identity check, a reply admitting it cannot see the images, a generic non-committal evaluation, or picking "the least bad" without an eligibility check is not a verdict.
3. **HTML is a prototype, not the product.** The prototype covers only the selected direction and exists to judge visuals and interaction; the final implementation must be a native app, and the prototype HTML must never be embedded into the app as the implementation.

**Local iteration** (copy, spacing, a single component state, bug, adaptation, replacing a registered asset) reuses `design-brief.md` + the three-image record + `direction-approved.md` and resumes at stage 4 without re-exploring directions. **Substantive change** (new/replaced design tokens or visual motif, IA or navigation change, cross-screen visual system, brand exploration, new core flow) is treated as a new task and runs 0–7 again.

---

## Product principles

**Order: useful → understandable → comfortable → meaningful. If an earlier layer fails, a later one cannot compensate.**

| Layer | The question | Cost of getting it wrong |
|---|---|---|
| **Useful** | Does it serve a real need and a real task, or something we think should exist? | Attractive but unneeded = refined slop |
| **Understandable** | How much effort does understanding take? Who carries the complexity? | The feature exists but cannot be found or read = it does not exist |
| **Comfortable** | Any pointless steps, or interactions that fight platform habits? | One extra step and thought every time = long-term friction |
| **Meaningful** | Can the direction explain which positioning, scenario and users it serves? | Style lottery; points, badges or animation standing in for real value |

- **Gamification is an optional means, not a product goal.** No mandatory points, badges, leaderboards, streaks or quest systems; no forced tasks, loss anxiety, fake scarcity, punitive streaks or excessive competition; never trade long-term value for short-term activity. Choosing not to gamify can be the better design.
- **Autonomy, mastery and growth are lenses, not a feature checklist.** No product, screen or release has to provide all three at once.
- **Professional information density is legitimate.** Tools, data and context-aware products may be dense; but every piece must carry content value — decorative icons, meaningless stats and status dots are still slop.
- **The system carries the complexity.** What the system should judge, merge or explain is not pushed onto the user as step-by-step manual work.

Full method: [`references/product-value.md`](references/product-value.md). Stage-by-stage application: [`references/app-visual-workflow.md`](references/app-visual-workflow.md).

---

## GPT image generation and asset reuse

Image generation is built in and depends on no other skill: `scripts/zcode_image.py` talks to an OpenAI-compatible image endpoint (default `gpt-image-2.5`) and supports `--health` for a zero-cost check, plus `--ref` reference images, `--size` / `--fit` sizing and cropping, and `--n` batching. Credentials come from environment variables or the local provider config and are never committed.

- **Used across the flow**: direction concepts (stage 2) → filling in prototype visuals (stage 4) → local elements, illustrations, backgrounds, decoration (stage 5). All three share one visual language, reference set, sizing and cropping rules.
- **Reuse first, generate second**: check `asset-manifest.json`, existing project assets, and already-registered concept and prototype assets. If an asset fits, do not regenerate it, and do not re-generate for microscopic differences.
- **Three asset states**: reference image (judgement input, not output) / concept image (direction comparison only) / production asset (shippable). Concept images never ship as production assets.
- **The manifest is the single source of truth**: `asset-manifest.json` records id, path, sha256, type, source, provenance (model/prompt/references), variants, consumers, licence and status. `scripts/asset_manifest.py` registers and verifies entries (missing files, hash mismatches and leftover temp images fail).
- **Processing and conversion**: sizing, cropping, transparency, compression, format and colour run through the local Pillow toolchain. CSS `object-fit: cover` and native `CENTER_CROP` are not the same thing — **focal points and crop parameters must be recorded**; px and dp/sp are never mixed.
- **If generation is unavailable**: report it and pause that step. You may hand over complete prompts for external generation, then continue from **real returned files**; never silently substitute HTML/SVG drawings for concept images, and never let placeholders masquerade as restored visuals.

---

## Scope

| Capability | Deliverables |
|---|---|
| Product understanding & design goal | `design-brief.md` (need, constraint tiers, success criteria, non-goals, assumptions) |
| Direction exploration | 3 real concept images + `concept-prompts.md` + `concept-index.json` (with sha256) |
| Direction verdict | `direction-approved.md` (Copilot recommendation, per-image differences, rationale, risks, adopted direction) |
| High-fidelity prototype | `prototype/index.html` (single-page inline React, libraries vendored locally, real device frame, clickable), baseline screenshots, `prototype-notes.md` |
| Asset system | `assets/`, `asset-manifest.json`, generation and reuse log |
| Native handoff | Native package (structure / tokens / states / assets / adaptation / accessibility / baselines) |
| Native implementation & acceptance | Build and install logs, on-device screenshots/recordings, `verification-report.md` |

**In scope**: iOS / Android mobile app interface and interaction design, and carrying it through to a native app.

**Out of scope**: slides / decks, video / motion pieces / promo films, voice-over / audio / music / SFX, infographics / posters / covers and other static print-like media, production web apps and backend systems, pure code refactors, layer-editable PPTX.

---

## Install

```bash
npx skills add tongsailong/designwise
```

Self-check after installing (this skill is more than `SKILL.md`):

```bash
python3 scripts/check-skill.py            # structure + reference integrity (exit 0 required)
python3 scripts/check-skill.py --strict   # additionally reports orphan files
```

If only `SKILL.md` shows up in the install directory, your `skills` CLI is too old (≤1.5.15 had a single-file sync bug, fixed in 1.5.19):

```bash
npm i -g skills@latest        # or npx skills@latest add tongsailong/designwise
```

Otherwise clone the repo into any skills directory:

```bash
git clone https://github.com/tongsailong/designwise.git ~/.claude/skills/designwise
```

### Example prompts

```
"Build an AI pomodoro iOS prototype — four core screens, actually clickable"
"Our budgeting app home screen is a mess; redesign it and give me real directions"
"Turn this design into a native Android UI and verify it on my test device"
"Add a set of illustrations and backgrounds to this screen, reusing the existing visual language"
"Check contrast, font scaling and empty states on the device"
```

---

## Supported platforms and dependencies

**Agent support**: Claude Code · Codex · Cursor · Trae · OpenClaw · Hermes Agent, or any agent that supports markdown-based skills. Capabilities are decoupled from carriers: docs state what a step needs (file I/O, local commands, real image generation, browser rendering, Copilot verdict, on-device evidence, public search) and the agent maps that to its own tools. See [`references/runtime-adapters.md`](references/runtime-adapters.md).

**Local toolchain** (as needed):

| Dependency | Used for |
|---|---|
| Node.js | `scripts/check-ui.mjs` (structure/overflow/images/contrast collection, `--shot` screenshots, `--ledger-*` appearance ledger; no npm deps), Playwright browser verification |
| Python 3 | `scripts/zcode_image.py` (real generation), `scripts/verify.py` (Playwright render + screenshots), `scripts/check-contrast.py`, `scripts/asset_manifest.py`, `scripts/ref_board.py` (reference board, needs Chrome), `scripts/extract_grid.py` / `contact_sheet.py` / `chroma_key.py` (image processing), `scripts/check-skill.py`; Pillow (image I/O, optional but recommended) |
| Playwright + Chromium | Real rendering, click tests and baseline screenshots for the HTML prototype |
| Android SDK / Xcode | Native builds; on-device installs go only through the host-authorised installer (see [SECURITY.md](SECURITY.md)) |

**Image credentials**: `ZCODE_CPA_BASE_URL` / `ZCODE_CPA_API_KEY`, or the local `~/.zcode/v2/provider_config.json`. Not distributed with the repo, never written into deliverables.

---

## Limitations

- **App UI only.** For slides, video, audio, infographics or a production web app, this is not the right tool.
- **Concept images are not UI truth.** Text, fake controls and impossible effects in them must be corrected against real product and platform rules, with corrections recorded in `prototype-notes.md`.
- **CSS px in the HTML prototype cannot prove Android 48dp.** dp/sp must be measured natively against density and font scaling.
- **On-device evidence cannot be substituted.** If the device is offline or the toolchain is missing, mark `PARTIAL` / `BLOCKED` — never "passed".
- **A completely blank brand designed from nothing will lose quality.** Drawing hi-fi out of thin air is a last resort.

---

## Repository layout

```
designwise/
├── SKILL.md                 # agent entry point (single routing authority)
├── README.md                # Chinese README
├── README.en.md             # English README (this file)
├── SECURITY.md              # security and data-flow statement
├── THIRD_PARTY_NOTICES.md   # full third-party licence text for ported code
├── LICENSE                  # MIT
├── references/              # method detail, read by stage
│   ├── app-visual-workflow.md   # stages 0–7 in full
│   ├── image-generation.md      # prompt method, sizes, quality
│   ├── image-assets.md          # asset states, manifest, reuse, provenance
│   ├── design-handoff.md        # native package and token mapping
│   ├── app-prototype.md         # HTML prototype spec
│   ├── verification.md          # HTML and native evidence chain
│   ├── product-value.md         # product principles
│   ├── critique-guide.md        # design review
│   ├── design-styles.md         # native-HTML style library
│   ├── design-research.md       # reference board and appearance ledger
│   ├── brand-asset-protocol.md  # five-step brand asset protocol
│   ├── routing-table.md · workflow.md   # flow quick reference and expansion
│   └── runtime-adapters.md · zcode-host.md  # host capability mapping
├── assets/                  # starter components and specimens
│   ├── ios_frame.jsx · android_frame.jsx · design_canvas.jsx
│   └── style-specimens/     # style specimens (App / CJK-East Asian)
├── scripts/                 # generation / processing / verification / gates / sync
└── demos/                   # capability demos (zh + en HTML)
```

> `test-prompts.json` is an **acceptance prompt set** (an assertion checklist run manually or in-session), not an automated test framework; `scripts/check-skill.py` only checks that it exists.

### Maintainers: source repo and runtime copy

This repository (git working tree) is the **only source**; the agent's skills directory is a **runtime copy** written one-way by `scripts/sync_runtime.py`. Do not hand-edit the copy:

```bash
python3 scripts/sync_runtime.py --to ~/.zcode/skills/designwise --check   # 0 = no drift
python3 scripts/sync_runtime.py --to ~/.zcode/skills/designwise --apply   # write missing/different files
python3 scripts/sync_runtime.py --to ~/.zcode/skills/designwise --apply --prune  # delete extra files in target (dangerous)
```

The script excludes `.env` / `.env.*` (keeping `.env.example`), `assets/personal-asset-index.json`, `.git`, `node_modules`, `design-demos`, `__pycache__`, and the **development assets**: root `AGENTS.md`, `scripts/test_*.py` and `.zcode/`. **`LICENSE` always ships with the copy** (MIT obligation; never exclude or trim it). Exclusions apply symmetrically to source and copy, so development assets that were already in the copy before the exclusion existed are neither reported as drift by `--check` nor deleted by `--prune`; clean them separately. See [`references/zcode-host.md`](references/zcode-host.md).

---

## Upstream project and credits

The visual methodology and part of the assets come from upstream:

**[花叔Design · huashu-design](https://github.com/alchaincyf/huashu-design)** — by [@alchaincyf](https://github.com/alchaincyf) (花生 / 花叔), MIT License.

- Star history: <https://star-history.com/#alchaincyf/huashu-design&Date>
- **Specimen assets**: `assets/style-specimens/` comes from the same upstream path and is byte-identical. Upstream publishes the repo under the MIT License; the specimens are original HTML/CSS interpretations (subjects and figures fictional). Designer/studio names and book titles in style names are **style references only** — not copies of their work, and not an endorsement by them.
- **Ported code**: `scripts/extract_grid.py`, `contact_sheet.py` and `chroma_key.py` are ported from huashu-gpt-image (MIT). The copyright and full licence text are in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), and each file keeps a header pointing to its origin.

> The upstream author's self-introduction belongs to upstream: 花生 (Huashu) is an AI-native coder, indie developer and AI writer.

**How this fork differs** (who did what, kept separate): this fork is maintained independently by this repository's maintainers. It keeps the upstream visual methodology and style library while restructuring into a **GPT-first, single standard flow for App UI**, folding product-value judgement, asset manifests with provenance, native translation and on-device acceptance into that one flow. Content marked "upstream / original author" in this README belongs to the upstream author.

---

## License

[MIT License](LICENSE). Use, modify and redistribute freely, **including commercially** — internal company use, client work, even a paid product. No prior permission, no fee. Attribution is welcome but not required.

Retained MIT code and copyright notices must not be removed or rewritten: see `LICENSE` and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Generated design assets do not automatically inherit MIT.

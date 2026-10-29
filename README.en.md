<sub>🌐 <a href="README.md">中文</a> · <b>English</b></sub>

<div align="center">

# DesignWise

### An open-source product design capability for AI agents

[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Agent](https://img.shields.io/badge/Agent-Agnostic-blueviolet)](https://skills.sh)
[![skills.sh](https://img.shields.io/badge/skills.sh-Compatible-green)](https://skills.sh)

Say one sentence to a skills-capable AI agent and get back a **design deliverable that survives product scrutiny** — a clickable App/Web prototype, an editable PPTX deck, a product launch animation, a print-grade infographic, or a professional design review.

3–30 minutes. Not "decent for AI" work: it ships a 60-style HTML-native library, a brand-asset protocol and an anti-AI-slop floor. More importantly, it adds the layer ordinary design skills skip — **judge product value first, then make the screen look good.**

```bash
npx skills add tongsailong/designwise
```

[Install](#install) · [What it does](#what-it-does) · [Demos & case studies](#demos--case-studies) · [Why it's different](#why-its-different-from-a-plain-design-skill) · [How it works](#how-it-works) · [Platforms & requirements](#platforms--requirements) · [Upstream & credits](#upstream--credits)

</div>

> **TL;DR**
> **What it is** — a **product design** skill for AI agents: it does visuals (prototypes, decks, motion, infographics) *and* product judgment (value trade-offs, UX review, spec conformance).
> **What it solves** — turns a one-sentence brief into a deliverable that can be reviewed and that doesn't drift in scope, instead of a pile of screens that merely look fine.
> **How to install** — `npx skills add tongsailong/designwise`, agent-agnostic, not tied to one tool ([Install](#install)).
> **Does it actually work** — every demo and sample below was produced by this skill.

<p align="center">
  <img src="https://github.com/alchaincyf/huashu-design/releases/download/v2.0/hero-animation-v10-en.gif" alt="Demo: a one-line terminal prompt expands into three side-by-side design directions, one is focused, and the brand visual resolves" width="100%">
</p>

<p align="center"><sub>▲ 25-second hero animation: terminal → three directions → gallery ripple → four focus passes → brand reveal<br>
This footage comes from the upstream project huashu-design (<a href="https://github.com/alchaincyf">@alchaincyf</a>); this branch preserves the capability in full. Open <a href="demos/hero-animation-v10-en.html">demos/hero-animation-v10-en.html</a> locally for the interactive version.</sub></p>

> ℹ️ **This repository is a fork of [huashu-design](https://github.com/alchaincyf/huashu-design) (by [@alchaincyf](https://github.com/alchaincyf), MIT License).** The upstream visual capabilities, 60-style HTML-native library, asset protocol and delivery pipeline are **preserved in full**; this branch layers **product value judgment, UX & usability review, spec conformance checking and cross-agent adaptation** on top. Install *this* fork with the command above, **not** the upstream one (upstream links are in [Upstream & credits](#upstream--credits)).

---

## Why it's different from a plain design skill

Most "design skills" answer one question: **how do I make this look good?** This project answers two — **is it the right thing**, and only then **does it look good**.

| | A plain design skill | This project |
|---|---|---|
| Before designing | Starts immediately, filling in "what a page usually has" | **Judges product value first**: who is using it / what they're here to do / which part of the design absorbs the complexity for them |
| Design judgment | Mostly visual (color, type, hierarchy) | Visual **plus three testable checks**: comprehension cost / operation cost / error tolerance |
| Scope control | Habitually "fills it out a bit more" | **Scope freeze**: no pages or features the user didn't ask for; "a real product would have this" is not a requirement |
| Review | Looks good or not | **Concept (highest weight) + 5-dimension critique** **plus a UX/usability layer** (product UIs) **plus spec conformance when a spec exists** **plus a pre-generation prompt-expert review**; **visual-direction and stage-gate judgment defaults to native self-check (the main model reads the real pixels); the external `scripts/zcode_vision.py --confirm-gpt-review` is used only when the user explicitly authorizes the GPT review channel; the formal `copilot` REVIEW only when the user explicitly names Copilot or explicitly requests the `copilot` Skill / formal REVIEW** (Gate 1 recommends after the real candidate images exist — you still choose the direction; Gate 2 judges the stage gate after polish) — **pixel-level tweaks are not re-submitted** |
| Platform | Bound to one AI coding tool | **Agent-agnostic**: a capability→carrier map, with automatic degradation on weak runtimes |
| Visual power | Varies | Upstream's 60-style HTML-native library, three-direction gate, brand-asset protocol and anti-slop floor (**all preserved**) |

### 1. Product value judgment (useful → understandable → comfortable → meaningful)

Product UI / interactive-prototype tasks get a lightweight layer of judgment by default. The four dimensions are **ordered — a later one cannot fix a missing earlier one**:

| Dimension | The question to ask | What goes wrong if you misjudge it |
|------|-------------|-------------|
| **Useful** | Does it solve a real user problem, or one we assumed? | Pretty but unneeded = polished slop |
| **Understandable** | How much effort does a user spend understanding it? Who carries the complexity? | The feature exists but can't be found or read = it doesn't exist |
| **Comfortable** | Pointless steps, or interactions that fight existing habits? | One extra step and one extra thought, every single time |
| **Meaningful** | Once the function works, is a little aesthetics / emotion / identity warranted? | Too early = decoration over function; never = purely instrumental |

Three **testable** checks back it up (shared by self-check and critique): **comprehension cost** (can someone say what this screen is for within seconds) / **operation cost** (how many steps, and how many of them the system should be doing) / **error tolerance** (what happens on a wrong tap — undo, explanation). Any red flag is a spot to fix.

Full method in [`references/product-value.md`](references/product-value.md) (Chinese). **Tasks that are only *viewed*** — animation, slides, infographic, cover — **do not** trigger product analysis; the original visual flow runs unchanged. Design never becomes PRD-writing.

### 2. UX & usability review

When a review is requested (or the agent self-checks), product-UI work gets **an extra layer of user-value and usability checking inside the "Functionality" dimension** of the existing critique — **concept (highest weight)** plus 5 dimensions (philosophical coherence / visual hierarchy / execution craft / functionality / innovation): is the core action served by the first screen, which of the three value checks lights up. Findings must be **concrete and actionable** — which element, changed to what — not "the interaction could be smoother."

> **On the GPT concept path there is also a pre-generation "prompt-expert review"**: the prompts exist but no image does yet, so the review decides only **what text can decide** (does it serve the need / will it yield distinguishable directions / any conflicting or ambiguous requirements / which requirements belong to production later / feasibility). It **does not decide the visual direction** and **never claims "48px legibility passed" or "opaque full-bleed confirmed" from a prompt** — those conclusions come only from the real image, and the direction comparison happens in Gate 1 on the real candidate images.

### 3. Spec conformance (Scope / Non-goals / AC)

When a design spec or explicit requirements exist, the review additionally runs a **scope conformance pass**: has Scope been exceeded, have Non-goals been breached, does every acceptance criterion have visible evidence in the design. A hit is flagged `BLOCKING_SPEC_DEVIATION`; without a spec it's N/A. It is an **additive check** — it doesn't replace the 5 dimensions and adds no approval gate. Together with **Scope freeze** during design (no unrequested pages / features / states), it keeps scope drift out of the delivery.

### 4. Cross-agent adaptation (no single-tool lock-in)

The skill is **agent-agnostic**: Claude Code, Codex, Cursor, Trae, OpenClaw, Hermes Agent, or any agent that supports markdown-based skills. The approach isn't "one doc per platform" — it decouples **capability** from **carrier**. The docs state only what capability a step needs (web search / parallel subagents / browser screenshots / local commands / file I/O); the agent maps it to whatever its environment provides. Weak runtimes (no subagents, non-Claude, small context) get a **tiered degradation mode** that sacrifices variety and process — **never the anti-slop floor or the real-asset protocol**. See [`references/runtime-adapters.md`](references/runtime-adapters.md).

### 5. The original visual capabilities, fully preserved

The four items above are an **added judgment layer**, not a replacement. Upstream's visual output pipeline is intact:

- **Direction exploration — `scripts/zcode_vision.py` compares the real candidate images, you choose the direction**: every **L2** task (new visual language or major structural change) produces **multiple real candidate directions** first (style or brand named — still no exemption); **L1 local optimization edits the existing UI directly, with no multi-direction pass**; the **prompts are reviewed first** (pre-generation, text-decidable items only, **not a direction decision**), then the approved prompts produce **several genuinely different directions, one real candidate image each**; by default **native self-check** runs **Gate 1 on those real pixels** and returns a **recommendation + rationale + risks** (external `scripts/zcode_vision.py --confirm-gpt-review` only with explicit GPT-review authorization; the formal `copilot` REVIEW only when the user explicitly names Copilot or explicitly requests the `copilot` Skill / formal REVIEW); **you look at the real candidate images and choose the direction** — the choice is yours, GPT only recommends. Only then is a converged final prompt written and the production concept image generated
- **60-style HTML-native library** (20 web + 20 deck + 20 infographic, pure CSS, no image generation)
- **Interactive prototypes** (real iPhone bezel, clickable, Playwright-verified) / **motion** (Stage + Sprite timeline, MP4/GIF export) / **editable PPTX** (real text frames) / **infographics** (print-grade, PDF/PNG/SVG)
- **Brand-asset protocol** (5 hard steps — never guess brand colors from memory) and an **anti-AI-slop floor**

---

## What it does

| Capability | Deliverable | Typical time |
|------|--------|----------|
| Interactive prototype (App / Web) | Single-file HTML · real iPhone bezel · clickable · Playwright-verified | 10–15 min |
| Slide decks | HTML deck (browser presentation) + editable PPTX (text frames preserved) | 15–25 min |
| Motion design | MP4 (25fps / 60fps interpolation) + GIF (palette-optimized) + BGM | 8–12 min |
| Design variations | 3+ side-by-side · Tweaks live params · cross-dimension exploration | 10 min |
| Infographic / data viz | Print-grade typography · exports PDF / PNG / SVG | 10 min |
| Design direction advisor | **Three logics in parallel** (second-hand roulette + award-winning references + best-designer philosophy) · 2–3 genuinely different real directions | 5 min |
| Visual concept exploration (GPT) | initial visual prompt → prompt-expert review → **one real candidate image per direction** → **Gate 1 (defaults to native self-check, which compares the real pixels and recommends; external `scripts/zcode_vision.py --confirm-gpt-review` only with explicit GPT-review authorization; the formal `copilot` REVIEW only when the user explicitly names Copilot or explicitly requests the `copilot` Skill / formal REVIEW)** → **you choose the direction** → converged final prompt → production concept image → **one** on-demand HTML prototype to validate the experience → targeted iteration (generation is a normal capability, no per-call paid approval) | 5–15 min |
| Expert critique | **Concept (highest weight) + 5 dimensions** · Keep / Fix / Quick Wins · actionable punch list · **includes a pre-generation prompt-expert review** (what text can and cannot decide; it does not decide the direction) | 3 min |

> Times are upstream's measured ranges; they vary with model capability and task complexity.

**Good fits**: hi-fi interactive prototypes and product mockups · interfaces that need to be clicked or presented · design-direction exploration · presentation decks · motion and video assets · infographics and data visualization · design review and pre-delivery QA.

**Poor fits**: production web apps · SEO sites · dynamic systems that need a backend and database. Those don't go through this skill.

---

## Install

```bash
npx skills add tongsailong/designwise
```

> ℹ️ This repository was formerly `ai-product-design-skill` and has been **renamed in place** to `designwise` (repository ID, Git history and all commits preserved; the old URL is redirected by GitHub). Install content and process are unchanged: earlier versions were verified to install completely with `npx skills` — `references/`, `assets/`, `scripts/` and `demos/` all matched the repository, no missing files. If your install comes out incomplete, see the troubleshooting below.

**Verify after install**: this skill is more than a single `SKILL.md` — `references/`, `assets/`, `scripts/` and `demos/` hold 65 referenced recipes, scripts and assets, and a missing one breaks a path. The repo ships a self-check that turns "is it complete?" into one command:

```bash
python3 scripts/check-skill.py            # structure + reference integrity
python3 scripts/check-skill.py --strict   # also flag files nothing references
```

Check the install directory (e.g. `~/.claude/skills/designwise/`). **If you only see SKILL.md and none of those subdirectories**, your `skills` CLI is too old (≤1.5.15 had a bug that synced only the single file, fixed in 1.5.19). Upgrade and reinstall:

```bash
npm i -g skills@latest        # or npx skills@latest add tongsailong/designwise
```

If it's still wrong, fall back to a `git clone` install — clone the repo into any skills directory:

```bash
git clone https://github.com/tongsailong/designwise.git ~/.claude/skills/designwise
```

Then just talk to Claude Code / Codex / Cursor or any skills-capable agent (see below).

---

## Usage examples

No buttons, no panels, no Figma plugin — one sentence is enough:

```
"Build an iOS prototype for a Pomodoro app — 4 screens, actually clickable."
"Make a keynote on AI psychology. Give me 3 style directions to pick from."
"Turn this logic into a 60-second animation. Export MP4 and GIF."
"Review this design, and focus on usability."
"Here's our app spec — check the build for scope creep and missed acceptance criteria."
"The interface feels messy — show me where comprehension and operation costs are too high."
"Design a brand landing page from our logo + palette + UI screenshots, three directions."
"Turn this quarter's data into a print-grade infographic I can export as PDF."
```

---

## Demos & case studies

### Open locally

- **24 prebuilt samples**: 8 scenes × 3 styles (Pentagram / Build / Takram) — PNG thumbnails plus renderable HTML; index at [`assets/showcases/INDEX.md`](assets/showcases/INDEX.md)
- **18 capability demo HTML files** (Chinese and English, `-en` for English): `demos/c1-ios-prototype.html`, `c2-slides-pptx`, `c3-motion-design`, `c4-tweaks`, `c5-infographic`, `c6-expert-review`, `w1-brand-protocol`, `w2-junior-designer`, `w3-fallback-advisor`, plus `demos/hero-animation-v10-en.html`
- **Long-form / narrated demos**: `demos/md-html-narration/`, `demos/voiceover-demo/`

### Animated demos (GIFs served from the upstream Releases)

> The GIFs below were produced and published by the upstream project huashu-design ([@alchaincyf](https://github.com/alchaincyf)); this skill preserves the corresponding capability, and the captions reference its public description.

**Design direction advisor** — for vague briefs, three complementary logics run in parallel (roulette + award-winning references + best-designer philosophy) and produce three real visuals to choose from.

<p align="center"><img src="https://github.com/alchaincyf/huashu-design/releases/download/v2.0/w3-fallback-advisor-en.gif" alt="Design direction advisor demo: three differentiated directions generated in parallel and shown side by side" width="100%"></p>

**iOS app prototype** — pixel-accurate iPhone 15 Pro body (Dynamic Island / status bar / home indicator) · state-driven multi-screen navigation · Playwright click tests.

<p align="center"><img src="https://github.com/alchaincyf/huashu-design/releases/download/v2.0/c1-ios-prototype-en.gif" alt="iOS prototype demo: screen states switching inside a real device bezel with click interaction" width="100%"></p>

**Motion design engine** — Stage + Sprite time-slice model · four APIs (`useTime` / `useSprite` / `interpolate` / `Easing`) · one command exports MP4 / GIF / 60fps-interpolated / BGM-scored finals.

<p align="center"><img src="https://github.com/alchaincyf/huashu-design/releases/download/v2.0/c3-motion-design-en.gif" alt="Motion engine demo: timeline-driven animated graphics and transitions" width="100%"></p>

**HTML slides → editable PPTX** — `html2pptx.js` reads DOM computed styles and translates each element into real PowerPoint objects; exports are **actual text frames** you can double-click and edit.

<p align="center"><img src="https://github.com/alchaincyf/huashu-design/releases/download/v2.0/c2-slides-pptx-en.gif" alt="Slides demo: HTML deck navigation and the exported editable PPTX text frames" width="100%"></p>

**Tweaks · live variation switching** — colors / typography / density parameterized · side-panel toggle · pure frontend + `localStorage` persistence.

<p align="center"><img src="https://github.com/alchaincyf/huashu-design/releases/download/v2.0/c4-tweaks-en.gif" alt="Tweaks demo: side panel switching palette and typography with the page updating live" width="100%"></p>

**Infographic / data viz** — magazine-grade typography · precise CSS Grid columns · driven by real data · exports to vector PDF / 300dpi PNG / SVG.

<p align="center"><img src="https://github.com/alchaincyf/huashu-design/releases/download/v2.0/c5-infographic-en.gif" alt="Infographic demo: a long, data-driven magazine-grade layout" width="100%"></p>

**Expert critique** — concept (highest weight) + five dimensions scored 0–10 · radar visualization · Keep / Fix / Quick Wins punch list.

<p align="center"><img src="https://github.com/alchaincyf/huashu-design/releases/download/v2.0/c6-expert-review-en.gif" alt="Design critique demo: five-dimension radar chart with a Keep/Fix/Quick Wins list" width="100%"></p>

**Junior designer workflow** — no heroic one-shot attempts: assumptions + placeholders + reasoning first, shown to you early, then iterated.

<p align="center"><img src="https://github.com/alchaincyf/huashu-design/releases/download/v2.0/w2-junior-designer-en.gif" alt="Junior designer workflow demo: placeholders and assumptions shown first, then filled in iteratively" width="100%"></p>

**Brand asset protocol · 5-step hard process** — ask → search → download (three fallbacks) → grep colors → write `brand-spec.md`.

<p align="center"><img src="https://github.com/alchaincyf/huashu-design/releases/download/v2.0/w1-brand-protocol-en.gif" alt="Brand asset protocol demo: pulling logo and color values from official sources into a spec" width="100%"></p>

### Real case studies by the upstream author (quoted, not this fork's output)

- **Parrot evolution site** — from the single prompt "make a site about parrot evolution": judged images to be content-critical, fetched public-domain natural-history illustrations, ran three logics in parallel. Live: <https://www.huasheng.ai/parrots/>
- **"Talking about skills" PM after-party deck** — 13 HTML slides, all made with the skill, including two 22-second cinematic demos with BGM + SFX. Live: <https://skill-huasheng.vercel.app>

---

## How it works

### Direction exploration: native self-check compares the real candidate images (external GPT only when authorized), you choose the direction (multi-direction gate)

Any **L2** task (new visual language or major structural change) starts by producing **multiple real candidate directions** — a named style or brand narrows the interpretation but doesn't waive the choice. **L1 local optimization edits the existing UI directly; it does not run the multi-direction gate.** The **prompts are reviewed first** (pre-generation, text-decidable items only, **not a direction decision**), then the approved prompts produce **several genuinely different directions, one real candidate image each**. By default **native self-check** then runs **Gate 1 on those real pixels** and returns a **recommendation + rationale + risks** (external `scripts/zcode_vision.py --confirm-gpt-review` only with explicit GPT-review authorization; the formal `copilot` REVIEW runs only when the user explicitly names Copilot or explicitly requests the `copilot` Skill / formal REVIEW); **you look at the real candidate images and choose the direction** — the choice is yours, GPT only recommends. A converged final prompt and the production concept image come after that.

**Tasks that explore a new visual direction** (app icon · splash redesign · app home or key-page redesign · multi-page visual system · brand exploration · illustration/key visual · interactive prototype) go down this full chain:

```
initial visual prompt → prompt-expert review (pre-generation, does not decide the direction)
  → generate several genuinely different directions (ONE real candidate image per direction) → per-image quality self-check
  → **Gate 1** (defaults to native self-check comparing the real pixels → recommendation + rationale + risks; external `zcode_vision --confirm-gpt-review` only with authorization; the formal `copilot` REVIEW only when the user explicitly names Copilot or explicitly requests the `copilot` Skill / formal REVIEW)
  → show the candidate images + recommendation → **you choose the direction** → converged final prompt → production concept image (self-check)
  → translate the concept into a visual spec → build ONE on-demand HTML prototype
  → objective size / geometry / mask verification + second review and targeted iteration → **Gate 2** (defaults to native self-check judging the stage gate against the confirmed concept image; external `zcode_vision --confirm-gpt-review` only with authorization; the formal `copilot` REVIEW only when the user explicitly names Copilot or explicitly requests the `copilot` Skill / formal REVIEW)
  → pass → move on / wrap up; fail → fix only what affects the core goal
  → production implementation (GPT production assets on demand) → real-run acceptance
```

- **GPT owns creative exploration**: several genuinely different **candidate directions** (each with a complete generation prompt and **ONE real candidate image**); image generation is a **normal model capability** — generated within the agreed task, with **no per-call paid approval**. 🔴 **The candidate images are a necessary investment** — picking the wrong direction costs far more than a few candidate images; equally, **don't pad the count** (a single-direction task gets a single-direction review)
- 🔴 **Prompts are reviewed first, but the review does not decide the direction**: the initial visual prompt goes through the **existing Huashu expert critique** (Keep / Fix / Quick Wins), deciding only **what text can decide** — does it serve the need / will it yield distinguishable directions / any conflicting or ambiguous requirements / which requirements belong to production later / feasibility. **Fix the prompt first, then generate**; 🔴 **never skip the review and mass-generate**; 🔴 **this step yields no direction decision**
- 🔴 **Gate 1 happens after the real candidate images exist**: **native self-check reviews all candidates in one go** by default (labelled by version/role, compared on real pixels); hand them to `scripts/zcode_vision.py --confirm-gpt-review` only with explicit GPT-review authorization (the formal `copilot` REVIEW only when the user explicitly names Copilot or explicitly requests the `copilot` Skill / formal REVIEW) and it returns a **recommended direction + reasons + risks + viable directions**. **No Gate 1 before the real images exist** — without pixels, any direction conclusion would just be text conjecture
- **Review knows its limits**: the pre-generation review only decides what text can decide — it **never claims "48px legibility passed" or "opaque full-bleed confirmed" from a prompt**; those conclusions come only from the real image
- 🔴 **You own the final direction choice**: GPT only recommends — **you choose the direction on the real candidate images**; nothing proceeds until you do; 🔴 **afterwards only that direction** gets HTML or engineering assets (the **default flow never picks the direction for you**)
- 🔴 **A converged final prompt is written after you choose**: it **only converges on the chosen direction** to raise the stability, clarity and producibility of the production concept image; **it introduces no new direction and never re-runs the direction choice**; 🔴 **the exploration prompt ≠ the final concept-image prompt** (never reuse it verbatim)
- **HTML validates the experience on demand**: build it only when interaction and multi-state behaviour need checking, and **only one prototype for the chosen direction**; app icons, simple static splash screens and single brand images skip it
- **HTML must reproduce the visuals, not just the structure**: when a page's visual value depends on imagery (illustration / people / key visual / complex background / decorative art / product shots), generate **validation assets** with GPT to reproduce the concept — **no placeholder images, random stock or code stand-ins**, which would corrupt the visual review. Pure layout / lists / forms / geometry / existing real assets need no generation
- **Constraint layering + quality self-check**: before generating, split requirements into **hard constraints** (purpose recognition / brand colours / size & safe area / small-size legibility) and **explorable constraints** (composition / elements / metaphor — left to GPT); after generating, composite onto the target background to verify hard constraints and judge first by "can the user recognise it at a glance", **not by pixel-ratio, connected-component or similar mechanical metrics alone**
- **Stage gate = Gate 2**: after polish / production work, **native self-check** reviews the real render (or production artefact) plus the **confirmed concept image** and objective measurements by default for **Gate 2**; hand them to `scripts/zcode_vision.py --confirm-gpt-review` only with explicit GPT-review authorization (the formal `copilot` REVIEW only when the user explicitly names Copilot or explicitly requests the `copilot` Skill / formal REVIEW) — is the direction still valid / has it drifted from the chosen direction / is it ready for the next stage or wrap-up. **Pass → wrap up; fail → fix only what affects the core goal**
- **The second review iterates in a targeted way**: first ask "does the HTML truly reproduce the concept's visuals, not just its structure?"; visual dissatisfaction → regenerate that direction or its validation assets; interaction problems → edit the existing HTML first; both → do both — **never re-run the whole flow**
- 🔴 **Pixel-level tweaks do not trigger GPT by default**: 1–2% geometry adjustments, spacing / radius / single-node moves, problems already settled by objective measurement are **not re-submitted**. Only a **substantive visual change, a new visual problem, a new stage gate, a genuine disagreement, something objective measurement can't settle, or a need to re-choose the direction** triggers another call — **the "tweak → GPT → tweak → GPT" loop is forbidden**
- **Validation assets aren't wasted**: at production time they can be reused as-is / regenerated to engineering spec / replaced by vector or code — whichever is more reliable
- **Cost stays sane**: image count decided by actual need, limited retries on failure, reuse of existing assets, no "just to probe" generation; a genuinely larger scope is a normal task-scope change
- **When generation is unavailable**: **state it and pause the generation step** (you can hand over the finished prompts to run in ChatGPT and bring the images back) — **never silently fall back to HTML/SVG code drawing passed off as concept art**, and never pass off placeholders as a faithful reproduction

**Local edits, bug fixes, feature work, adaptation and simple copy/layout fixes skip this chain** and go straight to implementation and verification. Full rules: [`references/gpt-visual-workflow.md`](references/gpt-visual-workflow.md).

### Product value judgment & scope freeze

Product-UI tasks write three lines before starting (who's using it / what they're here to do / which part absorbs their complexity) and share one requirement line across all directions (3 by default, 2 when justified). During design, **no pages, features or states the user didn't ask for** — if you believe the requirements should expand, hand it back to the user instead of turning "don't do X" into "did X."

### Brand-asset protocol (5 steps, never guess)

| Step | Action | Purpose |
|---|---|---|
| 1 · Ask | Do they have brand guidelines / logo / product shots / UI screenshots? | Respect existing resources |
| 2 · Search official pages | `<brand>.com/brand` · `brand.<brand>.com` · `<brand>.com/press` | Authoritative sources |
| 3 · Download | SVG files → full site HTML → color picked from product shots | Three fallbacks, next one immediately on failure |
| 4 · Extract colors | grep every `#xxxxxx`, rank by frequency, drop blacks/whites/greys | **Never guess brand colors from memory** |
| 5 · Freeze to spec | `brand-spec.md` + CSS variables; all HTML uses `var(--brand-*)` | Un-frozen knowledge evaporates |

### Junior designer workflow

The default mode, scoped by task tier: send the full question set in one batch and wait; write assumptions + placeholders + reasoning into the HTML first; show it to the user early (even gray blocks); **for L2 or an explicit comparison request**, show again at content → variations → Tweaks (**L1 edits the existing UI directly, without a multi-version pass**); eyeball the browser with Playwright before delivery.

### Fact verification first (core principle #0)

When a task mentions a specific product, technology or event, the first action must be a lookup (existence, version, specs) rather than an assertion from training memory. A search costs ~10 seconds; a wrong assumption can cost 1–2 hours of rework.

### Anti-AI-slop floor

Avoid the visual common denominator of AI output (purple gradients / emoji icons / rounded-corner + left-border accent / SVG humans / Inter as display). Use `text-wrap: pretty` + CSS Grid + carefully chosen serif display faces and oklch colors.

---

## Platforms & requirements

**Agents**: Claude Code · Codex · Cursor · Trae · OpenClaw · Hermes Agent, or any agent supporting markdown-based skills. Weak runtimes (no subagents / non-Claude / limited context) enter a degradation mode: **L2** still produces multiple directions (3 by default, 2 when justified; serial and physically isolated); **L1 edits the existing UI directly**.

**Local toolchain** (only needed when you use the matching export/verify capability):

| Requirement | Used for |
|---|---|
| Node.js | `scripts/render-video.js` (HTML→MP4), `html2pptx.js`, `export_deck_*.mjs`, `gen_deck_thumbs.mjs`; `package.json` deps: `playwright` / `pptxgenjs` / `pdf-lib` / `sharp` |
| ffmpeg | MP4 → 60fps / GIF, adding BGM, mixing narration (`convert-formats.sh`, `add-music.sh`, `mix-voiceover.sh`) |
| Python 3 | `scripts/verify.py` (Playwright verification), `fetch_images.py`, `check-skill.py` (structure), `check-contrast.py` (contrast), `check-assets.py` (asset manifest) |
| Playwright | Pre-delivery click tests and screenshot verification |

**Cloud features (fully optional)**: Doubao TTS narration and AI video review live in `scripts/cloud/`, need your own API key, and require an explicit `--yes` on first call. Off by default. The core pipeline (design → render → MP4 / PDF / PPTX export) runs **100% locally, zero network calls, zero keys**, with no telemetry. Every outbound host, credential touchpoint and deletion boundary is declared in [SECURITY.md](SECURITY.md).

---

## Limitations

- **No layer-editable PPTX-to-Figma round trip.** The output is HTML — screenshottable, recordable, image-exportable, but not draggable into Keynote for text-position tweaks.
- **Framer-Motion-tier complex animation is out of scope.** 3D, physics simulation, particle systems exceed the skill's boundaries.
- **Brand-from-zero design drops to 60–65 points.** Drawing hi-fi from nothing was always a last resort.
- The skill targets "visual output built with HTML" — **it does not build production web apps, SEO sites, or backend-driven dynamic systems**.

This is an 80-point skill, not a 100-point product. For people unwilling to open a graphical UI, an 80-point skill beats a 100-point product.

---

## Repository structure

```
ai-product-design-skill/          # repo renamed to designwise (this is the historical name)
├── SKILL.md                 # Main doc (read by the agent; Chinese)
├── README.md                # Chinese README (default)
├── README.en.md             # English README (this file)
├── SECURITY.md              # Security & data-flow statement
├── LICENSE                  # MIT
├── assets/                  # Starter components + prebuilt samples
│   ├── animations.jsx       # Stage + Sprite + Easing + interpolate
│   ├── ios_frame.jsx        # iPhone 15 Pro bezel
│   ├── android_frame.jsx · macos_window.jsx · browser_window.jsx
│   ├── deck_stage.js        # HTML deck engine
│   ├── deck_index.html      # Multi-file deck assembler
│   ├── design_canvas.jsx    # Side-by-side variation display
│   ├── cursor.jsx           # Cursor narrative for product-UI demos
│   ├── showcases/           # 24 prebuilt samples (8 scenes × 3 styles)
│   └── bgm-*.mp3 · sfx/     # Scene-specific tracks and SFX library
├── references/              # Drill-down docs by task (Chinese)
│   ├── product-value.md     # Product value judgment (useful→understandable→comfortable→meaningful)
│   ├── critique-guide.md    # concept + 5-dimension critique + usability + spec conformance + pre-generation prompt review
│   ├── runtime-adapters.md  # Capability → carrier map (cross-agent)
│   ├── design-styles.md     # 60-style HTML-native library
│   ├── app-prototype.md · slide-decks.md · editable-pptx.md
│   ├── animation-*.md · camera-language.md · storyboard-basics.md
│   └── ...
├── scripts/                 # Export & verification toolchain
│   ├── render-video.js      # HTML → MP4
│   ├── convert-formats.sh   # MP4 → 60fps + GIF
│   ├── add-music.sh         # MP4 + BGM
│   ├── export_deck_pdf.mjs · export_deck_pptx.mjs · html2pptx.js
│   ├── verify.py · check-contrast.py · check-assets.py · check-skill.py
│   └── cloud/               # Optional cloud features (own key + --yes)
└── demos/                   # Capability demos (Chinese + English HTML) + hero animation
```

Structure self-check:

```bash
python3 scripts/check-skill.py
```

---

## Upstream & credits

The visual capabilities, methodology lineage and the following materials come from upstream:

**[Huashu Design · huashu-design](https://github.com/alchaincyf/huashu-design)** — by [@alchaincyf](https://github.com/alchaincyf), MIT License.

- Upstream repo and install command (**use this fork's command to install this fork**): `npx skills add alchaincyf/huashu-design`
- Upstream author's beginner tutorial: <https://www.youtube.com/watch?v=m-_BlUdcIvw>
- Upstream star history: <https://star-history.com/#alchaincyf/huashu-design&Date>
- Upstream author's case studies: parrot-evolution site · the "talking about skills" deck · [FanBox · a cockpit for coding agents](https://github.com/alchaincyf/fanbox)
- The origin story as told by the upstream author: after Anthropic shipped Claude Design, the author had an agent deconstruct its publicly circulating system prompts, brand-asset protocol and component mechanics into a structured spec, then wrote it as a skill.

<table>
<tr><td>

**<b>The upstream author's bio (the original author's own, not a contribution of this fork)</b>**: Huasheng is an AI-native coder, independent developer and AI media creator. Notable work: Cat Fill Light (App Store top paid), *A Book on DeepSeek*, Nüwa.skill. Find him on X, WeChat, Bilibili, YouTube, Xiaohongshu, [huasheng.ai](https://www.huasheng.ai/) or [bookai.top](https://bookai.top).

</td></tr>
</table>

> Upstream also maintains community translations (English / Korean / Vietnamese); their translation quality and license terms are each maintainer's responsibility — see the upstream repo.

**What this fork changes** (no conflation of authorship): this branch is maintained by this repository's maintainer and, while preserving the full upstream visual capability, adds and iterates on **product value judgment, UX & usability review, spec conformance checking and cross-agent capability mapping**. Demos, tutorials, case studies and bios labelled "upstream" / "original author" in this README belong to the upstream author.

On upstream's own IP handling: upstream built on the ideas in Anthropic's publicly circulated Claude Design prompts and community material; this fork further clean-room rewrote the parts that depended on proprietary code (e.g. HTML-slides-to-PPTX) as its own implementation. See the commit history and [LICENSE](LICENSE).

### Contributing here

Found an install problem, a broken reference, or want to add a language? Open an issue. For translations, please include matching changes to both `SKILL.md` and `README.md`.

---

## License

[MIT License](LICENSE). You are free to **use, modify and distribute** this skill for any purpose, **including commercial use** — inside companies, in client deliverables, as part of a paid product. No prior authorization, no fee. Attribution is appreciated but not required.

Upstream huashu-design has also been MIT-licensed since 2026-05-14 (previously a commercial-restricting Personal Use License, now removed). This fork inherits that license and preserves the original author's attribution.

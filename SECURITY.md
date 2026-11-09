# Security & Data-Flow Statement

This document declares every network destination, credential touchpoint, subprocess and deletion this skill can perform, so that users and automated reviewers can verify the claims against the code.

**TL;DR — the design pipeline is local-first.** Product understanding, information architecture, HTML prototyping, screenshot verification, asset processing and the manifest live entirely on your machine. Network access exists only in explicit, user-initiated paths:

| Path | Leaves your machine when |
|---|---|
| `scripts/zcode_image.py` — real image generation | you (or the agent, inside an agreed task) generate concept/direction/asset images |
| `scripts/zcode_vision.py` — external GPT visual review | you explicitly authorise that channel **and** the call passes `--confirm-gpt-review` |
| `~/.zcode/skills/copilot/scripts/bridge_evidence.py` + `call_gpt.py` — Copilot direction selection | stage 3 of the standard flow runs: brief text + the three concept images go to the configured model endpoint |
| `scripts/fetch_images.py` — Wikimedia Commons | the agent fetches CC/public-domain imagery for a design |
| `scripts/ref_board.py` / `scripts/check-ui.mjs` — headless Chrome | you pass reference URLs or a page that itself loads remote assets |
| Brand asset protocol — brand official sites | the design is brand-specific and no local brand asset exists |

There is **no telemetry**, no analytics, no author-controlled server, and no background call of any kind. Nothing in this repo sends data anywhere on its own.

---

## 1. Network destinations

| Host | Where | What is sent | When |
|---|---|---|---|
| **Image endpoint** — configured `baseUrl` (default the local CPA proxy `http://127.0.0.1:8317`, OpenAI-compatible `/v1/images/generations` and `/v1/images/edits`) | `scripts/zcode_image.py` | Your prompt, size/quality/count parameters, and any `--ref` reference images (base64) | Only when the script is invoked; `--health` performs a zero-cost reachability check |
| **Vision endpoint** — same `baseUrl`, `/v1/responses` | `scripts/zcode_vision.py` | The image under review plus the review prompt | Only with `--confirm-gpt-review`; every non-health call without it is refused **before** any request is made |
| **Model endpoint** — Copilot's configured endpoint (CPA), via `call_gpt.py --mode CONSULT` | Copilot direction selection (stage 3) | The design brief, the three concept images and the selection request | Only when stage 3 runs; every call is written to the audit log (see §4) |
| `commons.wikimedia.org` (official Wikimedia API) | `scripts/fetch_images.py` | Search keywords; downloads CC/public-domain images with licence info printed for review | Only when the agent fetches stock imagery |
| Brand official sites, `simpleicons.org`, Google favicon service | `references/brand-asset-protocol.md` (instructions, no script) | Plain GET requests for publicly served logos/brand assets | Only for a brand-specific design |
| Reference URLs you supply | `scripts/ref_board.py` → `scripts/check-ui.mjs` (headless Chrome) | A normal page load of the URL you passed | Only when you ask for a reference board |
| `fonts.googleapis.com`, `unpkg.com` and similar CDNs | Static `<link>` / `<script>` tags inside generated prototype HTML | Standard browser font/library fetches when **you** open the file | Browser-side only; offline rendering degrades gracefully |

That is the entire list. Verify with:

```bash
grep -rn "urlopen\|requests\.\|fetch(" --include="*.py" --include="*.mjs" --include="*.js" scripts/
```

Every hit must map to a row above.

---

## 2. API keys and credentials

- **No key is hardcoded.** The repo ships only `.env.example` placeholders; `.env` is gitignored and excluded from runtime sync.
- `scripts/zcode_image.py` and `scripts/zcode_vision.py` read the endpoint and key at call time from `ZCODE_CPA_BASE_URL` / `ZCODE_CPA_API_KEY`, or from ZCode's provider config (`~/.zcode/v2/provider_config.json`, overridable with `ZCODE_PROVIDER_CONFIG`). They never print, copy or persist the key.
- Design outputs never embed credentials: keys are not written into HTML, images, manifests or reports. `asset-manifest.json` records model name and prompt reference, never auth material.
- Copilot's own credentials and audit configuration belong to the **`copilot` skill**, not to this repo. DesignWise only calls its documented CLI surface and never reads its config.
- Adding a provider, purchasing credit, or changing billing is **outside** this skill's authority; it is a user/account decision.

---

## 3. Image generation boundaries

`scripts/zcode_image.py` is the only generation path. Three rules apply:

- **Scope and cost.** Generation is a normal model capability inside an agreed design task — concept directions at stage 2, prototype support at stage 4, assets at stage 5. It is not per-image approval-gated, but it is also not unbounded: one image per direction, no "just to probe" batches, no unconditional retries, reference-image editing (`--ref`) for tweaks, and reuse before regeneration. A genuinely larger scope is handled as a normal task-scope change with the user.
- **Honesty.** If generation is unavailable, report the limit and pause that step; you may hand over complete prompts so the user can generate externally and return real files. Never substitute HTML/SVG drawings or placeholders and present them as generated concept images.
- **Not relaxed.** Using generation does not permit changing credentials, model routing or account configuration, opening new paid services, widening file/system/network permissions, or bypassing any other authorisation rule (commit, push, release and production changes keep their own gates).

---

## 4. Copilot direction selection (stage 3)

Stage 3 is the one place where the design itself is sent to an external model, and it is deliberate — the point is a real-pixel decision by a party other than the executor.

- `bridge_evidence.py` packs the goal/brief and the three concept images into a local evidence bundle (`.designwise/evidence-direction.md` + `.json`). Nothing leaves the machine at this step.
- `call_gpt.py --mode CONSULT` sends that bundle to the configured model endpoint and writes the reply locally. It also appends one audit line to `~/.zcode/skills/copilot/.audit/copilot.jsonl` (subject, timestamps, model identity, evidence digest, reply digest) — **not** the images themselves.
- Fail-closed conditions (missing/undecodable/duplicate image, image not actually in the request, model identity check failure, a reply admitting it cannot see the images, or a verdict with no clear recommendation) mean **no verdict**, and are recorded as such. They are not retried into a fabricated answer.
- The resulting `direction-approved.md` is design evidence, **not** a formal REVIEW, and it does not constitute authorisation for commit, push, release or deployment.

---

## 5. Subprocesses

All subprocess calls invoke local tools only: Playwright/Chromium (via `scripts/verify.py`, `scripts/check-ui.mjs`, `scripts/ref_board.py`), `node`, `git` (used read-only by `check-skill.py` and the version self-check), `python3`, and — for native verification — the host-authorised Android installer described below. No curl-pipe-sh patterns, no shell-to-network combinations.

`scripts/check-ui.mjs` launches local Chrome/Chromium in headless mode against the URL you pass (normally `file://` or loopback) and talks to it over a loopback CDP port. The script itself makes no outbound requests; the browser loads the page as it normally would. It writes only to a temporary profile directory it creates and removes.

---

## 6. On-device installation

Native verification installs a build onto a **real device**. This repo ships no installer and does not call `adb install` directly. Installation goes **only** through the host-authorised entry point:

```
~/.zcode/skills/app-testing/runtime/mi6-verify/adb-auto-install.sh
```

- The script aborts when more than one device is connected, and the workflow records device model, system/API level, density and build hash alongside the evidence.
- Evidence capture (`adb shell`, `uiautomator dump`, `screencap`, `logcat`) stays on the local USB connection. Raw `adb install` is prohibited by project rule.
- If the device is offline or the toolchain is missing, the result is `PARTIAL` / `BLOCKED` — never "passed".

---

## 7. File deletion

Recursive deletion is limited to scratch directories the scripts create themselves with unique timestamp/PID names, plus Python `tempfile` directories. No script deletes user data or anything outside its own scratch space.

The single exception is the explicit maintenance flag `python3 scripts/sync_runtime.py --apply --prune`: it removes files in the **target runtime copy** that do not exist in the source. It is never on by default, excludes `.env` / `.env.*`, `assets/personal-asset-index.json` and other generated files, refuses when source and target are the same or ancestor/descendant, and never deletes anything in the source repository.

---

## 8. Dependencies

Mainstream registry packages only — `playwright` and `sharp` via npm, `Pillow` via pip/uv. No binary downloads from arbitrary URLs and no post-install scripts that fetch code at runtime. `node_modules/` is gitignored and excluded from runtime sync.

---

## 9. Hooks

This skill installs **no** hooks and writes nothing to any host configuration. The old render-time gate hook was retired with the video/PPT export chain; the direction gate now lives in the flow as stage 3 evidence (`direction-approved.md` + Copilot audit record), enforced by instruction and by `asset_manifest.py` / `check-skill.py` checks rather than by a process hook.

Whatever hooks exist in your host configuration are yours and are outside this skill's scope.

---

## 10. Reporting

Found something that contradicts this document? Please open an issue — a mismatch between this file and the code is treated as a bug.

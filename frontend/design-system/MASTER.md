# NeuLitTrace - Design System (Master)

Status: **v2 direction, adopted 2026-07-23**, supersedes the v1 PET-thermal direction
in this file's git history. Source: `NeuLitTrace UIUX Design.zip` (Claude design
canvas export, `NeuLitTrace.dc.html`), extracted and reconciled against the working
frontend (`frontend/src`) and `plan/plan.md`.

Reconciliation note: the design canvas's mockup markup is a static illustration of
intent (React-like `{{ binding }}` syntax, not real code). Section structure, copy,
layout patterns, colors, and typography from it are adopted directly. Its "Brain
Atlas" mount (`brainMount`) shown in the mockup is a decorative Three.js icosahedron
with hardcoded region positions - this is **not** adopted as-is: the real
`BrainViewer` component (`frontend/src/components/brain-viewer.tsx`) already renders
the actual Nilearn/Harvard-Oxford atlas via a backend-served iframe, driven by the
real `/conditions` API. That integration is a correctness requirement per the root
`CLAUDE.md` (atlas lookup against real literature-stated regions, not custom
coordinate math) and stays as-is - only its container chrome (panel background,
border, blur, legend chip styling) gets restyled to this palette. The backend
(`backend/api/routes/atlas.py`) renders it with `view_img_on_surf` on an
`fsaverage6` surface mesh, recolored to this palette (`#16131C` background,
`#8D8894` non-highlighted regions, `#FF5FA3` highlighted region, matching
`--void`/`--mist-dim`/`--rare`), modebar hidden, cached in memory per condition.
The old procedural `BrainCanvas` component (`frontend/src/components/brain-canvas.tsx`)
isn't removed - `BrainViewer` shows it only as a brief loading visual while the atlas
iframe first loads, cross-fading out once the iframe fires `onLoad`; later condition
switches just swap the iframe's `src` and don't bring `BrainCanvas` back. The mockup's
Three.js neuron-branch canvas is reused only for the **hero's decorative background
animation**, which has no data-accuracy requirement.

## Voice

Instrument-console register carries over from v1: precise, clinical-adjacent, terse.
Copy in the mockup uses small tracked-uppercase section eyebrows ("INTERACTIVE
ATLAS", "SOURCED SUMMARY") - v1 named this an AI-slop tell and banned it; v2
explicitly reintroduces it as a deliberate motif consistent across every section, not
a one-off reflex choice. Every brain-highlight interaction still must carry the
disclaimer "Location reference from literature, not a diagnostic read" - non-
negotiable, unchanged from v1.

Copy rules (unchanged from v1):
- No AI-pitch filler ("seamless", "unlock", "empower", "cutting-edge", "leverage",
  "revolutionize", "dive into"). Say the specific thing.
- The top banner reads "Literature verification - not a diagnostic tool" - keep this
  exact framing anywhere the product is summarized in one line.

## Color

Dark purple/pink glow on near-black, in `oklch()`. This is a deliberate reversal of
v1's "reject blue/purple glow" rule - the v2 direction treats the glow as a bioluminescent/neural motif (paired with the neuron-branch hero animation) rather than a generic "AI tool" default, and pairs it with warm pink accents to avoid reading as flat blue-on-black.

| Token | Value | Role |
|---|---|---|
| `--void` | `oklch(0.14 0.025 296)` | Base background |
| `--void-2` | `oklch(0.19 0.035 300)` | Lifted surface (panel base before blur) |
| `--ink` | `oklch(0.97 0.01 296)` | Primary text |
| `--paper` | `oklch(0.85 0.02 296)` | Secondary reading text |
| `--mist` | `oklch(0.72 0.03 296)` | Muted labels, secondary UI text |
| `--mist-dim` | `oklch(0.58 0.03 296)` | Tertiary/disabled-weight text |
| `--line` | `oklch(1 0 0 / 0.08)` | Default dividers/borders |
| `--line-bright` | `oklch(1 0 0 / 0.14)` | Emphasized dividers/borders |
| `--accent-purple` | `oklch(0.64 0.19 296)` | Gradient stop, primary CTA start |
| `--accent-pink` | `oklch(0.66 0.19 340)` | Gradient stop, primary CTA end, section eyebrow color |
| `--rare` | `oklch(0.72 0.19 350)` | Rare-condition marker, citation superscript, highlight accents |
| `--common` | `oklch(0.7 0.11 240)` | Common-baseline marker (comparison contrast to `--rare`) |

Primary CTAs and active-tab pills use a 135deg gradient from `--accent-purple` to
`--accent-pink`. Glass panels: background `oklch(0.24 0.05 300 / 0.14)`, border
`oklch(1 0 0 / 0.1)`, `backdrop-filter: blur(20px)`, soft shadow
`0 20px 60px oklch(0 0 0 / 0.4)`.

## Typography

Loaded via `next/font/google` in `layout.tsx` (build-time self-hosting, same
mechanism already in place - no `fonts.googleapis.com` runtime request).

| Role | Face | Notes |
|---|---|---|
| Display / h1, h2 | **Newsreader** (400-500, italic available) | Serif, used only for section headlines, not body copy |
| Body / UI / labels / eyebrows | **Space Grotesk** (400-600) | Everything else: paragraphs, buttons, nav, tracked-uppercase eyebrows |
| Data / large stat numbers | **Sora** (600-700) | Citation count, confidence label, rarity-ring percentage - anywhere a number needs to read as a measurement |
| Mono / PMIDs / condition chips | **Martian Mono** (400-700) | Retained from v1 for citation metadata and condition-chip labels; the mockup didn't specify a role here so this fills the gap without introducing a fourth "unsafe" font |

Update `frontend/src/app/layout.tsx`'s three `next/font/google` imports from
`Plus_Jakarta_Sans` / `Source_Serif_4` / `Martian_Mono` to `Space_Grotesk` /
`Newsreader` / `Martian_Mono`, and add `Sora` as a fourth variable
(`--font-data`). Keep the existing `--font-mono` variable name for Martian Mono.

Type scale: fluid `clamp()` for h1/h2 only (see mockup's `clamp(44px,7vw,88px)` hero
size, `clamp(30px,4vw,44px)` section h2 size). Body/label/data sizes are fixed px,
not fluid.

## Sections (build order, matches `plan/plan.md`)

1. **Hero** - full-viewport, animated 2D canvas background (drifting radial glow
   blobs + procedurally drawn branching neuron structure, see "Hero canvas" below),
   subtle grain overlay, bottom fade to `--void`. Nav: wordmark left, pill badge
   right ("Literature verification - not a diagnostic tool"). Headline: small pink
   tracked-uppercase eyebrow, then serif `h1`, then a body paragraph capped at
   `max-width:560px`. "Scroll to explore" affordance at the bottom with a bouncing
   chevron line.
2. **Query** - centered glass panel (`max-width:760px`), a plain `textarea`
   (no visible border, transparent background) plus a pill gradient "Search" button
   right-aligned. Scroll-reveal on enter (translateY 28px → 0, opacity 0 → 1,
   `cubic-bezier(.16,1,.3,1)`, 0.9s).
3. **Brain Atlas** (`data-reveal-id="brain"`) - centered heading block, then a
   two-column grid: real `BrainViewer` iframe panel (left, restyled to glass-panel
   chrome, briefly showing the old procedural `BrainCanvas` as a loading visual that
   cross-fades out once the atlas iframe loads) and an info panel (right) that shows
   either the atlas-overview blurb (no region hovered/selected) or the active
   region's conditions list. Below the grid:
   two chip rows ("Rare conditions" / "Common baseline"), pill-shaped, hover/click
   drives the same hover/active state as the atlas panel.
4. **Retrieval trace** - horizontal `auto-fit` grid of numbered steps, each a glass
   card, staggered fade/slide-in (`0.6s ease {i*0.15s} delay`). Lives inside the
   Sourced summary panel's "Retrieval process" tab (see below), not a standalone
   page section; it is preceded there by a short "How this answer was produced."
   intro line.
5. **Sourced summary** - glass panel with a 4-stat header row (rarity weight, sources
   cited, region match confidence, corpus coverage), shown only in the success state,
   separated by a bottom border, then a tab bar, then tab content, then a right-hand
   citations rail (or below, stacked, under 900px width) with clickable
   citation-to-superscript cross-highlighting. The tab bar is **Summary / Case &
   region / Retrieval process / Rarity comparison** and renders across all three
   response states (success, degraded, no-match); only the Summary tab's content and
   the set of available tabs change per state (Case & region is present only when
   the backend resolves a matching condition and the summary call did not degrade).
   Retrieval process and Rarity comparison, previously standalone page sections, now
   live only inside these tabs, reachable in all three states.
6. **Rarity comparison** - two typographic columns side by side ("Naive ranking" /
   "Rarity-weighted ranking"), each paper row a link with a rank number and title;
   rare-condition rows get a pink-tinted background + border instead of a plain row.
   Lives inside the Sourced summary panel's "Rarity comparison" tab; its
   `/demo-contrast` fetch is lazy, triggered on first activation of that tab rather
   than on page load.

Responsive rule carried from the mockup: below 900px, two-column grids
(`atlasColumns`, `summaryColumns`) collapse to a single column
(`this.state.narrow`, driven by a `resize` listener).

## Hero canvas

2D canvas (not WebGL), two layers drawn every frame:
1. ~46 soft drifting particles (radius 0.6-2.8px, two hues: pale purple ~75% of
   particles, pale gold ~25%), looping wrap at viewport edges, very slow velocity
   (`±0.00009` normalized units/frame).
2. A procedurally generated branching neuron structure anchored around 68% width /
   42% height of the hero: 6 root branches at fixed angles, each recursively
   forking into 2-3 children per depth level (5 levels deep, length shrinking ×0.72
   per level), gradient stroke from pale purple to pale pink, gentle sinusoidal sway
   per branch keyed by a per-branch seed so branches don't move in lockstep. A
   pulsing radial-gradient glow sits at the root origin.

`prefers-reduced-motion: reduce` should disable both the particle drift and the
branch sway (freeze on a single frame), consistent with v1's motion rule.

## Motion

- 150-300ms for hover/press transitions (buttons, chips, tabs).
- Section scroll-reveal: opacity 0→1 + translateY 28px→0, 0.9s
  `cubic-bezier(.16,1,.3,1)`, triggered once per section when it crosses 88% of
  viewport height, not re-triggered on scroll-out.
- `prefers-reduced-motion: reduce` disables hero canvas motion, scroll-reveal
  animation (render revealed immediately instead), and any CSS transitions.

## Rejected / retained from v1

Retained: no AI-pitch filler copy, disclaimer non-negotiable on every brain
interaction, `prefers-reduced-motion` coverage, real Nilearn atlas integration
(not decorative).

Explicitly reversed from v1 (deliberate v2 choices, not oversights): purple/pink
glow background, tracked-uppercase eyebrow labels above every section, Space
Grotesk as the primary UI face.

## Open items for the build

- `BrainViewer`'s hover/active state (currently driven by its own React state) should
  visually integrate with the atlas panel's info column and the rare/common chip
  rows below it, per the mockup's `hoverId`/`activeId` unified state pattern - hover
  a chip highlights the panel, hover the panel (once a real hover target exists on
  the iframe boundary, which it may not since iframe content isn't hoverable from
  the parent) highlights the chip. If the iframe can't report hover, drive the panel
  from chip hover/click only.
- Resolved (2026-07-24): the Sourced summary tab list no longer matches the mockup's
  `plain`/`causal`/`next`/`symptom` set. It ships as Summary / Case & region /
  Retrieval process / Rarity comparison, wired against real `QueryResult` data end
  to end (`case_context` and `differential` fields from `/query`), documented in
  [docs/summary-tabs-restructure.md](../../docs/summary-tabs-restructure.md).
- Rarity comparison section's naive/weighted lists should come from
  `getDemoContrast()` (`frontend/src/lib/api.ts`) once available; the mockup's
  `rarityDemo` fixture is a placeholder shape reference only.

# BudgetBot Frontend — Design Audit

**Date:** 2026-06-09 · **Scope:** `starter_apps/budgetbot/frontend`
**Benchmark:** Mercury · Linear · Stripe Dashboard · Vercel · Notion · Cash App
**Verdict:** Solid foundation (B+). Architecture, tokens, and a11y baseline are
already production-shaped. What's missing is the **last 15% of polish** that
separates "good demo" from "real product": typographic weight discipline, chart
finish, table density features, relative time, keyboard UX, and richer empty states.

Legend: ✓ pass · ~ partial · ✗ fail · — n/a

---

## 1. Scorecard — criteria × screen

| # | Criterion | Dash | Txns | CSV | PDF | Insights | Settings | Chat | Global |
|---|-----------|:----:|:----:|:---:|:---:|:--------:|:--------:|:----:|:------:|
| 1 | Typography hierarchy | ~ | ~ | ~ | ~ | ~ | ~ | ✓ | ~ |
| 2 | Spacing discipline | ~ | ✓ | ~ | ~ | ~ | ~ | ✓ | ~ |
| 3 | Color discipline (tokens) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 4 | Number formatting | ~ | ✓ | ✓ | ✓ | ~ | ✓ | — | ~ |
| 5 | Micro-interactions | ~ | ~ | ~ | ~ | ~ | ~ | ✓ | ~ |
| 6 | Data density (table) | — | ~ | — | — | — | — | — | ~ |
| 7 | Empty states | ✓ | ~ | ✓ | — | ~ | — | ✓ | ~ |
| 8 | Loading states | ✓ | ✗ | ✓ | ✓ | ✓ | — | ✓ | ~ |
| 9 | Charts polish | ~ | — | — | — | ~ | — | — | ~ |
| 10 | Iconography (Lucide, sizing) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 11 | Navigation (active/hover) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ |
| 12 | Forms | — | — | ~ | ✓ | — | ~ | ✓ | ~ |
| 13 | Modal / drawer | — | ✓ | — | — | — | ✓ | ✓ | ✓ |
| 14 | Responsive | ✓ | ~ | ✓ | ✓ | ✓ | ✓ | ✓ | ~ |
| 15 | Accessibility | ✓ | ~ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 16 | Keyboard UX (shortcuts) | ✗ | ✗ | — | — | — | — | ✓ | ✗ |
| 17 | Theme (dark parity) | ~ | ~ | ~ | ~ | ~ | ~ | ~ | ~ |
| 18 | Brand touch | ~ | ~ | ~ | ~ | ~ | ~ | ✓ | ~ |

---

## 2. Findings by criterion (what's actually wrong)

**1. Typography** — `font-bold` (700) used on every page `h2` and every stat/amount
(12 files). Mercury/Linear use **600** for numbers and titles, reserving 700 for
one hero figure only. No shared type-scale primitives → each page re-declares sizes.
→ Fix: demote to `font-semibold`; add `<PageHeader>` + a documented type scale (24/18/16/14/13/12).

**2. Spacing** — Cards are `p-5` (20px); spec wants ≥24px (`p-6`). Pages use `space-y-5`
(20px) instead of the 24/32 rhythm. Section rhythm is uneven (no `mb-8` tiers).
→ Fix: card → `p-6`, page sections → `space-y-6`/`space-y-8`.

**3. Color** — ✓ Already clean: all components use semantic CSS-var tokens; only
modal/drawer scrims use raw `slate-950` (correct — scrims are theme-agnostic).
No `text-gray-*` leakage in app code. Keep as-is; just **add** `--warning` +
`--success`/`--danger` aliases so semantics read clearly.

**4. Number formatting** — VND ✓, dates ✓, compact ✓. **Missing:** percentage uses
`Math.round` → "12%" not VN "12,5%"; **no relative time** ("2 ngày trước", "vừa xong")
for recent lists; compact figures have no "full value on hover" affordance.
→ Fix: add `formatPercentVn`, `formatRelativeVn`, `formatDateLong`; wrap compact amounts in `title=`.

**5. Micro-interactions** — Global `:focus-visible` ✓ and `transition-colors` on most
hovers ✓. **Missing:** `active:scale-[.98]` press feedback is only on FAB/chat;
cards/rows/quick-actions don't depress. Buttons lack `active:` state.
→ Fix: add press-scale to Button + interactive cards; standardize `duration-150`.

**6. Data density** — Transactions table row height ok (`py-3` ≈ 44px) but: **no
sortable headers**, **no sticky header on scroll**, no compact toggle, no truncation
tooltip. Uses border rows (good — not zebra+border both).
→ Fix: sortable Date/Amount headers with arrow + `aria-sort`; sticky `thead`; `title` on truncated description.

**7. Empty states** — `EmptyState` component exists with icon + CTA (Dashboard ✓, CSV ✓).
**Weak:** Transactions "no results" passes only a title (no sub-copy/illustration);
Insights budgets empty is fine. No custom SVG illustration anywhere.
→ Fix: one lightweight inline SVG illustration; flesh out Transactions empty (title + subcopy + reset-filter CTA).

**8. Loading** — Dashboard/Insights use Skeletons ✓. **Transactions list shows plain
text "Đang tải…"** — biggest miss; needs a table skeleton. Skeleton uses `animate-pulse`,
spec prefers shimmer.
→ Fix: table-row skeleton for Transactions; upgrade `.skeleton` to a shimmer sweep.

**9. Charts** — Custom themed tooltip ✓, brand colors ✓, axes tabular ✓. **Missing:**
no explicit `animationDuration` → Recharts default ~1.5s bouncy ease; donut doesn't
reflow to horizontal bars on narrow mobile; no per-chart empty state (just "—").
→ Fix: `animationDuration={300}` + `animationEasing="ease-out"`; mobile donut→legend-only or bars; proper chart empty card.

**10. Iconography** — ✓ Lucide only, stroke-2 default, sizes 3.5/4/5 consistent. Pass.

**11. Navigation** — ✓ Sidebar active = `bg-secondary` + brand bottom-left area;
bottom nav ≤5; brand top-left. Minor: brand isn't a link to `/`; sidebar user id is
read once at mount (stale after rename).
→ Fix: wrap Brand in `<Link to="/">`; read user id reactively.

**12. Forms** — QuickAdd/PDF have top labels + helper + segmented control ✓. **Missing:**
no required `*` marks; no inline error text under fields (zod errors only via `aria-invalid`
ring); currency input has ₫ suffix ✓ but no format-on-blur normalization.
→ Fix: required marks + field-level error messages.

**13. Modal/drawer** — ✓ Backdrop blur + dim, Esc, focus trap (Radix/vaul), slide. Pass.

**14. Responsive** — Mostly ✓. Risk: Transactions **filter bar wraps awkwardly** at
768px (6 controls in a flex-wrap); amount min/max inputs cramped on 375px.
→ Fix: collapse filters into a "Bộ lọc" popover on mobile; stack amount range.

**15. Accessibility** — ✓ focus rings, aria-labels on icon buttons, `htmlFor` labels,
reduced-motion honored. Minor: checkbox `accent-[color:var(--primary)]` arbitrary may
not emit; table lacks `aria-sort` (tied to #6).

**16. Keyboard UX** — ✗ **Nothing global.** No `/` search focus, no `n` (Quick Add),
no `g d`/`g t` nav, no `Cmd/Ctrl+K`. Only chat has local Enter/Esc.
→ Fix: a `useKeyboardShortcuts` hook + a minimal Cmd+K command palette (reusing the existing Dialog).

**17. Dark mode** — Works and is designed (not naive invert), but uses cool **slate**.
Spec asks for **warmer dark + 10–15% desaturated accents**. Borders a touch low-contrast
in dark.
→ Fix: retune dark tokens (slate-950 bg is fine; lift card to `#1c2333`, borders `#2c3650`, desaturate positive/negative/primary slightly).

**18. Brand** — Logo mark ✓ (custom SVG ₿), favicon ✓. **Missing:** no accent glyph in
wordmark, no per-screen tagline, palette reads "safe blue".
→ Fix: small `✦` accent in wordmark; subtle tagline in sidebar footer; warm the primary one notch.

---

## 3. Top 10 highest-impact fixes (ordered)

1. **Chart finish** — 300ms ease-out entry, real empty states, mobile donut reflow. *(biggest "screenshot next to Stripe" win)*
2. **Typography weight pass** — 700→600 everywhere except one hero figure; shared `<PageHeader>` + type scale.
3. **Transactions table skeleton** + sortable/sticky headers. *(removes the only "Loading…" text)*
4. **Shimmer skeletons** (replace pulse) across Dashboard/Insights/Txns.
5. **Press-state micro-interactions** — `active:scale-[.98]` + unified `duration-150` on Button, cards, rows.
6. **Number formatting depth** — `formatPercentVn`, `formatRelativeVn`, long date; recent lists show relative time; compact amounts get `title=` full value.
7. **Dark-mode retune** — warmer surfaces, desaturated accents, stronger borders.
8. **Spacing rhythm** — card `p-6`, page `space-y-6/8`, consistent section tiers.
9. **Keyboard layer** — `/`, `n`, `g d/g t`, `Esc`, **Cmd+K palette**; shortcut hints in tooltips.
10. **Empty-state richness** — 1 reusable inline SVG illustration; flesh out Transactions empty + per-chart empties.

---

## 4. Proposed design-token updates (for PLAN review — not yet applied)

### Typography scale (new primitives, documented in `design-tokens.md`)
| Token | px / weight / leading / tracking | Use |
|---|---|---|
| `text-display` | 24 / 600 / 1.2 / -0.02em | page hero number only (700 allowed here) |
| `text-h1` | 20 / 600 / 1.25 / -0.015em | page titles |
| `text-h2` | 16 / 600 / 1.3 | card titles |
| `text-body` | 14 / 400 / 1.55 | default |
| `text-label` | 13 / 500 / 1.4 | form labels, table values |
| `text-caption` | 12 / 500 / 1.4 / 0.04em uppercase | table headers, eyebrows |

### Color tokens — add semantic aliases + retune dark
```
Light: --success #059669  --danger #dc2626  --warning #d97706   (unchanged, add --warning)
Dark (retuned, warmer + desaturated):
  --background #0f1729   --card #1c2333   --border #2b3550   --muted-foreground #9aa7bd
  --positive #2fbe87     --negative #ef6a6a   --primary #4f8ef7   (≈12% less saturated)
```

### Spacing rhythm (enforce subset)
`1 2 3 4 6 8 12 16 24` only. Card `p-6`, inner `p-4`, page section gap `space-y-6`
(within), `space-y-8` (between blocks). Drop all `p-5`/`space-y-5`.

### Motion tokens
`--ease-out: cubic-bezier(.2,.8,.2,1)` · micro 150ms · overlay 200ms · chart 300ms.
Press: `active:scale-[.98]`. All gated by existing `prefers-reduced-motion` block.

---

## 5. Execution plan (commit-by-commit, each builds green)

| # | Commit | Files (approx) |
|---|--------|----------------|
| 1 | Design tokens consolidation (color retune, motion vars, type primitives) | `index.css`, `design-tokens.md` |
| 2 | Typography pass (700→600, `<PageHeader>`, scale classes) | new `PageHeader.tsx`, all 6 pages, StatCard, charts |
| 3 | Number formatting (`formatPercentVn`/`formatRelativeVn`/`formatDateLong` + usages) | `lib/format.ts`, Dashboard, Txns, TransactionDetail |
| 4 | Empty states (SVG illustration, Transactions + chart empties) | `EmptyState.tsx`, new `illustrations.tsx`, Txns, charts |
| 5 | Loading skeletons (shimmer + Transactions table skeleton) | `skeleton.tsx`/`index.css`, new `TableSkeleton`, Txns |
| 6 | Chart polish (anim 300ms, empty cards, mobile donut reflow) | 4 chart files |
| 7 | Micro-interactions (press-scale Button + cards/rows, unify durations) | `button.tsx`, cards, Dashboard, Txns |
| 8 | Dark-mode parity audit + fix | `index.css` |
| 9 | Responsive audit (Txns filter popover on mobile, 375px pass) | `Transactions.tsx`, minor |
| 10 | Keyboard layer + a11y (`useKeyboardShortcuts`, Cmd+K palette, aria-sort) | new `useKeyboardShortcuts.ts`, `CommandPalette.tsx`, shell, Txns |

**Constraints honored:** no rebuild, no stack change, no new heavy deps (Cmd+K reuses
existing Radix Dialog — no `cmdk` needed), no API change. Each commit independently builds.

**Deliverables on completion:** this file (with before/after), `design-tokens.md`,
`CHANGELOG.md`, README "Design philosophy" section, 5 key screenshots for the quality gate.

---

## 6. After — what changed (all 10 commits shipped, build green)

| Criterion | Before | After |
|---|---|---|
| Typography | `font-bold` everywhere, per-page sizes | 600 default, `text-*` scale, `PageHeader` |
| Spacing | `p-5` cards, `space-y-5` | `p-6` cards, `space-y-6/8` rhythm |
| Number formatting | VND only | + VN `%`, relative time, long date, hover full-value |
| Empty states | icon + text | SVG illustrations + sub-copy + CTA; chart empties |
| Loading | pulse; "Đang tải…" on Txns | shimmer skeletons incl. Txns table skeleton |
| Charts | default ~1.5s bounce | 300ms ease-out, reduced-motion aware, empty cards |
| Micro-interactions | hover only | press-scale + focus-ring + unified 150ms |
| Dark mode | cool slate, faint borders | retuned navy, lifted surfaces, desaturated accents |
| Responsive | filter bar wraps at 768 | collapsible "Bộ lọc" on mobile, stacked range |
| Keyboard | none (global) | ⌘K/`/` palette, `n`, `g d/t/i/s`, sortable headers + `aria-sort` |

**Verification:** `tsc --noEmit` clean and `vite build` green after every commit;
all routes + new modules transpile under the dev server. New deps: **0**.

> Quality gate (5 screenshots: Dashboard / CSV / PDF / Transactions / Insights)
> is a manual visual step — run `pnpm dev` and capture in both themes.

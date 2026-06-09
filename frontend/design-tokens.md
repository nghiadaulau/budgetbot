# BudgetBot — Design Tokens

The single source of truth for color, typography, spacing, and motion. All tokens
live in `src/index.css` as CSS variables, exposed to Tailwind v4 utilities via
`@theme inline`. **Components never hardcode hex** — they reference semantic tokens
(`bg-card`, `text-muted-foreground`, `text-[color:var(--positive)]`).

## Philosophy

Modern fintech minimalism — calm navy identity, generous whitespace, restrained
weight. Money semantics are unmissable (income green / expense red) but never neon.
Light and dark are designed as a pair, not an inversion.

---

## Color

Semantic roles (not raw palette names). Each has a light and dark value tuned
independently for ≥4.5:1 text contrast and ≥3:1 UI contrast.

| Token | Role | Light | Dark |
|---|---|---|---|
| `--background` | app canvas | `#f8fafc` | `#0e1626` |
| `--foreground` | primary text | `#020617` | `#eef2f8` |
| `--card` / `--popover` | surfaces | `#ffffff` | `#1b2438` |
| `--primary` | brand / primary CTA | `#0f172a` | `#4f8ef7` |
| `--secondary` | subtle fills | `#eef2f7` | `#232e45` |
| `--muted-foreground` | secondary text | `#64748b` | `#9fadc4` |
| `--border` / `--input` | dividers, fields | `#e2e8f0` | `#2c3852` |
| `--ring` | focus ring | `#3b82f6` | `#5b9bf8` |
| `--positive` (success) | income, under-budget | `#059669` | `#34c98e` |
| `--negative` (danger) | expense, over-budget | `#dc2626` | `#f0736f` |
| `--warning` | near-limit, alerts | `#b45309` | `#e0a23c` |

**Dark-mode principles:** navy identity preserved; surfaces *lifted* (bg → card)
for elevation instead of borders alone; borders strengthened for visibility;
accents desaturated ~12% to reduce glare on dark.

**Category colors** (10 fixed brand hues) live in `src/lib/categories.ts`, rendered
as soft tints (`color` text on `color@12%` bg) that read in both themes.

**Chart series:** `--chart-1…8`, calm and distinct, mapped per category.

---

## Typography

**Family:** IBM Plex Sans (self-hosted, weights 300–700) — true tabular figures,
full Vietnamese diacritics. Amounts always use `.tabular`
(`font-variant-numeric: tabular-nums`) to prevent layout shift.

**Scale** (`@layer components` in `index.css`):

| Class | Size | Weight | Leading | Tracking | Use |
|---|---|---|---|---|---|
| `.text-display` | 28px | 700 | 1.15 | -0.025em | the one hero figure per view |
| `.text-h1` | 20px | 600 | 1.25 | -0.015em | page titles |
| `.text-h2` | 16px | 600 | 1.3 | -0.01em | card titles |
| `.text-body` | 14px | 400 | 1.55 | — | default body |
| `.text-label` | 13px | 500 | 1.4 | — | form labels, table values |
| `.text-caption` | 12px | 500 | 1.4 | 0.04em UPPER | table headers, eyebrows |

**Weight discipline:** 400 body · 500 labels · 600 titles & numbers. 700 only for
`.text-display`. Avoid arbitrary intermediate sizes.

---

## Spacing

Tailwind scale, restricted subset: **1 2 3 4 6 8 12 16 24** (4px base; avoid 5/7/11).

- Card padding: `p-6` (24px); inner sections `p-4` (16px).
- Vertical rhythm: `space-y-6` within a block, `space-y-8` between blocks.
- Page container: `max-w-6xl` centered, `px-4` (mobile) → `px-8` (desktop).

---

## Motion

| Token / value | Use |
|---|---|
| `--ease-snappy` `cubic-bezier(.2,.8,.2,1)` | enter / micro-interactions |
| 150ms | hover, color, press |
| 200ms | overlays (dialog, drawer, dropdown) |
| 300ms | chart entry (`animationEasing="ease-out"`) |
| `active:scale-[.98]` | press feedback on buttons & interactive cards |

All motion is gated by a global `prefers-reduced-motion: reduce` block (animations
and transitions collapse to ~0ms; shimmer disabled).

---

## Radius & elevation

`--radius` 0.75rem base → `rounded-md/lg/xl` derived. Single soft shadow scale
(`shadow-sm` cards, `shadow-md` popovers, `shadow-lg/xl` overlays) — no ad-hoc shadows.

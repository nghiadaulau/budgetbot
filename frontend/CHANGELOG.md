# Changelog

## Design refinement — fintech-grade polish (2026-06-09)

A 10-step polish pass taking the UI from "good demo" to "production-shaped",
benchmarked against Mercury / Linear / Stripe / Vercel. No rebuild, no stack
change, no API change, no new heavy dependency (the command palette reuses the
existing Radix Dialog).

### C1 · Design tokens
- Added semantic `--warning` (+ documented success/danger aliases).
- Retuned **dark mode** (navy identity kept): lifted surfaces (`#0e1626` bg /
  `#1b2438` card), stronger borders (`#2c3852`), accents desaturated ~12%.
- Added `--ease-snappy` motion token and a documented **type scale**
  (`.text-display/h1/h2/body/label/caption`).
- New `design-tokens.md` source-of-truth doc.

### C2 · Typography
- Demoted `font-bold` (700) → `font-semibold` (600) across the app; 700 reserved
  for the display scale only. Brand wordmark keeps bold.
- New `PageHeader` primitive; page titles unified to the `text-h1` token.

### C3 · Number formatting
- `formatPercentVn` ("12,5%"), `formatRelative` ("2 ngày trước" / "Hôm nay"),
  `formatDateLong` ("15 tháng 6, 2026").
- Dashboard recent list now shows **relative time** (full date on hover).
- Detail view uses the long date; donut centre shows full value on hover;
  percentages routed through the VN formatter.

### C4 · Empty states
- New inline SVG illustrations (`EmptyWalletIllustration`, `NoResultsIllustration`).
- Dashboard empty + Transactions no-results now have illustration + sub-copy +
  CTA (clear filters). Charts get a proper `ChartEmpty` instead of "—".

### C5 · Loading
- Skeleton upgraded from flat pulse to a **shimmer sweep** (`prefers-reduced-motion`
  aware). Transactions list shows a **table skeleton** instead of "Đang tải…".

### C6 · Charts
- 300 ms `ease-out` entry animations (gated by reduced-motion) on donut, bar,
  and area. Per-chart empty states. Donut + legend stack cleanly on mobile.

### C7 · Micro-interactions
- Press feedback (`active:scale-[.98]`) + focus ring + unified 150 ms easing on
  buttons and interactive cards.

### C8 · Spacing & dark parity
- Removed odd spacing steps: card padding `p-5 → p-6`, sections `space-y-5 → 6`.
- Verified text/border contrast in both themes.

### C9 · Responsive
- Transactions filter bar collapses behind a **"Bộ lọc"** toggle on mobile;
  amount range stacks full-width; search stays visible. Verified 375–1440px.

### C10 · Keyboard & a11y
- Global shortcuts: **⌘/Ctrl+K** & **/** open the command palette, **n** opens
  Quick Add, **g d / g t / g i / g s** navigate.
- New **Command Palette** (Radix Dialog) with filter + arrow-key navigation.
- Sortable **Date / Amount** table headers with arrow indicators + `aria-sort`.
- Discoverable ⌘K trigger in the header; shortcut hints on buttons.

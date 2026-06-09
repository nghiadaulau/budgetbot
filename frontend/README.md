# BudgetBot — Frontend

> **Stop logging expenses by hand. Let AI do it.**

The web UI for BudgetBot, a Vietnamese personal-finance bookkeeper. Upload a bank
statement (CSV) or a receipt (PDF), or type a transaction by hand — AI categorizes
everything and surfaces spending insights. Bilingual (VN primary, EN ready),
light + dark, mobile-first.

Built with **React 19 + Vite + TypeScript + Tailwind v4 + shadcn-style components
(Radix) + Recharts + React Query + react-router 7**.

---

## Quick start

```bash
pnpm install
pnpm dev
```

Open **http://localhost:5173**. The app ships with built-in sample data, so it
looks alive immediately — no backend required.

| Command | What it does |
|---|---|
| `pnpm dev` | Start the dev server (port 5173) |
| `pnpm build` | Type-check + production build to `dist/` |
| `pnpm preview` | Serve the production build locally |
| `pnpm typecheck` | `tsc --noEmit` only |

---

## Screens

| Route | Screen | Description |
|---|---|---|
| `/` | **Dashboard** | Hero stats (spent / income / net with vs-last-month deltas), spending-by-category donut, last-6-months bar chart, quick-action cards, recent transactions. Friendly empty state when there's no data. |
| `/transactions` | **Transactions** | Filterable table — search, multi-select category, source, amount range, month / all-months toggle. Inline category editing (optimistic, rolls back on failure), row → detail drawer, bulk recategorize, source icons, load-more paging. |
| `/upload` | **CSV upload** | Drag-drop CSV with staged AI progress ("Reading… → Categorizing 18… → Done") and a subtle cost hint, then an editable classified-results list. |
| `/receipt` | **PDF receipt** | Drag-drop a receipt PDF, "AI is reading your receipt…", then editable extracted fields (merchant, date, amount, collapsible line items, category chips) → confirm to save. |
| `/insights` | **Insights** | Daily-spend area chart, calendar heatmap, top merchants, and budget-vs-actual progress bars (live from the budgets API). |
| `/settings` | **Settings** | Display name (→ `X-User-Id`), CSV export, clear-all danger zone, theme toggle, VN/EN language, and a mock-mode switch. |

**Quick Add** (manual entry) is a global slide-over drawer — a right panel on
desktop, a bottom sheet on mobile — opened from the sidebar, the dashboard card,
or the mobile **FAB**. It has a large VND amount input, an expense/income toggle,
and AI category auto-suggest from the description.

**AI Money Coach chat** is a global widget — a floating bubble (bottom-right) on
desktop, a header icon on mobile (so it never collides with the FAB). It opens a
docked panel (full-height sheet on mobile) that **streams replies token-by-token**
over the backend's `POST /chat` SSE endpoint, with suggested prompts, a typing
indicator, month context, conversation persistence, and a reset button
(`POST /chat/reset`). In mock mode it streams a data-aware canned reply.

---

## Deduplication UX

The bookkeeper guards against double-entry across all input paths:
- **CSV/Excel re-upload** → a confirmation card (Skip / Append & dedupe / Replace),
  driven by the backend's `409 duplicate_file`. Results show
  "X saved · Y duplicates skipped" with an expandable list.
- **Manual Quick Add** → an inline "Possible duplicate" warning (lists the similar
  transactions) with **Save anyway**; editing the entry dismisses it.
- **Receipt / screenshot** → warning banners for re-scanned receipts and the
  offline-stub notice.

All of this works in mock mode too (the in-memory store implements file-hash +
transaction-fingerprint dedup).

## Design philosophy

Modern fintech minimalism — calm navy identity, generous whitespace, restrained
weight, money semantics you can't miss (income green / expense red) but never neon.
Light and dark are designed as a pair, not an inversion. Principles:

- **Numbers first.** Every amount uses tabular figures and VN formatting
  (`1.250.000 ₫`); relative time on recent items, full values on hover.
- **Weight discipline.** 400 body · 500 labels · 600 titles/numbers; 700 only for
  the one hero figure. A single type scale (`design-tokens.md`), not ad-hoc sizes.
- **Tokens, not hex.** Components reference semantic tokens; theming is centralized.
- **Motion with meaning.** 150 ms micro-interactions, 300 ms chart entries, all
  gated by `prefers-reduced-motion`. Press + focus states on everything tappable.
- **Keyboard-first.** ⌘K / `/` command palette, `n` quick add, `g d/t/i/s` nav.
- **Never a blank screen.** Skeletons while loading, illustrated empty states with
  a clear next action.

See `design-tokens.md` for the full system and `AUDIT_REPORT.md` / `CHANGELOG.md`
for the refinement history.

## Design system

- **Style:** modern fintech minimalism — calm slate-navy palette, soft shadows,
  generous whitespace. Income = emerald, expense = red. Light + dark designed together.
- **Type:** IBM Plex Sans (self-hosted via `@fontsource`) with **tabular figures**
  on every amount, and full Vietnamese diacritic coverage.
- **Tokens** live in `src/index.css` (`@theme inline` over CSS variables); the
  `.dark` class drives dark mode and is applied pre-paint in `index.html`.
- VND is always formatted `1.250.000 ₫`; dates as `15 Th6 2026` — see `src/lib/format.ts`.

---

## Wiring to the FastAPI backend

By default the app runs in **mock mode** (`VITE_USE_MOCK=true`) using an in-memory
store, so it's fully interactive offline. To talk to the real backend:

1. Copy the env file and point it at your API:
   ```bash
   cp .env.example .env
   ```
   ```dotenv
   VITE_API_URL=http://localhost:8000
   VITE_USE_MOCK=false
   ```
2. Run the backend (`uvicorn src.app:app --reload --port 8000` from the repo root).
3. `pnpm dev` — or flip **Settings → Use sample data** off at runtime.

**Auth:** there's no login. The display name from **Settings** is stored in
`localStorage` and sent as the `X-User-Id` header on every request.

**Dev proxy:** when `VITE_API_URL` is unset, requests go to `/api/*` and Vite
proxies them to `http://localhost:8000` (see `vite.config.ts`), avoiding CORS in
local dev.

### API client (`src/api/client.ts`)

Typed to the brief's REST contract; every method has a mock branch and a real
`fetch` branch:

| Method | Endpoint |
|---|---|
| `listTransactions(month?)` | `GET /transactions?month=YYYY-MM` |
| `getSummary(month?)` | `GET /summary?month=YYYY-MM` |
| `createTransaction(input)` | `POST /transaction` |
| `updateCategory(id, category)` | `PUT /transaction/{id}` |
| `deleteTransaction(id)` | `DELETE /transaction/{id}` |
| `uploadCsv(file)` | `POST /upload` (multipart) |
| `uploadPdf(file)` | `POST /upload-pdf` (multipart) |
| `getBudgets(month?)` / `setBudget(...)` | `GET` / `POST /budgets` |
| `streamChat(...)` / `resetChat(...)` | `POST /chat` (SSE) / `POST /chat/reset` |

> ⚠️ The current FastAPI app in this repo uses slightly different routes (plural
> `/transactions`, `PATCH`, no separate `/upload-pdf`). This client targets the
> brief's contract — align the backend routes to match, or adjust `client.ts`.

---

## Project layout

```
src/
├── api/          client.ts (typed endpoints + mock branch), chat.ts (SSE), types.ts
├── components/
│   ├── ui/       shadcn-style primitives (button, card, dialog, drawer, …)
│   ├── layout/   AppShell, Sidebar, BottomNav, Header, Fab, MonthPicker, toggles
│   ├── charts/   CategoryDonut, MonthlyBar, DailyTrend, CalendarHeatmap
│   ├── chat/     ChatWidget (AI money-coach, streaming)
│   └── transactions/  TransactionDetail, SourceIcon
├── context/      theme, i18n, ui (shared month + quick-add + chat state)
├── hooks/        useApi (React Query), useChat, useMediaQuery
├── i18n/         strings.ts (full VN + EN dictionary)
├── lib/          format (VND/dates), categories, aggregate, utils
├── mock/         data.ts (in-memory backend + seed)
└── pages/        Dashboard, Transactions, UploadCsv, UploadPdf, Insights, Settings
```

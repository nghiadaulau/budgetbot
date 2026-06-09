# BudgetBot — Talk slides

23-slide deck for the 15-minute talkshow (20/06/2026) — paced for **~12' talk +
3' live demo + Q&A**. Single self-contained `presentation.html` built on
**reveal.js v5** — no build step, works offline once the CDN assets are cached
(open it on venue wifi at least once beforehand).

Flow: Title → Team → Agenda → Pain → Question → Product → **6 decisions** →
Architecture → Adapter code → Hybrid AI → Prompt → Dedup → Async → Security →
**Demo** → Numbers → Cost → Testing → 3 Lessons → Hero quote → QR → Q&A.
Architecture & async diagrams render live via Mermaid (only when their slide is
shown — fixes the blank-diagram issue on hidden slides).

## Present

```bash
open docs/slides/presentation.html        # macOS (Chrome recommended)
```

Then press **F** for fullscreen and drive with the arrow keys.

### Keyboard shortcuts

| Key | Action |
|-----|--------|
| `→` / `←` / `Space` | Next / previous slide |
| `F` | Fullscreen |
| `S` | Speaker view (opens a window with notes + timer + next slide) |
| `ESC` | Overview grid of all slides |
| `T` | Toggle dark ⇄ light theme |
| `B` / `.` | Blackout (pause — black screen) |

Speaker notes (2–3 hints per slide) are written in `<aside class="notes">` and show
up in **Speaker view (S)**. Open `presentation.html` first, then press `S`.

## PDF handout

reveal.js prints via a URL flag:

1. Open `presentation.html?print-pdf` in Chrome.
2. **File → Print** (⌘P) → **Destination: Save as PDF**.
3. **Layout: Landscape**, **Margins: None**, **Background graphics: ON**.
4. Save — all 15 slides render one-per-page.

## Notes on content

- All figures are taken from the codebase (5,445 LOC `src/`, 1,674 LOC tests,
  113 tests pass / 11 skipped on SQLite, 78% coverage, 5 DB adapters, 20 `.tf`
  modules) — model is **Claude Haiku 4.5** at $1/$5 per 1M tokens, cost
  ~$0.017 per 1,000 transactions (keyword fast-path handles ~65% offline).
- Slide 7 renders `app_architecture` live via the Mermaid CDN.
- Slide 8/9 quote `src/adapters/factory.py` and `src/prompts.py` verbatim.
- Slide 14 generates the GitHub QR code client-side (qrcodejs) — no network call.

## Files

```
presentation.html        the deck (open this)
assets/preview_*.png      static previews of title / numbers / hero slides
README.md                 this file
```

## Re-generate the preview screenshots (optional)

```bash
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
F="file://$(pwd)/presentation.html"
"$CHROME" --headless=new --force-device-scale-factor=2 --window-size=1280,720 \
  --virtual-time-budget=6000 --screenshot=assets/preview_title.png "$F#/0"
```

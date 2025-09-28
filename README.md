# Daily ERP & Middleware Brief — $0 Starter (Enhanced)

Automates a daily newsletter:
- Pulls last 24h from a wide RSS list (+ optional GDELT)
- Dedupe, rank (vendor news > top tech press > blogs)
- AI summaries (optional) or fallback summaries
- Renders a polished HTML email (dark mode, preheader, view-in-browser)
- Sends via Brevo (free 300/day) and publishes an HTML archive in `out/`

## Setup
1. Push these files to your GitHub repo (main branch).
2. Add **Secrets** (Settings → Secrets and variables → Actions):
   - `BREVO_API_KEY`
   - `SENDER_EMAIL` (verified in Brevo)
   - `RECIPIENTS` (comma-separated for transactional mode)
   - Optional: `OPENAI_API_KEY`
   - Optional (for campaign mode): `BREVO_LIST_ID`
3. (Optional) **Variables** (Settings → Variables):
   - `SEND_MODE` = `transactional` or `campaign` (defaults to transactional)
   - `VIEW_URL_BASE` = Your GitHub Pages base URL (e.g. `https://you.github.io/repo/`)

## Run it
- Actions → **Daily Newsletter** → **Run workflow**.
- It also runs daily at **7:15am ET**.

## Customize
- Edit `sources.yml` to add/remove feeds.
- `KEYWORD_FILTER` is off by default (include everything in last 24h). Set `KEYWORD_FILTER=on` as a variable to enable keyword gating.
- Change the footer unsubscribe link in `pipeline.py`.
- To publish a public archive, enable **Settings → Pages** (Deploy from branch: main, root). The workflow also writes `out/index.html`.

## Deliverability
- In Brevo, authenticate your domain (SPF/DKIM) and add DMARC `p=none` to start.
- Keep List-Unsubscribe links (already present) and honor removals.

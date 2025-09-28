# Daily ERP & Middleware Brief — $0 Starter

This repo pulls the last 24h of ERP/middleware news from RSS + (optional) GDELT,
summarizes each item (OpenAI), renders an HTML newsletter, emails it via Brevo (free 300/day),
and publishes an HTML archive to `out/` (serve with GitHub Pages).

## 1) One-time setup
- Push this folder to your GitHub account.
- In **Settings → Secrets and variables → Actions**, add:
  - `OPENAI_API_KEY`
  - `BREVO_API_KEY`
  - `SENDER_EMAIL` (your verified Brevo sender email)
  - `RECIPIENTS` (comma-separated emails for now; switch to lists later)
- (Optional) edit `sources.yml` to add/remove feeds and GDELT queries.
- Turn on **Pages** (deploy from `main` root) if you want a public archive.

## 2) Run it
- It runs daily at 07:15 ET via cron.
- You can also run manually: **Actions → Daily Newsletter → Run workflow**.

## 3) Local test
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...
export BREVO_API_KEY=...
export SENDER_EMAIL=you@domain.com
export RECIPIENTS=you@domain.com
python pipeline.py
```

## 4) Customize
- Change keywords in `pipeline.py` (regex `kws`) or adjust scoring in `rank()`.
- Edit the email template in `email.html.j2` (simple, mobile-friendly).
- Set `MAX_ITEMS` env var (10–20 recommended).

## 5) Deliverability
- Authenticate your domain in Brevo (SPF, DKIM; add DMARC p=none to start).
- Add a real unsubscribe URL and honor removals promptly.
- Keep complaints low; seed-test with internal addresses first.

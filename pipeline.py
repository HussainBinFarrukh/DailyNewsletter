
import os, time, json, math, hashlib, html, re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
import yaml, feedparser, requests
from dateutil import parser as dtparse
from jinja2 import Environment, FileSystemLoader, select_autoescape

# ---- Config via env ----
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
SENDER_NAME = os.getenv("SENDER_NAME", "Daily ERP Brief")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "no-reply@example.com")
RECIPIENTS = [e.strip() for e in os.getenv("RECIPIENTS", "").split(",") if e.strip()]
TIMEZONE = os.getenv("TIMEZONE", "America/New_York")
MAX_ITEMS = int(os.getenv("MAX_ITEMS", "15"))
MIN_TOP = min(5, MAX_ITEMS)

ROOT = os.path.dirname(__file__)

def load_sources():
    with open(os.path.join(ROOT, "sources.yml"), "r") as f:
        return yaml.safe_load(f)

def parse_when(s):
    try:
        dt = dtparse.parse(s)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None

def fetch_rss(url):
    d = feedparser.parse(url)
    items = []
    for e in d.entries:
        title = e.get("title", "").strip()
        link = e.get("link", "").strip()
        published = e.get("published") or e.get("updated") or ""
        published_parsed = None
        if e.get("published_parsed"):
            published_parsed = datetime.fromtimestamp(time.mktime(e.published_parsed), tz=timezone.utc)
        elif published:
            published_parsed = parse_when(published)
        items.append({
            "title": title,
            "url": link,
            "published": published_parsed,
            "source": d.feed.get("title", url),
            "summary_raw": html.unescape(e.get("summary", ""))[:1500]
        })
    return items

def fetch_gdelt(query):
    # 24h window
    url = "https://api.gdeltproject.org/api/v2/doc/doc"
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "TIMESPAN": "24H",
        "maxrecords": "75"
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    js = r.json()
    items = []
    for a in js.get("articles", []):
        published = parse_when(a.get("seendate") or a.get("pubtime") or a.get("publishdate"))
        items.append({
            "title": a.get("title") or "",
            "url": a.get("url") or "",
            "published": published,
            "source": a.get("sourceDomain") or "GDELT",
            "summary_raw": a.get("socialimage") or ""
        })
    return items

def within_last_24h(dt):
    if not dt: return False
    return (datetime.now(timezone.utc) - dt) <= timedelta(hours=24)

def rank(items):
    # Simple scoring: vendor newsroom > big tech press > blogs, plus recency
    def score(it):
        src = (it.get("source") or "").lower()
        s = 0
        if any(x in src for x in ["sap", "oracle", "microsoft", "boomi", "mulesoft", "workato", "partnerlinq"]):
            s += 3
        if any(x in src for x in ["infoworld", "register", "gartner", "idc"]):
            s += 2
        # recency boost
        if it.get("published"):
            hrs = (datetime.now(timezone.utc) - it["published"]).total_seconds()/3600
            s += max(0, 2 - hrs/12)  # up to +2 if very fresh
        # title signals
        title = (it.get("title") or "").lower()
        if any(k in title for k in ["ga", "generally available", "roadmap", "security", "cve", "patch", "partnership", "acquires", "announces"]):
            s += 1.0
        return s
    return sorted(items, key=score, reverse=True)

def dedupe(items):
    seen = set()
    out = []
    for it in items:
        key = it["url"].split("?")[0].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out

def summarize_batch(items):
    # If no OpenAI key, return trimmed title as "summary" for smoke tests.
    for it in items:
        it["summary"] = ""
        it["why"] = ""

    if not OPENAI_API_KEY:
        for it in items:
            it["summary"] = it["summary_raw"][:140] or it["title"]
            it["why"] = ""
        return items

    # Use OpenAI Chat Completions via raw HTTP to avoid SDK drift
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    for it in items:
        prompt = f"""Summarize the following news item in exactly two concise sentences. Then add one bullet that starts with 'Why it matters:' focused on ERP/middleware pros.
Title: {it['title']}
URL: {it['url']}
Snippet: {it['summary_raw'][:1200]}"""
        payload = {
            "model": OPENAI_MODEL,
            "messages": [{"role":"user","content": prompt}],
            "temperature": 0.2,
            "max_tokens": 160
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            txt = resp.json()["choices"][0]["message"]["content"].strip()
            parts = txt.split("Why it matters:", 1)
            summary = parts[0].strip().rstrip("-•").strip()
            why = parts[1].strip(" -•\n") if len(parts) > 1 else ""
            it["summary"] = summary
            it["why"] = why
        except Exception as e:
            it["summary"] = it["summary_raw"][:200] or it["title"]
            it["why"] = ""
    return items

def render(items, date_dt, out_path, unsubscribe_url):
    env = Environment(
        loader=FileSystemLoader(ROOT),
        autoescape=select_autoescape(["html","xml"])
    )
    tmpl = env.get_template("email.html.j2")
    for it in items:
        dt = it.get("published")
        it["published_human"] = dt.astimezone(timezone.utc).strftime("%b %d, %H:%M UTC") if dt else "—"
    top = items[:min(len(items), 5)]
    rest = items[5:]
    html_out = tmpl.render(
        subject=f"Daily ERP & Middleware Brief — {date_dt.strftime('%b %d, %Y')}",
        date_str=date_dt.strftime("%A, %B %d, %Y"),
        items=items, top=top, rest=rest,
        unsubscribe_url=unsubscribe_url,
        sender_name=SENDER_NAME, sender_email=SENDER_EMAIL
    )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_out)
    return html_out

def send_brevo(html, subject):
    if not BREVO_API_KEY or not RECIPIENTS:
        print("Skipping send: BREVO_API_KEY or RECIPIENTS missing.")
        return
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "api-key": BREVO_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "sender": {"name": SENDER_NAME, "email": SENDER_EMAIL},
        "to": [{"email": e} for e in RECIPIENTS],
        "subject": subject,
        "htmlContent": html,
        "headers": {
            "List-Unsubscribe": "<https://example.com/unsubscribe>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"
        }
    }
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    print("Brevo send status:", r.status_code)

def main():
    sources = load_sources()
    all_items = []

    for url in sources.get("rss_feeds", []):
        try:
            all_items += fetch_rss(url)
        except Exception as e:
            print("RSS error:", url, e)

    for q in sources.get("gdelt_queries", []):
        try:
            all_items += fetch_gdelt(q)
        except Exception as e:
            print("GDELT error:", q, e)

    # filter last 24h and keywords
    kws = re.compile(r"(SAP|S/4HANA|Oracle|Fusion|middleware|iPaaS|EDI|integration|Dynamics 365|supply chain)", re.I)
    fresh = [it for it in all_items if within_last_24h(it.get("published")) and kws.search((it.get("title","") + " " + it.get("summary_raw",""))) ]

    cleaned = dedupe(fresh)
    ranked = rank(cleaned)[: max(10, min(MAX_ITEMS, 20))]

    summarized = summarize_batch(ranked)

    out_dir = os.path.join(ROOT, "out")
    os.makedirs(out_dir, exist_ok=True)
    today = datetime.now(timezone.utc).date()
    out_path = os.path.join(out_dir, f"{today.isoformat()}.html")

    html_body = render(summarized, datetime.now(timezone.utc), out_path, unsubscribe_url="https://example.com/unsubscribe")
    subject = f"Daily ERP & Middleware Brief — {datetime.now(timezone.utc).strftime('%b %d, %Y')}"
    send_brevo(html_body, subject)
    print("Rendered:", out_path)

if __name__ == "__main__":
    main()

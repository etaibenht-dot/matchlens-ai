"""Collect job listings from LinkedIn (guest pages), Israeli job sites and career pages."""
import logging
import os
import re
import time
from datetime import datetime, timedelta
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
session = requests.Session()
session.headers.update({
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
})
EN = {"Accept-Language": "en-US,en;q=0.9"}

DEBUG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug")
LI_SEARCH = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
LI_POSTING = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{}"


def _get(url, **kw):
    try:
        return session.get(url, timeout=30, **kw)
    except requests.RequestException as e:
        log.warning("Request failed %s: %s", url, e)
        return None


def _txt(el):
    return el.get_text(" ", strip=True) if el else ""


def _save_debug(name, html):
    os.makedirs(DEBUG_DIR, exist_ok=True)
    slug = re.sub(r"[^\w\-]+", "_", name)[:80]
    with open(os.path.join(DEBUG_DIR, f"{slug}.html"), "w", encoding="utf-8") as f:
        f.write(html)


def page_text(html, limit=4000):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "header", "footer", "nav", "iframe"]):
        tag.decompose()
    root = soup.find("main") or soup.find("article") or soup.body or soup
    lines = [ln.strip() for ln in root.get_text("\n").splitlines()]
    text = "\n".join(ln for ln in lines if ln)
    return text[:limit]


# ---------------- LinkedIn ----------------
_REL = re.compile(r"(\d+)\s*(minute|hour|day|week|month)s?\s+ago", re.I)


def _li_posted(time_tag, now):
    if not time_tag:
        return ""
    m = _REL.search(_txt(time_tag))
    if m:
        n, unit = int(m.group(1)), m.group(2).lower()
        delta = {"minute": timedelta(minutes=n), "hour": timedelta(hours=n), "day": timedelta(days=n),
                 "week": timedelta(weeks=n), "month": timedelta(days=30 * n)}[unit]
        t = now - delta
        return f"{t:%d/%m/%Y} בסביבות {t:%H:%M}" if unit in ("minute", "hour") else f"{t:%d/%m/%Y}"
    dt = time_tag.get("datetime")
    if dt:
        try:
            return datetime.strptime(dt, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            return dt
    return _txt(time_tag)


def collect_linkedin(cfg, now, state=None):
    lc = cfg["linkedin"]
    jobs, ids, failures = [], set(), 0
    # regular searches, plus searches limited to LinkedIn's "Entry level" filter (f_E=2)
    searches = [(kw, None) for kw in lc["keywords"]] + [(kw, "2") for kw in lc.get("entry_level_keywords", [])]
    # fewer requests per run = fewer blocks: each run does part of the list, in turns.
    # hours_back covers a full day, so every search still runs at least once a day.
    per_run = int(lc.get("searches_per_run", len(searches)))
    st = state if state is not None else {}
    start = int(st.get("li_cursor", 0)) % max(1, len(searches))
    order = searches[start:] + searches[:start]
    failed_before = [tuple(x) for x in st.get("li_failed", []) if tuple(x) in searches]
    todo = failed_before + [x for x in order if x not in failed_before]
    todo = todo[:per_run]
    st["li_cursor"] = (start + per_run) % max(1, len(searches))
    failed_now = []
    for kw, level in todo:
        for page in range(int(lc.get("pages_per_keyword", 1))):
            params = {
                "keywords": kw,
                "location": lc.get("location", "Israel"),
                "f_TPR": f"r{int(lc.get('hours_back', 24)) * 3600}",
                "f_JT": "F",
                "start": page * 25,
            }
            if level:
                params["f_E"] = level
            r = _get(LI_SEARCH, params=params, headers=EN)
            time.sleep(lc.get("seconds_between_requests", 8))
            if r is not None and r.status_code == 429:
                log.info("LinkedIn asked to slow down, waiting 60s and retrying once")
                time.sleep(60)
                r = _get(LI_SEARCH, params=params, headers=EN)
                time.sleep(lc.get("seconds_between_requests", 8))
            if r is None or r.status_code != 200:
                failures += 1
                code = r.status_code if r is not None else "network"
                log.warning("LinkedIn '%s' -> %s", kw, code)
                if page == 0:
                    failed_now.append([kw, level])
                if failures >= 4:
                    log.warning("LinkedIn blocked too many times, stopping LinkedIn for this run")
                    done_idx = todo.index((kw, level))
                    failed_now += [[k, l] for k, l in todo[done_idx + 1:]]
                    st["li_failed"] = failed_now
                    return jobs
                break
            soup = BeautifulSoup(r.text, "html.parser")
            items = soup.find_all("li")
            for li in items:
                urn_el = li.select_one("[data-entity-urn]")
                link = li.select_one("a.base-card__full-link, a[href*='/jobs/view/']")
                m = re.search(r"(\d{6,})", urn_el.get("data-entity-urn", "") if urn_el else "")
                if not m and link:
                    m = re.search(r"(\d{6,})", link.get("href", "").split("?")[0])
                if not m:
                    continue
                jid = m.group(1)
                if jid in ids:
                    continue
                ids.add(jid)
                jobs.append({
                    "key": f"linkedin:{jid}",
                    "source": "LinkedIn",
                    "source_id": jid,
                    "title": _txt(li.select_one(".base-search-card__title")),
                    "company": _txt(li.select_one(".base-search-card__subtitle")),
                    "location": _txt(li.select_one(".job-search-card__location")),
                    "posted": _li_posted(li.select_one("time"), now),
                    "url": f"https://www.linkedin.com/jobs/view/{jid}/",
                })
            if len(items) < 25:
                break
    st["li_failed"] = failed_now
    log.info("LinkedIn: %d jobs (%d searches this run, %d to retry next run)", len(jobs), len(todo), len(failed_now))
    return jobs


# ---------------- Israeli sites & career pages ----------------
def _links_via_gemini(base_url, soup, gemini):
    links = []
    for a in soup.find_all("a", href=True):
        t = a.get_text(" ", strip=True)
        if t and len(t) > 3:
            links.append(f"{t[:120]} | {urljoin(base_url, a['href'])}")
    if not links:
        return []
    prompt = (
        "Below are links from a jobs/careers page (text | url). Return ONLY links that point to an "
        "individual job posting (not categories, filters, login, or company pages). "
        'Respond as JSON: {"jobs": [{"title": "...", "url": "..."}]}\n\n' + "\n".join(links[:400])
    )
    try:
        data = gemini.json(prompt)
    except Exception as e:  # noqa: BLE001
        log.warning("Gemini link extraction failed: %s", e)
        return []
    return [j for j in data.get("jobs", []) if j.get("url", "").startswith("http")]


def scrape_listing(name, url, pattern, gemini, fallback_budget):
    r = _get(url)
    if r is None or r.status_code != 200:
        log.warning("%s: %s -> %s", name, url, r.status_code if r is not None else "network error")
        return []
    _save_debug(f"{name}_{url[-40:]}", r.text)
    soup = BeautifulSoup(r.text, "html.parser")
    found = {}
    if pattern:
        rx = re.compile(pattern)
        for a in soup.find_all("a", href=True):
            href = urljoin(url, a["href"])
            m = rx.search(href)
            if not m:
                continue
            jid = m.group(1) if m.groups() else href
            title = a.get_text(" ", strip=True) or a.get("title", "")
            card = _card_text(a, rx, url)
            if jid in found:
                if len(title) > len(found[jid]["title"]):
                    found[jid]["title"] = title
                if len(card) > len(found[jid]["card"]):
                    found[jid]["card"] = card
                continue
            found[jid] = {"title": title, "url": href, "card": card}
    if not found and gemini and fallback_budget[0] > 0:
        fallback_budget[0] -= 1
        log.info("%s: no links matched pattern, asking Gemini", name)
        for j in _links_via_gemini(url, soup, gemini):
            found[j["url"]] = {"title": j.get("title", ""), "url": j["url"], "card": ""}
    log.info("%s [%s]: %d jobs", name, url, len(found))
    return [{
        "key": f"{name}:{jid}",
        "source": name,
        "source_id": jid,
        "title": v["title"],
        "company": "",
        "location": "",
        "posted": "",
        "url": v["url"],
        "card": v.get("card", ""),
    } for jid, v in found.items()]


def _card_text(a, rx, base, max_len=900):
    """The text of the search-result card around a job link (company, city, years, date, snippet).
    Climbs up the page until the block would include another job."""
    best = ""
    node = a
    for _ in range(7):
        node = node.parent
        if node is None:
            break
        ids = set()
        for link in node.find_all("a", href=True):
            m = rx.search(urljoin(base, link["href"]))
            if m:
                ids.add(m.group(1) if m.groups() else m.group(0))
        t = re.sub(r"\s+", " ", node.get_text(" | ", strip=True))
        if len(ids) > 1 or len(t) > max_len:
            break
        best = t
    return best


def collect_sites(cfg, gemini):
    jobs = []
    sc = cfg.get("israeli_sites") or {}
    budget = [int(sc.get("max_gemini_fallback_calls", 3))]
    if sc.get("enabled"):
        for site in sc.get("sites", []):
            for q in sc.get("queries", []):
                url = site["url"].format(query=quote(q))
                jobs += scrape_listing(site["name"], url, site.get("link_pattern"), gemini, budget)
                time.sleep(sc.get("seconds_between_requests", 3))
    for page in cfg.get("career_pages") or []:
        jobs += scrape_listing(page["name"], page["url"], page.get("link_pattern"), gemini, [1])
    return jobs


# ---------------- Details ----------------
CLOSED_MARKERS = ("no longer accepting applications", "this job is no longer available", "job not found",
                  "המשרה אינה פעילה", "המשרה לא נמצאה", "המשרה הוסרה", "המשרה כבר לא", "משרה זו אינה זמינה",
                  "המודעה אינה פעילה", "המשרה נסגרה")


def fetch_details(job):
    """Adds the full posting text, whether it is still open, and the best link to apply."""
    job["closed"] = False
    job["apply_url"] = job["url"]
    if job["source"] == "LinkedIn":
        r = _get(LI_POSTING.format(job["source_id"]), headers=EN)
        time.sleep(3)
        if r is not None and r.status_code == 429:
            time.sleep(30)
            r = _get(LI_POSTING.format(job["source_id"]), headers=EN)
            time.sleep(3)
        if r is None or r.status_code != 200:
            job["description"] = ""
            job["closed"] = r is not None and r.status_code in (404, 410)
            return job
        soup = BeautifulSoup(r.text, "html.parser")
        el = soup.select_one(".show-more-less-html__markup")
        desc = el.get_text("\n", strip=True) if el else ""
        crit = " | ".join(_txt(li) for li in soup.select(".description__job-criteria-item"))
        job["description"] = (f"{crit}\n{desc}" if crit else desc)[:7000]
        job["closed"] = any(m in r.text.lower() for m in CLOSED_MARKERS)
        code = soup.select_one("code#applyUrl")
        m = re.search(r'"(https?://[^"]+)"', str(code)) if code else None
        if m:
            job["apply_url"] = m.group(1).replace("&amp;", "&")
        return job
    r = _get(job["url"])
    time.sleep(1.5)
    if r is None or r.status_code != 200:
        job["description"] = ""
        job["closed"] = r is not None and r.status_code in (404, 410)
        return _use_card(job)
    full = page_text(r.text, limit=30000)
    job["description"] = _focus(full, job.get("title", ""))
    if len(job["description"]) < 250:
        return _use_card(job)
    job["closed"] = any(m in job["description"][:3000].lower() for m in CLOSED_MARKERS)
    return job


def _use_card(job):
    """The job page could not be read: fall back to the summary shown in the search results."""
    if job.get("card") and not job.get("closed"):
        job["description"] = "[PARTIAL - only the search-result summary could be read]\n" + job["card"]
        job["partial"] = True
    return job


SECTION_END = ("משרות דומות", "משרות נוספות", "עוד משרות", "משרות שעשויות לעניין", "similar jobs", "more jobs",
               "משרות אחרונות שצפית", "משרות מומלצות")


def _focus(text, title, size=4500):
    """Job pages on Israeli sites also show menus and OTHER jobs ("similar jobs").
    Keep only this job's own part: from its title until a "similar jobs" section."""
    flat = re.sub(r"[ \t/|\-–]+", " ", text)
    words = [w for w in re.split(r"[\s/|\-–]+", title or "") if len(w) > 1][:4]
    start = 0
    for n in (4, 3, 2):
        key = " ".join(words[:n])
        if len(key) >= 6 and key in flat:
            start = flat.find(key)
            break
    part = flat[start:start + size]
    low = part.lower()
    cuts = [low.find(m) for m in SECTION_END if low.find(m) > 200]
    return part[:min(cuts)] if cuts else part

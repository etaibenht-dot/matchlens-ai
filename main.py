"""Job alerts: collect -> filter -> AI score -> Telegram digest at fixed hours."""
import csv
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import yaml

from basic import precheck
import feedback
from gemini import Gemini
from mail_alerts import collect_mail
from scorer import verify_jobs
from sources import collect_linkedin, collect_sites, fetch_details
from telegram_sender import build_header, send_digest

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("main")

ROOT = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(ROOT, "state.json")
SEEN_DAYS = 30
REJ_PATH = os.path.join(ROOT, "rejections.csv")
REJ_FIELDS = ["date", "stage", "source", "title", "company", "reason", "url"]
MAX_TRIES = 4          # runs to retry a job that could not be verified before dropping it
MAX_QUEUE = 400


def recheck_once(state, cfg):
    """One-time fix: Israeli-site jobs that were rejected by the old automatic experience check
    (which could read other ads on the page) are forgotten, so they are verified again properly."""
    if state.get("recheck_v1"):
        return
    patterns = {site["name"]: re.compile(site["link_pattern"]) for site in
                (cfg.get("israeli_sites") or {}).get("sites", []) if site.get("link_pattern")}
    n = 0
    try:
        with open(REJ_PATH, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                rx = patterns.get(row.get("source"))
                if rx and row.get("stage") == "בדיקה אוטומטית" and "ניסיון" in row.get("reason", ""):
                    m = rx.search(row.get("url", ""))
                    if m and state.get("seen", {}).pop(f"{row['source']}:{m.group(1)}", None):
                        n += 1
    except FileNotFoundError:
        pass
    state["recheck_v1"] = True
    log.info("Re-checking %d jobs that the old experience check may have rejected by mistake", n)


def log_rejections(rows):
    """Internal log of every job that was not sent, and why (opens as a table on GitHub)."""
    old = []
    try:
        with open(REJ_PATH, encoding="utf-8-sig", newline="") as f:
            old = list(csv.DictReader(f))
    except FileNotFoundError:
        pass
    allrows = (old + rows)[-3000:]
    with open(REJ_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=REJ_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(allrows)


def load_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {"seen": {}, "last_slot": ""}


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1, sort_keys=True)


def current_slot(send_hours, now):
    """Latest send hour that already passed today, e.g. '2026-11-05-9'."""
    passed = [h for h in sorted(send_hours) if h <= now.hour]
    return (f"{now:%Y-%m-%d}-{passed[-1]}", passed[-1]) if passed else (None, None)


def norm(s):
    return re.sub(r"\W+", " ", (s or "").lower()).strip()


def has_any(text, words):
    t = (text or "").lower()
    return any(w.lower() in t for w in words)


def main():
    with open(os.path.join(ROOT, "config.yaml"), encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    with open(os.path.join(ROOT, "profile.md"), encoding="utf-8") as f:
        profile = f.read()

    tz = ZoneInfo(cfg["schedule"]["timezone"])
    now = datetime.now(tz)
    force = os.getenv("FORCE_RUN", "").lower() in ("1", "true", "yes")
    state = load_state()

    # button presses (applied / saved / not relevant) are collected on every run
    feedback.process_presses(state, now)
    feedback.prune(state, now)

    slot, slot_hour = current_slot(cfg["schedule"]["send_hours"], now)
    if not force:
        if slot is None:
            log.info("Before the first send hour (%s local). Nothing to do.", now.strftime("%H:%M"))
            save_state(state)
            return
        if state.get("last_slot") == slot:
            log.info("Slot %s already sent. Nothing to do.", slot)
            save_state(state)
            return
    label_hour = slot_hour if (slot_hour is not None and not force) else now.hour

    # forget old seen jobs
    cutoff = (now - timedelta(days=SEEN_DAYS)).date().isoformat()
    state["seen"] = {k: v for k, v in state.get("seen", {}).items() if v >= cutoff}
    recheck_once(state, cfg)
    seen = state["seen"]

    g = cfg["gemini"]
    use_ai = bool(g.get("enabled", True))
    gemini = Gemini(g["models"], g.get("seconds_between_calls", 13), g.get("max_minutes", 8)) if use_ai else None

    today = now.date().isoformat()
    rej = []

    def reject(j, stage, reason):
        rej.append({"date": today, "stage": stage, "source": j.get("source", ""), "title": j.get("title", ""),
                    "company": j.get("company", ""), "reason": reason, "url": j.get("url", "")})

    # ---------- Stage A: discovery ----------
    candidates = list(state.get("queue", {}).values())   # jobs waiting from earlier runs come first
    candidates += collect_mail(cfg, now)        # job-alert emails first (most reliable for LinkedIn)
    if cfg.get("linkedin", {}).get("enabled"):
        candidates += collect_linkedin(cfg, now, state)
    candidates += collect_sites(cfg, gemini)
    log.info("Collected %d listings in total (incl. %d queued)", len(candidates), len(state.get("queue", {})))

    done, fresh, seen_pairs, keys = [], [], set(), set()
    for j in candidates:
        if j["key"] in seen or j["key"] in keys:
            continue
        keys.add(j["key"])
        pair = (norm(j["title"]), norm(j["company"]))
        if j["company"] and pair in seen_pairs:
            done.append(j["key"])
            continue
        seen_pairs.add(pair)
        bad_title = [w for w in cfg.get("title_exclude", []) if w.lower() in (j["title"] or "").lower()]
        if bad_title:
            reject(j, "סינון מוקדם", f"כותרת: {bad_title[0].strip()}")
            done.append(j["key"])
            continue
        bad_loc = [w for w in cfg.get("location_exclude", []) if w.lower() in f"{j['location']} {j['title']}".lower()]
        if bad_loc:
            reject(j, "סינון מוקדם", f"מיקום: {bad_loc[0]}")
            done.append(j["key"])
            continue
        fresh.append(j)
    log.info("New after light pre-filter: %d", len(fresh))

    prio = cfg.get("priority_title_words", [])
    queued = state.get("queue", {})
    # fair share: queued jobs first, then take turns between sources (LinkedIn, AllJobs, Drushim, JobMaster...)
    fresh.sort(key=lambda j: 0 if has_any(j["title"], prio) else 1)
    waiting = [j for j in fresh if j["key"] in queued]
    by_source = {}
    for j in fresh:
        if j["key"] not in queued:
            by_source.setdefault(j["source"], []).append(j)
    mixed = []
    while any(by_source.values()):
        for src in list(by_source):
            if by_source[src]:
                mixed.append(by_source[src].pop(0))
    fresh = waiting + mixed
    to_check = fresh[: int(g.get("max_jobs_to_score", 60))]
    later = fresh[len(to_check):]

    # ---------- Stage B: verify requirements ----------
    for j in to_check:
        fetch_details(j)
    ready = []
    for j in to_check:
        reason = precheck(j)
        if reason:
            reject(j, "בדיקה אוטומטית", reason)
            done.append(j["key"])
        else:
            ready.append(j)
    readable = [j for j in ready if j.get("description")]
    results, verified = [], set()
    if gemini and readable:
        results, verified = verify_jobs(gemini, profile + feedback.profile_note(state), readable, today,
                                        int(g.get("batch_size", 6)))
        log.info("Gemini calls: %d, verified %d/%d", gemini.calls, len(verified), len(readable))

    # not verified (AI busy / page unreadable): keep in the queue and retry, never send unverified
    tries = state.setdefault("tries", {})
    queue = {}
    for j in ready:
        if j["key"] in verified:
            tries.pop(j["key"], None)
            continue
        n = tries.get(j["key"], 0) + 1
        if n >= MAX_TRIES:
            reject(j, "לא אומת", "לא ניתן היה לקרוא או לאמת את הדרישות המלאות")
            done.append(j["key"])
            tries.pop(j["key"], None)
        else:
            tries[j["key"]] = n
            queue[j["key"]] = {k: v for k, v in j.items() if k not in ("description",)}
    for j in later:
        queue[j["key"]] = {k: v for k, v in j.items() if k not in ("description",)}
    state["queue"] = dict(list(queue.items())[:MAX_QUEUE])

    # ---------- Stage C: score and send ----------
    feedback.adjust(results, state)
    min_score = float(cfg.get("min_score_to_send", 6))
    approved, manual = [], []
    for r in results:
        done.append(r["key"])
        if r["verdict"] == "reject":
            reject(r, "אימות דרישות", r["reason"] or "לא עומד בדרישת חובה")
        elif r["score"] is None or r["score"] < min_score:
            reject(r, "ציון נמוך", f"ציון {r['score']}")
        elif r["verdict"] == "pass":
            approved.append(r)
        else:
            r["check"] = r["reason"] or "ניסוח לא חד במודעה"
            manual.append(r)
    # approved jobs first, then the ones to double-check (marked with ⚠️), each by score
    approved.sort(key=lambda r: r["score"], reverse=True)
    manual.sort(key=lambda r: r["score"], reverse=True)
    max_cards = int(cfg.get("max_jobs_to_send", 25))
    cards = (approved + manual)[:max_cards]

    stats = {}
    for j in candidates:
        stats.setdefault(j["source"], {"collected": 0, "new": 0, "checked": 0, "read": 0, "partial": 0, "sent": 0})
        stats[j["source"]]["collected"] += 1
    for j in fresh:
        stats[j["source"]]["new"] += 1
    for j in to_check:
        st_ = stats[j["source"]]
        st_["checked"] += 1
        if j.get("partial"):
            st_["partial"] += 1
        elif j.get("description"):
            st_["read"] += 1
    for j in cards:
        stats[j["source"]]["sent"] += 1
    for src, v in stats.items():
        log.info("SOURCE %s: collected %d, new %d, checked %d, read %d, summary-only %d, sent %d",
                 src, v["collected"], v["new"], v["checked"], v["read"], v["partial"], v["sent"])

    if cards:
        n_pre = sum(1 for r in rej if r["stage"] == "סינון מוקדם")
        header = build_header(now, label_hour, approved, len(to_check), len(rej) - n_pre, len(manual),
                              prefiltered=n_pre, waiting=len(state["queue"]), stats=stats)
        sent = send_digest(header, cards, None,
                           markup_for=lambda j: feedback.keyboard(feedback.short_id(j["key"]),
                                                                  j.get("apply_url") or j["url"], j["source"]))
        feedback.remember_sent(state, sent, today)
    else:
        log.info("No job passed all requirements - no alert sent")
    feedback.weekly_summary(state, now)

    # ---------- save ----------
    for k in done:
        seen[k] = today
        state.get("queue", {}).pop(k, None)
    if not force and slot:
        state["last_slot"] = slot
    log_rejections(rej)
    save_state(state)
    log.info("Done. Approved %d, manual %d, rejected %d, queued %d.",
             len(cards), len(manual), len(rej), len(state["queue"]))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log.exception("Run failed")
        sys.exit(1)

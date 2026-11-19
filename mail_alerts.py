"""Read job-alert emails (LinkedIn, Drushim) from Gmail and turn them into job leads.

LinkedIn often blocks direct searches from GitHub's servers, but it emails your job alerts to you
without any blocking. The bot reads those emails (read-only, without marking them as read).
Needs two GitHub secrets: GMAIL_ADDRESS and GMAIL_APP_PASSWORD. Without them this step is skipped.
"""
import email
import imaplib
import logging
import os
import re
from datetime import timedelta
from email.header import decode_header
from urllib.parse import unquote

log = logging.getLogger(__name__)

LI_RX = re.compile(r"linkedin\.com/(?:comm/)?jobs/view/(?:[^/?\s\"'<>]*?-)?(\d{8,})")
DR_RX = re.compile(r"drushim\.co\.il/job/(\d+)/([0-9a-fA-F]+)")


def _header(v):
    out = ""
    for part, enc in decode_header(v or ""):
        out += part.decode(enc or "utf-8", "replace") if isinstance(part, bytes) else part
    return out


def _bodies(msg):
    for part in msg.walk():
        if part.get_content_type() in ("text/html", "text/plain"):
            raw = part.get_payload(decode=True) or b""
            yield raw.decode(part.get_content_charset() or "utf-8", "replace")


def _titles_from_html(html, rx):
    """Map job id -> link text, from the email's HTML."""
    titles = {}
    for m in re.finditer(r"<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", html, re.S | re.I):
        href = unquote(unquote(m.group(1)))
        idm = rx.search(href)
        if not idm:
            continue
        text = re.sub(r"<[^>]+>", " ", m.group(2))
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > len(titles.get(idm.group(1), "")):
            titles[idm.group(1)] = text
    return titles


def collect_mail(cfg, now):
    mc = cfg.get("email_alerts") or {}
    address = os.environ.get("GMAIL_ADDRESS", "")
    password = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")
    if not mc.get("enabled", True) or not address or not password:
        log.info("Email alerts: not configured, skipping")
        return []
    since = (now - timedelta(days=int(mc.get("days_back", 2)))).strftime("%d-%b-%Y")
    jobs, seen = [], set()
    try:
        box = imaplib.IMAP4_SSL("imap.gmail.com")
        box.login(address, password)
        box.select("INBOX", readonly=True)
        for sender in mc.get("senders", ["linkedin.com", "drushim.co.il"]):
            typ, data = box.search(None, f'(SINCE "{since}" FROM "{sender}")')
            ids = data[0].split() if typ == "OK" and data and data[0] else []
            for mid in ids[-60:]:
                typ, msg_data = box.fetch(mid, "(BODY.PEEK[])")
                if typ != "OK" or not msg_data or not msg_data[0]:
                    continue
                msg = email.message_from_bytes(msg_data[0][1])
                for body in _bodies(msg):
                    text = unquote(unquote(body))
                    li_titles = _titles_from_html(body, LI_RX)
                    dr_titles = _titles_from_html(body, DR_RX)
                    for m in LI_RX.finditer(text):
                        jid = m.group(1)
                        if f"li{jid}" in seen:
                            continue
                        seen.add(f"li{jid}")
                        jobs.append({"key": f"linkedin:{jid}", "source": "LinkedIn", "source_id": jid,
                                     "title": li_titles.get(jid, ""), "company": "", "location": "",
                                     "posted": "", "url": f"https://www.linkedin.com/jobs/view/{jid}/",
                                     "via": "mail"})
                    for m in DR_RX.finditer(text):
                        jid = m.group(1)
                        if f"dr{jid}" in seen:
                            continue
                        seen.add(f"dr{jid}")
                        jobs.append({"key": f"דרושים:{jid}", "source": "דרושים", "source_id": jid,
                                     "title": dr_titles.get(jid, ""), "company": "", "location": "",
                                     "posted": "",
                                     "url": f"https://www.drushim.co.il/job/{jid}/{m.group(2)}/",
                                     "via": "mail"})
        box.logout()
    except Exception as e:  # noqa: BLE001
        log.warning("Email alerts: could not read Gmail (%s)", e)
        return jobs
    log.info("Email alerts: %d jobs (%d LinkedIn, %d Drushim)", len(jobs),
             sum(1 for j in jobs if j["source"] == "LinkedIn"), sum(1 for j in jobs if j["source"] == "דרושים"))
    return jobs

"""Send the digest to Telegram, formatted as clean cards with a button."""
import html
import logging
import os
import time

import requests

log = logging.getLogger(__name__)
UNKNOWN = ("", "לא צוין", None)


def _e(s):
    return html.escape(str(s or ""), quote=False)


def _icon(score):
    return "🟢" if score >= 8 else "🟡" if score >= 7 else "🟠"


def build_header(now, hour, approved, checked, rejected, manual, prefiltered=0, waiting=0, stats=None):
    title = "☀️ <b>משרות הבוקר</b>" if hour < 12 else "🌇 <b>משרות אחר הצהריים</b>"
    lines = [f"{title}  ·  {now:%d/%m}", "━━━━━━━━━━━━━━",
             f"✅ <b>{len(approved)}</b> משרות עברו את כל תנאי הסף"
             + (f"   ·   ⚠️ <b>{manual}</b> כדאי לבדוק" if manual else ""),
             f"<i>נבדקו לעומק {checked} · נפסלו בבדיקה {rejected}"
             + (f" · סוננו מראש {prefiltered}" if prefiltered else "")
             + (f" · ממתינות להרצה הבאה {waiting}" if waiting else "") + "</i>"]
    if stats:
        parts = [f"{_e(src)} {v['sent']}/{v['checked']}" for src, v in sorted(stats.items()) if v["checked"]]
        if parts:
            lines.append("<i>נשלחו/נבדקו לפי מקור: " + " · ".join(parts) + "</i>")
    return "\n".join(lines)


def format_job(j):
    s = j["score"]
    out = [f"{_icon(s)} <b>{_e(j['company'] or 'חברה לא צוינה')} · {_e(j['title'])}</b>"]
    if j.get("location") not in UNKNOWN:
        out.append(f"📍 {_e(j['location'])}")
    if j.get("posted") not in UNKNOWN:
        out.append(f"🕒 {_e(j['posted'])}")
    out.append(f"⭐ ציון התאמה: <b>{s:.1f}/10</b>")
    if j.get("check"):
        out.append(f"⚠️ <b>כדאי לבדוק:</b> {_e(j['check'])}")
    out.append("")
    if j.get("degree_quote"):
        out.append(f"🎓 <b>דרישת תואר:</b> <i>“{_e(j['degree_quote'])}”</i>")
    out.append(f"🧭 <b>ניסיון נדרש:</b> {_e(j.get('experience') or 'לא צוין')}")
    out.append(f"💡 <b>למה איתי מתאים:</b> {_e(j['why_fit'])}")
    if j.get("gaps"):
        out.append("⚠️ <b>פערים:</b> " + _e(" · ".join(j["gaps"][:5])))
    return "\n".join(out)[:4000]


def format_list(jobs):
    """Compact list of jobs that need a manual check (not approved recommendations)."""
    msgs, cur = [], "🔎 <b>לבדיקה ידנית</b> <i>(לא אושרו – ניסוח לא חד או מידע חסר)</i>\n"
    for j in jobs:
        sub = " · ".join(_e(x) for x in (j.get("company"), j["source"]) if x)
        item = (f'\n• <a href="{html.escape(j.get("apply_url") or j["url"])}">{_e(j.get("title") or "משרה")}</a>'
                f'\n<i>{sub} – {_e(j.get("reason") or "")}</i>\n')
        if len(cur) + len(item) > 3900:
            msgs.append(cur)
            cur = "🔎 <b>המשך</b>\n"
        cur += item
    msgs.append(cur)
    return msgs


def api(method, payload):
    """Calls a Telegram Bot API method and returns its result."""
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    for _ in range(3):
        r = requests.post(f"https://api.telegram.org/bot{token}/{method}", json=payload, timeout=30)
        if r.status_code == 200:
            return r.json().get("result")
        if r.status_code == 429:
            time.sleep(int(r.json().get("parameters", {}).get("retry_after", 5)) + 1)
            continue
        raise RuntimeError(f"Telegram {method} error {r.status_code}: {r.text[:300]}")
    raise RuntimeError(f"Telegram {method}: too many retries")


def send_text(text, markup=None):
    """Sends a message and returns its message_id."""
    body = {"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": text, "parse_mode": "HTML",
            "disable_web_page_preview": True}
    if markup:
        body["reply_markup"] = markup
    try:
        return api("sendMessage", body)["message_id"]
    except RuntimeError as e:
        if not markup or "400" not in str(e):
            raise
        # a link Telegram refuses inside a button: send the card without buttons instead
        body.pop("reply_markup")
        return api("sendMessage", body)["message_id"]


esc = _e


def send_digest(header, jobs, extra=None, markup_for=None):
    """Sends everything; returns [(job, message_id)] for the job cards.
    A single card that fails is skipped instead of stopping the whole digest."""
    send_text(header)
    sent = []
    for j in jobs:
        markup = markup_for(j) if markup_for else None
        try:
            sent.append((j, send_text(format_job(j), markup)))
        except RuntimeError as e:
            log.warning("Skipped one card (%s): %s", j.get("title"), e)
        time.sleep(1.1)
    if extra:
        for m in format_list(extra):
            send_text(m)
            time.sleep(1.1)
    return sent

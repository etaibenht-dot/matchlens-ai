"""Keyword-based scoring, used when Gemini is unavailable (no AI needed)."""
import re

NUM_YEARS = re.compile(r"(\d{1,2})\s*\+?\s*(?:[-–]\s*(\d{1,2})\s*)?(?:שנות|שנים|שנה|years?|yrs)", re.I)
ANY_DEGREE = ("תואר", "אקדמ", "b.sc", "bsc", "b.a.", "b.a ", "ba ", "bachelor", "degree", "השכלה גבוהה")
IS_WORDS = ("מערכות מידע", "information systems")
ENTRY_WORDS = ("junior", "entry level", "entry-level", "graduate", "no experience", "without experience",
               "training provided", "ג'וניור", "גוניור", "ג׳וניור", "ללא ניסיון", "בלי ניסיון", "אין צורך בניסיון",
               "בוגרי", "בוגר/ת", "בוגרים", "הכשרה מלאה", "מתחילים", "0-1", "0-2")
EXP_WORDS = ("ניסיון", "experience")
DEGREE_WORDS = ("תואר", "degree", "b.a", "bsc", "b.sc")
BAD_DEGREES = ("כלכלה", "חשבונאות", "ראיית חשבון", "רו\"ח", "משפטים", "economics", "accounting", "law", "cpa")
ALT_DEGREE = (" או ", "רלוונטי", "מערכות מידע", "תעשייה וניהול", "relevant", "equivalent", "information systems",
              "or similar", "related field")
REQ_HEADERS = ("דרישות", "requirements", "qualifications", "what you", "you have", "we're looking", "כישורים")
SALARY_WORDS = ("שכר", "₪", "ש\"ח", "nis", "salary")


def _has(text, words):
    t = (text or "").lower()
    return any(w.lower() in t for w in words)


def _lines(text):
    return [ln.strip(" •-*·\t") for ln in (text or "").splitlines() if ln.strip()]


def _years(lines):
    """Returns (minimum years asked, True if it asks for more than 2 years)."""
    lows, too_much = [], False
    for ln in lines:
        if not _has(ln, EXP_WORDS):
            continue
        for m in NUM_YEARS.finditer(ln):
            lo = int(m.group(1))
            hi = int(m.group(2)) if m.group(2) else lo
            if lo > 15:
                continue
            lows.append(lo)
            if lo >= 3 or (lo == 2 and hi > 2):
                too_much = True
    return (min(lows) if lows else None), too_much


def _bad_degree(lines):
    for ln in lines:
        if _has(ln, DEGREE_WORDS) and _has(ln, BAD_DEGREES) and not _has(ln, ALT_DEGREE):
            return True
    return False


def _requirements(lines):
    for i, ln in enumerate(lines):
        if _has(ln[:40], REQ_HEADERS):
            picked = [x for x in lines[i + 1:i + 8] if 8 < len(x) < 140 and not _has(x, SALARY_WORDS)][:4]
            if picked:
                return picked
    return []


def _salary(lines):
    for ln in lines:
        if _has(ln, SALARY_WORDS) and re.search(r"\d", ln) and len(ln) < 120:
            return re.sub(r"^(שכר|salary)\s*[:\-]\s*", "", ln, flags=re.I)
    return None


def basic_score(job, cfg):
    title = job.get("title", "")
    desc = job.get("description") or ""
    lines = _lines(desc)
    head = " ".join(lines[:15])
    reasons = []
    include, exclude_reason = True, ""

    score = 3
    if _has(title, cfg.get("target_title_words", [])):
        score += 4
        reasons.append("התפקיד ברשימת התפקידים שאתה מחפש")
    elif _has(head, cfg.get("target_title_words", [])):
        score += 1
    if _has(title + " " + head, cfg.get("priority_title_words", [])):
        score += 2
        reasons.append("מיועד לג'וניור / בוגרים")
    if _has(title + " " + head, cfg.get("bonus_words", [])):
        score += 1
        reasons.append("תחום מועדף (פיננסים / ספורט / פינטק)")

    years, too_much = _years(lines)
    if too_much:
        include, exclude_reason = False, "נדרשות יותר משנתיים ניסיון"
    elif years == 2:
        score -= 1
        reasons.append("דורש עד שנתיים ניסיון")
    if desc and not _has(desc, ANY_DEGREE):
        include, exclude_reason = False, "לא מבקשים תואר אקדמי"
    if _bad_degree(lines):
        include, exclude_reason = False, "דורש תואר בכלכלה / חשבונאות / משפטים"
    if _has(desc, IS_WORDS):
        score += 1
        reasons.append("מוזכר תואר במערכות מידע")
    if not desc:
        reasons.append("לא הצלחתי לקרוא את תיאור המשרה")

    return {
        **job,
        "title": title or "משרה",
        "company_about": "",
        "requirements": _requirements(lines),
        "location": job.get("location") or "לא צוין",
        "work_mode": "לא צוין",
        "salary": _salary(lines),
        "posted": job.get("posted") or "לא צוין",
        "seniority": {None: "לא צוין", 0: "ללא ניסיון / ג'וניור", 1: "עד שנה", 2: "עד שנתיים"}.get(years, "לא צוין"),
        "include": include,
        "exclude_reason": exclude_reason,
        "score": max(1, min(9, score)),
        "fit_reason": " · ".join(reasons) or "התאמה חלקית לפי מילות מפתח",
        "ai": False,
    }


def precheck(job):
    """Cheap certain rejections before spending AI quota. Returns a Hebrew reason, or None."""
    if job.get("closed"):
        return "המשרה סגורה להגשה"
    desc = job.get("description") or ""
    if not desc:
        return None  # unreadable: handled separately (retried, never sent unverified)
    lines = _lines(desc)
    # experience is checked automatically only on LinkedIn, whose text is clean. On Israeli sites the page
    # can still contain other ads, so there the AI reads the requirements and decides.
    if job.get("source") == "LinkedIn":
        years, too_much = _years(lines)
        if too_much:
            return "נדרשות יותר משנתיים ניסיון (זוהה אוטומטית)"
    # entry-level / junior / no-experience roles go to the AI even without a degree requirement;
    # a search-result summary is too short to judge the degree, so it also goes to the AI
    if not job.get("partial") and not _has(desc, ANY_DEGREE) and not _has(job.get("title", "") + " " + desc, ENTRY_WORDS):
        return "אין דרישה לתואר אקדמי במודעה (וגם לא משרת ג'וניור / ללא ניסיון)"
    return None

"""Stage B + C: verify every must-have requirement with Gemini, then score only jobs that pass."""
import logging

log = logging.getLogger(__name__)

INSTRUCTIONS = """You are a strict job-requirements verifier for one specific candidate.
Today's date is {today}. Read the CANDIDATE PROFILE (the only source of truth about him), then check EVERY job.

Work in this order for each job:
1. Extract ALL must-have requirements and ALL nice-to-have requirements from the FULL posting text.
2. Compare each requirement to the profile. Academic knowledge is NOT professional experience.
3. Decide the verdict: "pass", "reject" or "manual".

REJECT if ANY of these is true:
- Requires MORE than 2 years of relevant professional experience (e.g. "2-3 years", "3+ years").
- Requires proven / commercial / hands-on professional experience, or expert / advanced proficiency, in a tool he
  knows only academically (SQL, Python, SAP, Priority, ERP/CRM, Power BI, Tableau, etc.).
- Requires previous experience in a specific role he never had (e.g. a year as a marketing analyst, dedicated
  banking experience, ERP development experience).
- Requires a master's degree, or a MANDATORY bachelor's degree in a closed field that does not include Information
  Systems or a relevant field (e.g. only Economics / Accounting / Law / a specific engineering).
- The posting does not mention an academic degree at all. (A bachelor's degree that is required OR only
  "an advantage" / "preferred" is fine. Items listed under "requirements" without the word "advantage" are must-haves.)
- Titled junior, but the actual requirements are those of an experienced employee.
- Mainly administrative, without meaningful work with data, systems or technological processes.
- Not full-time; located outside central Israel and not fully remote.
- The posting says it is closed / no longer accepting applications.
- The posting date is more than 21 days before today.

ENTRY-LEVEL RULE (overrides the degree rule above):
If the posting is explicitly entry-level / junior / for graduates / "no experience required" / "ללא ניסיון" /
"ג'וניור" / "training provided", and the role is even loosely related to what he studied (information systems,
data, systems, business processes, ERP/CRM, QA, operations, finance, technology) or to his career targets,
give verdict "pass" even if no degree is mentioned. Score such roles at least 6.0 (higher the closer they are to
his targets). Still reject them for: wrong location, not full-time, more than 2 years required, or a role that is
clearly unrelated (driver, warehouse, sales rep, cook, cleaner, call-center telemarketing, pure clerical work).

PARTIAL TEXT RULE: if the text starts with "[PARTIAL", only the search-result summary was readable.
Never reject such a job for missing information (e.g. degree not mentioned). Reject it only for a reason that
is clearly visible (e.g. "3-4 שנים", wrong city, unrelated role). Otherwise give "manual" with a score, and
reason "הדרישות המלאות לא נקראו".

How to read tool requirements:
- "Basic knowledge", "familiarity", "academic knowledge", "willingness to learn", "training provided" -> fits him.
- "Advantage", "preferred", "nice to have" -> never a reason to reject (list it under gaps if he lacks it).
- "Hands-on professional experience required", "proven experience", "expert", "advanced proficiency" -> reject
  unless the profile shows that level.
Do NOT reject just because SQL, Python, ERP or BI is mentioned.

Use "manual" (never guess) when: the wording is ambiguous; the full requirements cannot be read from the text; the
degree must be from a "leading university" specifically; or you cannot tell whether the job is still open.

Score jobs with verdict "pass" AND "manual" (one decimal; for "manual" score as if the unclear point is fine):
- 9.0-10: meets all must-haves, and the role strongly matches his real experience and career targets.
- 8.0-8.9: meets all must-haves, small gaps in nice-to-haves only.
- 7.0-7.9: meets all must-haves, but the professional fit is partial.
- 6.0-6.9: meets all must-haves, but the fit is limited (e.g. degree only an advantage, or a stretch role).
- below 6.0: weak fit (it will not be sent).
Never give a high score just because the title says Data Analyst / ERP / Finance / Information Systems.

Return for each job an object with:
- "id": exactly as given
- "verdict": "pass" | "reject" | "manual"
- "reason": short Hebrew reason for reject/manual (the exact failed requirement), "" for pass
- "score": number with one decimal for pass and manual, null for reject
- "title": the real job title (original language)
- "company": company name or ""
- "location": city / area in Hebrew, or "לא צוין"
- "posted": posting date as written in the text, or null
- "degree_quote": the EXACT degree requirement sentence quoted from the posting (original language), or null
- "experience": Hebrew: required years + the specific experience, e.g. "0-2 שנים בניתוח נתונים", or "לא נדרש ניסיון"
- "why_fit": 2-3 Hebrew sentences based ONLY on his real experience and education (for pass and manual), else ""
- "gaps": list of short Hebrew strings: ONLY nice-to-have requirements he lacks (empty list if none)

Respond ONLY as JSON: {{"results": [ ... ]}} with one object per job.
"""


def build_prompt(profile, jobs, today):
    blocks = []
    for j in jobs:
        blocks.append(
            f"### JOB id={j['key']}\n"
            f"Source: {j['source']}\n"
            f"Listing title: {j.get('title', '')}\n"
            f"Listing company: {j.get('company', '')}\n"
            f"Listing location: {j.get('location', '')}\n"
            f"Listing posted: {j.get('posted', '')}\n"
            f"Full posting text:\n{(j.get('description') or '(no text)')[:5000]}\n"
        )
    return (INSTRUCTIONS.format(today=today) + "\n\n=== CANDIDATE PROFILE ===\n" + profile
            + "\n\n=== JOBS ===\n" + "\n".join(blocks))


def _num(x):
    try:
        return round(float(x), 1)
    except (TypeError, ValueError):
        return None


def verify_jobs(gemini, profile, jobs, today, batch_size=6):
    """Returns (results, verified_keys). Jobs in failed batches are not verified (retried next run)."""
    results, verified = [], set()
    for i in range(0, len(jobs), batch_size):
        batch = jobs[i:i + batch_size]
        try:
            data = gemini.json(build_prompt(profile, batch, today))
        except Exception as e:  # noqa: BLE001
            log.warning("Verification batch failed, will retry next run: %s", e)
            continue
        by_id = {str(r.get("id")): r for r in data.get("results", []) if isinstance(r, dict)}
        for j in batch:
            r = by_id.get(j["key"])
            if not r:
                continue
            verdict = str(r.get("verdict", "")).lower()
            if verdict not in ("pass", "reject", "manual"):
                verdict = "manual"
            verified.add(j["key"])
            results.append({
                **j,
                "verdict": verdict,
                "reason": r.get("reason") or "",
                "score": _num(r.get("score")) if verdict in ("pass", "manual") else None,
                "title": r.get("title") or j.get("title") or "",
                "company": r.get("company") or j.get("company") or "",
                "location": r.get("location") or j.get("location") or "לא צוין",
                "posted": j.get("posted") or r.get("posted") or "לא צוין",
                "degree_quote": r.get("degree_quote"),
                "experience": r.get("experience") or "לא צוין",
                "why_fit": r.get("why_fit") or "",
                "gaps": r.get("gaps") or [],
            })
        log.info("Verified %d/%d", len(verified), len(jobs))
    return results, verified

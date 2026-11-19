import argparse
import json
import os
import sys
from datetime import date, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "https://v3.football.api-sports.io"
LEAGUES = [
    {"label": "Premier League", "country": "England", "api_names": {"Premier League"}},
    {"label": "La Liga", "country": "Spain", "api_names": {"La Liga"}},
    {"label": "Serie A", "country": "Italy", "api_names": {"Serie A"}},
    {"label": "Bundesliga", "country": "Germany", "api_names": {"Bundesliga"}},
    {"label": "Ligue 1", "country": "France", "api_names": {"Ligue 1"}},
    {"label": "Israeli Premier League", "country": "Israel", "api_names": {"Ligat Ha'al", "Ligat Al", "Premier League"}},
]


def api_get(path, params):
    key = os.environ.get("API_FOOTBALL_KEY")
    if not key:
        raise RuntimeError("API_FOOTBALL_KEY is unavailable")
    request = Request(
        f"{BASE_URL}{path}?{urlencode(params)}",
        headers={"x-apisports-key": key, "Accept": "application/json", "User-Agent": "MatchLens-AI/1.0"},
    )
    with urlopen(request, timeout=45) as response:
        payload = json.load(response)
    if payload.get("errors"):
        raise RuntimeError(f"API error: {payload['errors']}")
    return payload.get("response", []), payload.get("paging", {}), payload.get("results", 0)


def current_league(config):
    rows, _, _ = api_get("/leagues", {"country": config["country"], "current": "true"})
    matches = [row for row in rows if row.get("league", {}).get("name") in config["api_names"]]
    if not matches:
        return None
    row = matches[0]
    current = [s for s in row.get("seasons", []) if s.get("current")]
    if not current:
        return None
    return {
        "league_id": row["league"]["id"],
        "league_name": row["league"]["name"],
        "season": current[0]["year"],
        "coverage": current[0].get("coverage", {}),
    }


def fixture_candidates(league, from_date, to_date):
    rows, _, _ = api_get("/fixtures", {
        "league": league["league_id"], "season": league["season"],
        "from": from_date, "to": to_date, "status": "FT-AET-PEN",
    })
    return rows


def basic_score(fixture):
    goals = fixture.get("goals", {})
    home = goals.get("home") or 0
    away = goals.get("away") or 0
    total = home + away
    margin = abs(home - away)
    draw_bonus = 5 if home == away and total >= 4 else 0
    return total * 6 + margin * 3 + draw_bonus


def stats_for_fixture(fixture_id):
    rows, _, _ = api_get("/fixtures/statistics", {"fixture": fixture_id})
    parsed = {}
    for team_row in rows:
        team_name = team_row.get("team", {}).get("name")
        stats = {item.get("type"): item.get("value") for item in team_row.get("statistics", [])}
        parsed[team_name] = stats
    return parsed


def number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace("%", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def interest_score(fixture, stats):
    teams = fixture["teams"]
    home_name, away_name = teams["home"]["name"], teams["away"]["name"]
    goals = fixture["goals"]
    home_goals, away_goals = goals.get("home") or 0, goals.get("away") or 0
    h, a = stats.get(home_name, {}), stats.get(away_name, {})
    hg, ag = home_goals, away_goals
    winner_home = hg > ag
    winner_away = ag > hg
    score = basic_score(fixture)

    for metric, weight in [("Total Shots", 0.8), ("Shots on Goal", 1.4), ("Ball Possession", 0.25)]:
        hv, av = number(h.get(metric)), number(a.get(metric))
        if hv is None or av is None:
            continue
        if winner_home and hv < av:
            score += min(abs(hv-av) * weight, 12)
        elif winner_away and av < hv:
            score += min(abs(hv-av) * weight, 12)

    required = ["Total Shots", "Shots on Goal", "Ball Possession"]
    completeness = sum(1 for m in required if number(h.get(m)) is not None and number(a.get(m)) is not None)
    score += completeness * 5
    return round(score, 2), completeness


def main():
    parser = argparse.ArgumentParser(description="Dry-run weekly MatchLens selection")
    parser.add_argument("--from-date")
    parser.add_argument("--to-date")
    args = parser.parse_args()

    today = date.today()
    last_sunday = today - timedelta(days=(today.weekday() + 1) % 7)
    last_saturday = last_sunday - timedelta(days=1)
    from_date = args.from_date or last_saturday.isoformat()
    to_date = args.to_date or last_sunday.isoformat()

    print(f"MATCHLENS WEEKLY DRY RUN: {from_date} to {to_date}")
    print("No files will be changed and no commits will be created.\n")
    report = []
    requests_used = 0

    try:
        for config in LEAGUES:
            league = current_league(config)
            requests_used += 1
            if not league:
                report.append({"competition": config["label"], "status": "league_not_available"})
                continue

            fixtures = fixture_candidates(league, from_date, to_date)
            requests_used += 1
            if not fixtures:
                report.append({"competition": config["label"], "status": "no_completed_fixtures"})
                continue

            shortlist = sorted(fixtures, key=basic_score, reverse=True)[:3]
            ranked = []
            for fixture in shortlist:
                fixture_id = fixture["fixture"]["id"]
                stats = stats_for_fixture(fixture_id)
                requests_used += 1
                score, completeness = interest_score(fixture, stats)
                ranked.append((score, completeness, fixture))

            ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
            score, completeness, chosen = ranked[0]
            report.append({
                "competition": config["label"],
                "api_league": league["league_name"],
                "league_id": league["league_id"],
                "season": league["season"],
                "status": "selected",
                "fixture_id": chosen["fixture"]["id"],
                "date": chosen["fixture"]["date"][:10],
                "home": chosen["teams"]["home"]["name"],
                "away": chosen["teams"]["away"]["name"],
                "score": f"{chosen['goals'].get('home')}-{chosen['goals'].get('away')}",
                "interest_score": score,
                "core_stats_complete": completeness,
                "shortlisted_fixtures": len(shortlist),
            })
    except (HTTPError, URLError, RuntimeError) as exc:
        print(f"Dry run failed: {exc}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nEstimated API requests used by this dry run: {requests_used}")
    if requests_used > 90:
        print("Safety warning: request count exceeded 90", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()

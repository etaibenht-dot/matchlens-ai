import json
import os
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE_URL = "https://v3.football.api-sports.io"


def api_get(path, params):
    api_key = os.environ.get("API_FOOTBALL_KEY")
    if not api_key:
        raise RuntimeError("API_FOOTBALL_KEY is not configured")

    url = f"{BASE_URL}{path}?{urlencode(params)}"
    request = Request(
        url,
        headers={
            "x-apisports-key": api_key,
            "Accept": "application/json",
            "User-Agent": "MatchLens-AI/1.0",
        },
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def main():
    try:
        payload = api_get("/leagues", {"country": "Israel", "current": "true"})
    except HTTPError as exc:
        print(f"API request failed with HTTP {exc.code}", file=sys.stderr)
        sys.exit(1)
    except URLError as exc:
        print(f"Network error: {exc.reason}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    errors = payload.get("errors") or {}
    if errors:
        print(f"API returned errors: {errors}", file=sys.stderr)
        sys.exit(1)

    results = []
    for item in payload.get("response", []):
        league = item.get("league", {})
        country = item.get("country", {})
        seasons = item.get("seasons", [])
        current_seasons = [s for s in seasons if s.get("current")]
        results.append(
            {
                "league_id": league.get("id"),
                "league_name": league.get("name"),
                "country": country.get("name"),
                "current_seasons": [s.get("year") for s in current_seasons],
                "coverage": [s.get("coverage") for s in current_seasons],
            }
        )

    target = [
        row for row in results
        if str(row.get("league_name", "")).lower() in {"ligat ha'al", "ligat al", "premier league"}
    ]

    print("API connection succeeded.")
    print(f"Israel competitions returned: {len(results)}")
    print("Relevant current competitions:")
    print(json.dumps(target or results, ensure_ascii=False, indent=2))

    if not target:
        print("Ligat Ha'al was not found among current Israel competitions.", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()

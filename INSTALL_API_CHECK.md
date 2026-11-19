# API-Football connection check

Copy:

- `src/check_api_football.py` to `matchlens-ai/src/`
- `.github/workflows/check-api-football.yml` to `matchlens-ai/.github/workflows/`

Then commit and push. In GitHub, open **Actions**, select **Check API-Football connection**, and click **Run workflow**.

The workflow reads `API_FOOTBALL_KEY` from GitHub Actions secrets. The key is never printed.

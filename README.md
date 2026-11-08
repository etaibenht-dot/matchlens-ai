# MatchLens AI

Football analytics portfolio project built from 20 iconic matches. The project converts an editable Excel research tracker into validated analytical tables, DuckDB storage, explainable KPIs, similarity analysis, and a Streamlit application.

## What this demonstrates
- Data collection and source lineage
- Python ETL with Pandas
- SQL analytics with DuckDB
- Automated quality checks
- Feature engineering
- Nearest-neighbor similarity analysis
- Interactive Streamlit reporting

## Quick start
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
python -m src.pipeline
pytest -q
streamlit run app/Home.py
```

## Data flow
`Excel research tracker -> CSV snapshots -> validation -> DuckDB -> features -> Streamlit`

## Important methodology notes
- Missing data remains NULL, never zero.
- xG values retain provider identity and retrospective models are not treated as official contemporary values.
- Control Score and Attacking Efficiency are transparent project indices, not FIFA or UEFA metrics.
- Similar matches describe statistical proximity and are not predictions.

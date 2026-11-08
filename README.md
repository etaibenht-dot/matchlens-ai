# MatchLens AI

[![Live App](https://img.shields.io/badge/Live_App-Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://matchlens-ai.streamlit.app)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/Tests-6_Passing-2EA44F)](#testing)

**MatchLens AI** is an explainable football analytics application built as a Data Analyst portfolio project. It transforms source-backed match statistics into interactive comparisons, transparent performance metrics, data-driven narratives, and statistically similar-match recommendations.

## Live application

**Open MatchLens AI:** https://matchlens-ai.streamlit.app

## Project objective

The project answers three post-match questions:

1. Which team controlled more of the match?
2. Which team created more attacking volume or finished more efficiently?
3. Which historical matches have the most similar statistical profile?

The current archive contains **20 iconic football matches** from club and international competitions, including the UEFA Champions League, FIFA World Cup, UEFA European Championship, La Liga, the Spanish Super Cup, and the Israeli Premier League.

## Main features

- Select and analyze any match in the archive
- Separate team panels for clear side-by-side analysis
- Full match date and final score
- Shots, shots on target, possession, pass accuracy, corners, and xG when available
- Shot accuracy and shot conversion calculations
- Transparent **Control Score** based on possession, pass share, and pass accuracy
- Automated data-driven match narrative
- Similar-match analysis using `StandardScaler` and `NearestNeighbors`
- Explanation of the metrics that make two matches statistically similar
- Data provenance, missing-data messaging, and provider-specific xG notes
- Dedicated page for comparing two matches

## Technology stack

| Layer | Technology |
|---|---|
| Data collection and research | Excel, public football data sources |
| ETL and transformation | Python, Pandas, OpenPyXL |
| Analytical storage | DuckDB, Parquet |
| Machine learning | scikit-learn |
| Visualization | Plotly |
| Web application | Streamlit |
| Testing | pytest |
| Version control and deployment | GitHub, Streamlit Community Cloud |

## Data pipeline

```text
Editable Excel research tracker
            ↓
Python ingestion and validation
            ↓
Team-level transformation and KPI calculation
            ↓
Parquet analytical datasets + DuckDB
            ↓
Feature engineering and similarity model
            ↓
Streamlit application
```

## Analytical methodology

### Shot accuracy

```text
Shots on target / Total shots
```

### Shot conversion

```text
Goals / Total shots
```

### Control Score

```text
40% Ball possession
35% Pass share
25% Pass accuracy
```

The Control Score is a transparent project index. It is not an official FIFA or UEFA metric and is not presented as a probability.

### Similar-match analysis

Each match is represented through differences between the two teams, including:

- Possession difference
- Shot difference
- Shots-on-target difference
- Passing-volume difference
- Pass-accuracy difference
- Corner difference
- Shot-accuracy difference
- Shot-conversion difference
- Control Score difference

Missing feature values are imputed with the dataset median. Features are normalized with `StandardScaler`, and `NearestNeighbors` retrieves the closest statistical profiles. The displayed distance is not a win probability or similarity percentage.

## Data-quality principles

- Missing information remains missing and is never converted to zero.
- The application displays **No data** when a reliable public statistic was not found.
- Retrospective xG values remain labelled by provider.
- xG values from different providers are not treated as directly interchangeable.
- Automated validation checks that shots on target do not exceed total shots and that pass accuracy remains within 0% to 100%.
- Source and coverage limitations are shown to the viewer.

## Repository structure

```text
matchlens-ai/
├── app/
│   ├── Home.py
│   └── pages/
│       └── 1_Compare.py
├── data/
│   ├── input/
│   ├── processed/
│   └── db/
├── src/
│   ├── config.py
│   ├── ingest.py
│   ├── validate.py
│   ├── transform.py
│   ├── metrics.py
│   ├── narrative.py
│   ├── similarity.py
│   ├── database.py
│   └── pipeline.py
├── sql/
├── tests/
├── requirements.txt
└── README.md
```

## Run locally

### 1. Clone the repository

```bash
git clone https://github.com/etaibenht-dot/matchlens-ai.git
cd matchlens-ai
```

### 2. Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

macOS or Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Run automated tests

```bash
python -m pytest -q
```

Expected result:

```text
6 passed
```

### 5. Build the analytical datasets

```bash
python -m src.pipeline
```

Expected result:

```text
Loaded 20 matches; quality issues: 0
```

### 6. Launch the application

```bash
python -m streamlit run app/Home.py
```

## Testing

The current test suite covers:

- Shot-accuracy calculation
- Safe handling of zero attempts
- Completed-pass calculation
- Missing values represented as `None`
- Missing values represented as `NaN`
- Detection of impossible shots-on-target values

## Current limitations

- The archive contains 20 curated matches, so similarity analysis is exploratory.
- Data availability varies between modern and historical matches.
- Some historical xG values are retrospective reconstructions.
- The current model analyzes completed matches and does not predict future results.
- Metrics from different providers may use different definitions.

## Planned development

- Add one current match from each of Europe’s five major leagues and the Israeli Premier League
- Expand source-level metric auditing
- Normalize comparisons by competition and season
- Add richer tactical and event-level visualizations
- Improve similarity explanations and model evaluation
- Add downloadable match-analysis reports

## Portfolio summary

This project demonstrates an end-to-end analytics workflow:

```text
Data sourcing → Data quality → ETL → SQL storage → Feature engineering
→ Machine learning → Explainable analytics → Interactive deployment
```

## Author

**Itai Ben Hetz**

- GitHub: https://github.com/etaibenht-dot
- Live app: https://matchlens-ai.streamlit.app

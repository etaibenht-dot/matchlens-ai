import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from src.config import PROCESSED_DIR
from src.narrative import build_match_narrative, similarity_reasons
from src.similarity import fit_similarity, similar_matches

st.set_page_config(page_title="MatchLens AI", page_icon="⚽", layout="wide")
st.markdown("""
<style>
.block-container{padding-top:1.4rem;padding-bottom:3rem;max-width:1250px}
[data-testid="stMetric"]{background:#f6f8fb;border:1px solid #e4e9f0;padding:14px;border-radius:12px}
.hero{padding:20px 24px;border-radius:16px;background:linear-gradient(120deg,#0b1f3a,#164f73);color:white;margin-bottom:18px}
.small-note{color:#65758b;font-size:.9rem}
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    return (
        pd.read_parquet(PROCESSED_DIR / "match_team_metrics.parquet"),
        pd.read_parquet(PROCESSED_DIR / "match_features.parquet"),
    )

team, features = load_data()
match_id = st.selectbox(
    "Select match",
    features.match_id.tolist(),
    format_func=lambda x: features.loc[features.match_id == x, "match"].iloc[0],
)
selected = team[team.match_id == match_id]
home = selected[selected.side == "home"].iloc[0]
away = selected[selected.side == "away"].iloc[0]

st.markdown(f"""<div class="hero"><div style="font-size:14px;opacity:.8">MATCHLENS AI • POST-MATCH ANALYSIS</div>
<div style="font-size:32px;font-weight:700;margin-top:4px">{home.team} {int(home.goals)} – {int(away.goals)} {away.team}</div>
<div style="opacity:.85;margin-top:5px">Explainable analytics from source-backed match data</div></div>""", unsafe_allow_html=True)


def team_panel(column, row, color, side_label):
    with column:
        st.markdown(
            f"""<div style="border:2px solid {color};border-radius:16px;padding:16px 18px 8px;margin-bottom:10px;">
            <div style="font-size:12px;font-weight:700;color:{color};letter-spacing:.08em">{side_label}</div>
            <div style="font-size:28px;font-weight:750;margin:2px 0 14px">{row.team}</div>
            </div>""",
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            a, b, c = st.columns(3)
            a.metric("Goals", int(row.goals))
            b.metric("Shots", int(row.shots) if pd.notna(row.shots) else "N/A")
            c.metric("On target", int(row.shots_on_target) if pd.notna(row.shots_on_target) else "N/A")
            st.divider()
            a, b, c = st.columns(3)
            a.metric("Shot accuracy", f"{row.shot_accuracy:.1%}" if pd.notna(row.shot_accuracy) else "N/A")
            b.metric("Conversion", f"{row.shot_conversion:.1%}" if pd.notna(row.shot_conversion) else "N/A")
            c.metric("Control score", f"{row.control_score:.1f}" if pd.notna(row.control_score) else "N/A")
            st.caption(
                "Possession: " + (f"{row.possession:.1f}%" if pd.notna(row.possession) else "N/A")
                + "  |  Pass accuracy: " + (f"{row.pass_accuracy:.1f}%" if pd.notna(row.pass_accuracy) else "N/A")
                + "  |  xG: " + (f"{row.xg:.2f}" if pd.notna(row.xg) else "N/A")
            )

left, right = st.columns(2, gap="large")
team_panel(left, home, "#1f77b4", "HOME / FIRST-LISTED TEAM")
team_panel(right, away, "#ff7f0e", "AWAY / SECOND-LISTED TEAM")

st.subheader("Match comparison")
metric_map = {
    "Possession": (home.possession, away.possession),
    "Shots": (home.shots, away.shots),
    "Shots on target": (home.shots_on_target, away.shots_on_target),
    "Pass accuracy": (home.pass_accuracy, away.pass_accuracy),
    "Corners": (home.corners, away.corners),
    "xG": (home.xg, away.xg),
}
available = {k:v for k,v in metric_map.items() if pd.notna(v[0]) and pd.notna(v[1])}
fig = go.Figure()
fig.add_bar(name=home.team, x=list(available), y=[v[0] for v in available.values()], marker_color="#1f77b4")
fig.add_bar(name=away.team, x=list(available), y=[v[1] for v in available.values()], marker_color="#ff7f0e")
fig.update_layout(barmode="group", height=420, margin=dict(l=10,r=10,t=30,b=10), legend_orientation="h")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Data-driven match story")
st.info(build_match_narrative(home, away))
st.caption("Control Score is a transparent project index based on possession, pass share and pass accuracy. xG remains provider-specific.")

st.subheader("Similar matches")
pipe, model, X, feature_cols = fit_similarity(features)
similar = similar_matches(match_id, features, model, X)
selected_feature = features[features.match_id == match_id].iloc[0]
rows=[]
for _, candidate in similar.iterrows():
    candidate_feature = features[features.match_id == candidate.match_id].iloc[0]
    rows.append({
        "Match": candidate["match"],
        "Distance": round(candidate["distance"], 3),
        "Why similar": similarity_reasons(selected_feature, candidate_feature, feature_cols),
    })
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
st.markdown('<div class="small-note">Lower distance means greater statistical similarity after median imputation and StandardScaler normalization. It is not a probability.</div>', unsafe_allow_html=True)

with st.expander("Data provenance and limitations"):
    st.write(f"Primary source label: **{home.source}**")
    st.write("Missing values remain NULL and are shown as N/A. Retrospective xG values must remain labelled by provider. Similarity results are exploratory because the archive currently contains 20 matches.")

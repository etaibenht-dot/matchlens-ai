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
    team = pd.read_parquet(PROCESSED_DIR / "match_team_metrics.parquet")
    features = pd.read_parquet(PROCESSED_DIR / "match_features.parquet")
    catalog = pd.read_csv(ROOT / "data" / "input" / "match_catalog.csv", parse_dates=["match_date"])
    verification = pd.read_csv(ROOT / "data" / "input" / "metric_verification.csv")
    return team, features.merge(catalog, on="match_id", how="left"), catalog, verification

team, features, catalog, verification = load_data()

st.title("MatchLens AI")
st.caption("Explainable football analytics across iconic and weekly matches")

filter_1, filter_2 = st.columns(2)
with filter_1:
    type_options = ["All matches"] + sorted(features["match_type"].dropna().unique().tolist())
    selected_type = st.selectbox("Match collection", type_options)

filtered = features.copy()
if selected_type != "All matches":
    filtered = filtered[filtered["match_type"] == selected_type]

with filter_2:
    competition_options = ["All competitions"] + sorted(filtered["competition"].dropna().unique().tolist())
    selected_competition = st.selectbox("Competition", competition_options)

if selected_competition != "All competitions":
    filtered = filtered[filtered["competition"] == selected_competition]

if filtered.empty:
    st.warning("No matches are available for the selected filters.")
    st.stop()

match_id = st.selectbox(
    "Select match",
    filtered.match_id.tolist(),
    format_func=lambda x: filtered.loc[filtered.match_id == x, "match"].iloc[0],
)
selected_feature = features[features.match_id == match_id].iloc[0]
selected = team[team.match_id == match_id]
verification_row = verification[verification.match_id == match_id].iloc[0]
home = selected[selected.side == "home"].iloc[0]
away = selected[selected.side == "away"].iloc[0]
formatted_date = pd.to_datetime(selected_feature.match_date).strftime("%d/%m/%Y")
batch_text = f" • {selected_feature['batch']}" if pd.notna(selected_feature.get("batch")) else ""

st.markdown(f"""<div class="hero">
<div style="font-size:14px;opacity:.82">{selected_feature.match_type.upper()} • {selected_feature.competition}{batch_text}</div>
<div style="font-size:32px;font-weight:700;margin-top:4px">{home.team} {int(home.goals)} – {int(away.goals)} {away.team}</div>
<div style="opacity:.9;margin-top:5px;font-size:17px">{formatted_date}</div>
</div>""", unsafe_allow_html=True)


def team_panel(column, row, color, side_label):
    with column:
        st.markdown(
            f"""<div style="border:2px solid {color};border-radius:16px;padding:16px 18px 8px;margin-bottom:10px;">
            <div style="font-size:12px;font-weight:700;color:{color};letter-spacing:.08em">{side_label}</div>
            <div style="font-size:28px;font-weight:750;margin:2px 0 14px">{row.team}</div>
            </div>""", unsafe_allow_html=True)
        with st.container(border=True):
            a, b, c = st.columns(3)
            a.metric("Goals", int(row.goals))
            b.metric("Shots", int(row.shots) if pd.notna(row.shots) else "No data")
            c.metric("On target", int(row.shots_on_target) if pd.notna(row.shots_on_target) else "No data")
            st.divider()
            a, b, c = st.columns(3)
            a.metric("Shot accuracy", f"{row.shot_accuracy:.1%}" if pd.notna(row.shot_accuracy) else "No data")
            b.metric("Conversion", f"{row.shot_conversion:.1%}" if pd.notna(row.shot_conversion) else "No data")
            display_mode = verification_row.display_mode
            if display_mode == "control_score" and pd.notna(row.control_score):
                control_label, control_value = "Control score", f"{row.control_score:.1f}"
            elif display_mode == "possession" and pd.notna(row.possession):
                control_label, control_value = "Possession", f"{row.possession:.1f}%"
            else:
                control_label, control_value = "Control", "Not calculated"
            c.metric(control_label, control_value)
            st.caption(
                "Possession: " + (f"{row.possession:.1f}%" if pd.notna(row.possession) and verification_row.possession_status == "Verified" else "Not verified")
                + "  |  Pass accuracy: " + (f"{row.pass_accuracy:.1f}%" if pd.notna(row.pass_accuracy) else "No data")
                + "  |  xG: " + (f"{row.xg:.2f}" if pd.notna(row.xg) else "No data")
            )
            if display_mode == "possession":
                st.caption("Full Control Score was not calculated because complete verified passing data was unavailable.")
            elif display_mode == "not_calculated":
                st.caption("Verified possession and passing inputs were not sufficient to calculate Control Score.")

left, right = st.columns(2, gap="large")
team_panel(left, home, "#1f77b4", "HOME / FIRST-LISTED TEAM")
team_panel(right, away, "#ff7f0e", "AWAY / SECOND-LISTED TEAM")

st.subheader("Match comparison")
metric_map = {
    "Possession": (home.possession, away.possession), "Shots": (home.shots, away.shots),
    "Shots on target": (home.shots_on_target, away.shots_on_target),
    "Pass accuracy": (home.pass_accuracy, away.pass_accuracy),
    "Corners": (home.corners, away.corners), "xG": (home.xg, away.xg),
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
_, model, X, feature_cols = fit_similarity(features)
similar = similar_matches(match_id, features, model, X)
rows=[]
for _, candidate in similar.iterrows():
    candidate_feature = features[features.match_id == candidate.match_id].iloc[0]
    rows.append({"Match": candidate["match"], "Distance": round(candidate["distance"], 3),
                 "Why similar": similarity_reasons(selected_feature, candidate_feature, feature_cols)})
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
st.markdown('<div class="small-note">Lower distance means greater statistical similarity after median imputation and StandardScaler normalization. It is not a probability.</div>', unsafe_allow_html=True)

with st.expander("Data provenance and limitations"):
    st.write(f"Primary source label: **{home.source}**")
    st.write(f"Control-data audit: **{verification_row.control_status}**")
    st.write(f"Verification source: **{verification_row.source_name}**")
    if pd.notna(verification_row.source_url) and verification_row.source_url:
        st.link_button("Open verification source", verification_row.source_url)
    st.write(verification_row.audit_note)
    displayed_fields = {"shots":[home.shots,away.shots],"shots on target":[home.shots_on_target,away.shots_on_target],
        "shot accuracy":[home.shot_accuracy,away.shot_accuracy],"shot conversion":[home.shot_conversion,away.shot_conversion],
        "Control Score":[home.control_score,away.control_score],"possession":[home.possession,away.possession],
        "pass accuracy":[home.pass_accuracy,away.pass_accuracy],"xG":[home.xg,away.xg]}
    missing_fields = [label for label, values in displayed_fields.items() if any(pd.isna(value) for value in values)]
    if missing_fields:
        st.warning("Some statistics are unavailable for this match: " + ", ".join(missing_fields)
                   + ". A reliable public figure was not found, so the app shows ‘No data’. This does not mean the value was zero.")
    if pd.notna(home.xg) or pd.notna(away.xg):
        st.write("xG values are provider-specific and may have been reconstructed after the match.")
    st.write(f"Similarity results are exploratory because the archive currently contains {len(features)} matches.")

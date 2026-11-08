import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from src.config import PROCESSED_DIR

st.set_page_config(page_title='Compare Matches',page_icon='📊',layout='wide')
team=pd.read_parquet(PROCESSED_DIR/'match_team_metrics.parquet')
features=pd.read_parquet(PROCESSED_DIR/'match_features.parquet')
st.title('Match comparison')
labels=dict(zip(features.match_id,features.match))
c1,c2=st.columns(2)
a=c1.selectbox('First match',features.match_id.tolist(),format_func=lambda x:labels[x],index=0)
b=c2.selectbox('Second match',features.match_id.tolist(),format_func=lambda x:labels[x],index=min(1,len(features)-1))
cols=[c for c in features.columns if c.endswith('_diff')]
fa=features[features.match_id==a].iloc[0]; fb=features[features.match_id==b].iloc[0]
chart=pd.DataFrame({'Metric':[c.replace('_diff','').replace('_',' ').title() for c in cols],labels[a]:[fa[c] for c in cols],labels[b]:[fb[c] for c in cols]}).dropna()
fig=go.Figure()
fig.add_bar(name=labels[a],x=chart.Metric,y=chart[labels[a]])
fig.add_bar(name=labels[b],x=chart.Metric,y=chart[labels[b]])
fig.update_layout(barmode='group',height=500,legend_orientation='h')
st.plotly_chart(fig,use_container_width=True)
st.caption('Positive values favor the designated home team; negative values favor the designated away team. Metrics use different units, so this view is descriptive rather than a combined score.')

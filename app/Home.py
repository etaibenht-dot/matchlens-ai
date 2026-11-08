import streamlit as st
import pandas as pd
from src.config import PROCESSED_DIR
from src.similarity import fit_similarity,similar_matches

st.set_page_config(page_title='MatchLens AI',layout='wide')
st.title('MatchLens AI')
st.caption('Explainable football match analytics')
team=pd.read_parquet(PROCESSED_DIR/'match_team_metrics.parquet')
features=pd.read_parquet(PROCESSED_DIR/'match_features.parquet')
match_id=st.selectbox('Select match',features.match_id,format_func=lambda x: features.loc[features.match_id==x,'match'].iloc[0])
selected=team[team.match_id==match_id]
cols=st.columns(2)
for col,(_,r) in zip(cols,selected.iterrows()):
    with col:
        st.subheader(r.team)
        st.metric('Goals',int(r.goals))
        st.metric('Shots',int(r.shots) if pd.notna(r.shots) else 'N/A')
        st.metric('Shot accuracy',f'{r.shot_accuracy:.1%}' if pd.notna(r.shot_accuracy) else 'N/A')
        st.metric('Control score',f'{r.control_score:.1f}' if pd.notna(r.control_score) else 'N/A')
st.subheader('Similar matches')
_,model,X,_=fit_similarity(features)
st.dataframe(similar_matches(match_id,features,model,X),use_container_width=True,hide_index=True)

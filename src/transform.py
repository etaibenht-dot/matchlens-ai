import pandas as pd
from .ingest import parse_goals
from .metrics import shot_accuracy,shot_conversion,on_target_conversion,completed_passes,control_score

def build_team_metrics(core):
    rows=[]
    for _,r in core.iterrows():
        hg,ag=parse_goals(r['score'])
        base={'match_id':int(r['match_id']),'score':r['score'],'source':r.get('primary_source')}
        for side,opp,goals in [('h','a',hg),('a','h',ag)]:
            team=r['home_team'] if side=='h' else r['away_team']
            opponent=r['away_team'] if side=='h' else r['home_team']
            shots=r.get(f'shots_{side}'); sot=r.get(f'on_target_{side}')
            passes=r.get(f'passes_{side}'); opp_passes=r.get(f'passes_{opp}')
            acc=r.get(f'pass_accuracy_{side}'); poss=r.get(f'possession_{side}')
            row={**base,'team':team,'opponent':opponent,'side':'home' if side=='h' else 'away','goals':goals,
                 'possession':poss,'shots':shots,'shots_on_target':sot,'passes':passes,'pass_accuracy':acc,
                 'corners':r.get(f'corners_{side}'),'fouls':r.get(f'fouls_{side}'),'yellow_cards':r.get(f'yellow_{side}'),
                 'red_cards':r.get(f'red_{side}'),'xg':r.get(f'xg_{side}')}
            row['shot_accuracy']=shot_accuracy(sot,shots)
            row['shot_conversion']=shot_conversion(goals,shots)
            row['on_target_conversion']=on_target_conversion(goals,sot)
            row['completed_passes']=completed_passes(passes,acc)
            row['control_score']=control_score(poss,passes,opp_passes,acc)
            rows.append(row)
    return pd.DataFrame(rows)

def build_match_features(team):
    h=team[team.side=='home'].set_index('match_id'); a=team[team.side=='away'].set_index('match_id')
    cols=['possession','shots','shots_on_target','passes','pass_accuracy','corners','shot_accuracy','shot_conversion','control_score']
    out=pd.DataFrame(index=h.index)
    for c in cols: out[f'{c}_diff']=h[c]-a[c]
    out['match']=h['team']+' vs '+a['team']
    return out.reset_index()

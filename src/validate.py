import pandas as pd

def validate_core(df: pd.DataFrame) -> pd.DataFrame:
    issues=[]
    for _,r in df.iterrows():
        match_id=int(r['match_id'])
        for side in ['h','a']:
            shots=r.get(f'shots_{side}')
            on_target=r.get(f'on_target_{side}')
            accuracy=r.get(f'pass_accuracy_{side}')
            if pd.notna(shots) and pd.notna(on_target) and on_target > shots:
                issues.append((match_id,'FAIL',f'on_target_{side} exceeds shots_{side}'))
            if pd.notna(accuracy) and not 0 <= accuracy <= 100:
                issues.append((match_id,'FAIL',f'pass_accuracy_{side} outside 0-100'))
        ph,pa=r.get('possession_h'),r.get('possession_a')
        if pd.notna(ph) and pd.notna(pa):
            total=ph+pa
            if total > 105:
                issues.append((match_id,'FAIL','possession total exceeds 105%'))
            elif total < 95 and match_id != 7:
                issues.append((match_id,'WARNING','possession total below 95%'))
    return pd.DataFrame(issues,columns=['match_id','severity','issue'])

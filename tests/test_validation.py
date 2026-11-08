import pandas as pd
from src.validate import validate_core

def test_detects_impossible_shots():
    df=pd.DataFrame([{'match_id':1,'shots_h':4,'shots_a':5,'on_target_h':6,'on_target_a':2,'pass_accuracy_h':80,'pass_accuracy_a':90,'possession_h':50,'possession_a':50}])
    issues=validate_core(df)
    assert 'FAIL' in set(issues.severity)

from src.metrics import shot_accuracy,shot_conversion,completed_passes,control_score

def test_shot_accuracy(): assert shot_accuracy(5,10)==0.5
def test_zero_shots_returns_none(): assert shot_conversion(0,0) is None
def test_completed_passes(): assert completed_passes(400,85)==340
def test_control_score_missing_returns_none(): assert control_score(None,400,300,85) is None

def test_completed_passes_with_nan_returns_none():
    assert completed_passes(float("nan"), 85) is None
    assert completed_passes(400, float("nan")) is None

import math


def is_missing(value):
    if value is None:
        return True
    try:
        return math.isnan(value)
    except TypeError:
        return False


def safe_divide(numerator, denominator):
    if is_missing(numerator) or is_missing(denominator) or denominator == 0:
        return None
    return numerator / denominator


def shot_accuracy(shots_on_target, shots):
    return safe_divide(shots_on_target, shots)


def shot_conversion(goals, shots):
    return safe_divide(goals, shots)


def on_target_conversion(goals, shots_on_target):
    return safe_divide(goals, shots_on_target)


def completed_passes(passes, pass_accuracy):
    if is_missing(passes) or is_missing(pass_accuracy):
        return None
    return round(passes * pass_accuracy / 100)


def control_score(possession, team_passes, opponent_passes, pass_accuracy):
    values = [possession, team_passes, opponent_passes, pass_accuracy]
    if any(is_missing(value) for value in values):
        return None
    total_passes = team_passes + opponent_passes
    if total_passes == 0:
        return None
    pass_share = team_passes / total_passes * 100
    return round(0.40 * possession + 0.35 * pass_share + 0.25 * pass_accuracy, 1)

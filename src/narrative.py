import pandas as pd


def _fmt(value, digits=1):
    return "N/A" if pd.isna(value) else f"{value:.{digits}f}"


def build_match_narrative(home, away):
    notes = []
    if pd.notna(home.shots) and pd.notna(away.shots):
        leader = home if home.shots >= away.shots else away
        gap = abs(home.shots - away.shots)
        notes.append(f"{leader.team} produced the higher shot volume, by {int(gap)} attempts.")
    if pd.notna(home.shot_conversion) and pd.notna(away.shot_conversion):
        leader = home if home.shot_conversion >= away.shot_conversion else away
        notes.append(f"{leader.team} was more efficient in finishing ({leader.shot_conversion:.1%} shot conversion).")
    if pd.notna(home.control_score) and pd.notna(away.control_score):
        leader = home if home.control_score >= away.control_score else away
        notes.append(f"{leader.team} recorded the stronger Control Score ({leader.control_score:.1f}).")
    if pd.notna(home.xg) and pd.notna(away.xg):
        leader = home if home.xg >= away.xg else away
        notes.append(f"{leader.team} led the provider-specific xG measure ({_fmt(leader.xg)}).")
    return " ".join(notes) if notes else "Not enough complete metrics are available for a reliable narrative."


def similarity_reasons(selected_feature, candidate_feature, feature_cols, limit=3):
    comparable=[]
    labels={
        'possession_diff':'possession balance','shots_diff':'shot balance',
        'shots_on_target_diff':'on-target balance','passes_diff':'passing-volume balance',
        'pass_accuracy_diff':'passing-accuracy balance','corners_diff':'corner balance',
        'shot_accuracy_diff':'shot-accuracy balance','shot_conversion_diff':'finishing-efficiency balance',
        'control_score_diff':'control-score balance'
    }
    for col in feature_cols:
        a=selected_feature.get(col); b=candidate_feature.get(col)
        if pd.notna(a) and pd.notna(b):
            comparable.append((abs(a-b), labels.get(col,col.replace('_',' '))))
    comparable.sort(key=lambda x:x[0])
    return ", ".join(label for _,label in comparable[:limit]) or "limited common metrics"

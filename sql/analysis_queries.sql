-- Matches where the winner had fewer shots
SELECT match_id, team, opponent, goals, shots
FROM match_team_metrics
ORDER BY match_id, side;

-- Highest shot conversion
SELECT match_id, team, shot_conversion
FROM match_team_metrics
WHERE shot_conversion IS NOT NULL
ORDER BY shot_conversion DESC;

from .ingest import read_tracker
from .transform import build_team_metrics,build_match_features
from .validate import validate_core
from .database import write_database
from .config import PROCESSED_DIR

def main():
    matches,core,sources=read_tracker()
    quality=validate_core(core)
    team=build_team_metrics(core)
    features=build_match_features(team)
    PROCESSED_DIR.mkdir(parents=True,exist_ok=True)
    team.to_parquet(PROCESSED_DIR/'match_team_metrics.parquet',index=False)
    features.to_parquet(PROCESSED_DIR/'match_features.parquet',index=False)
    quality.to_csv(PROCESSED_DIR/'quality_issues.csv',index=False)
    write_database(matches,core,sources,team,features,quality)
    print(
    f"Loaded {len(core)} matches; "
    f"created {len(team)} team records; "
    f"quality issues: {len(quality)}"
)
if __name__=='__main__': main()

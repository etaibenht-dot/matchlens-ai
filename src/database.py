import duckdb
from .config import DB_PATH

def write_database(matches,core,sources,team_metrics,features,quality):
    DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    with duckdb.connect(str(DB_PATH)) as con:
        for name,df in {'matches':matches,'core_match_data':core,'sources':sources,'match_team_metrics':team_metrics,'match_features':features,'quality_issues':quality}.items():
            con.register('frame',df)
            con.execute(f'CREATE OR REPLACE TABLE {name} AS SELECT * FROM frame')
            con.unregister('frame')

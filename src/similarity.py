from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors

def fit_similarity(features):
    feature_cols=[c for c in features.columns if c.endswith('_diff')]
    pipe=Pipeline([('imputer',SimpleImputer(strategy='median')),('scaler',StandardScaler())])
    X=pipe.fit_transform(features[feature_cols])
    model=NearestNeighbors(n_neighbors=min(4,len(features)),metric='euclidean').fit(X)
    return pipe,model,X,feature_cols

def similar_matches(match_id,features,model,X):
    idx=features.index[features.match_id==match_id][0]
    distances,indices=model.kneighbors(X[idx:idx+1])
    result=features.iloc[indices[0]][['match_id','match']].copy()
    result['distance']=distances[0]
    return result[result.match_id!=match_id].reset_index(drop=True)

import re
import pandas as pd
from .config import EXCEL_PATH

def snake(name):
    name=re.sub(r'[^A-Za-z0-9]+','_',str(name).strip()).strip('_').lower()
    return name

def read_tracker():
    matches=pd.read_excel(EXCEL_PATH,sheet_name='Match Registry',engine='openpyxl')
    core=pd.read_excel(EXCEL_PATH,sheet_name='Core Match Data',engine='openpyxl')
    sources=pd.read_excel(EXCEL_PATH,sheet_name='Source Audit',engine='openpyxl')
    for df in [matches,core,sources]: df.columns=[snake(c) for c in df.columns]
    return matches,core,sources

def parse_goals(score):
    if pd.isna(score): return (None,None)
    parts=str(score).split('-')
    return (int(parts[0]),int(parts[1])) if len(parts)==2 else (None,None)

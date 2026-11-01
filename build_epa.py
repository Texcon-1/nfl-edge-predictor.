"""Build compact, date-safe, team-by-game offensive EPA summaries from nflverse PBP.
Requires: requests pandas pyarrow. Executed by GitHub Actions, not on an iPhone.
"""
import io, csv, datetime as dt, pathlib, requests, pandas as pd
YEARS=range(2022,dt.datetime.now(dt.timezone.utc).year+1)
OUT=pathlib.Path('epa_team_games.csv')
cols=['game_id','posteam','epa','play_type','season_type']
frames=[]
for year in YEARS:
 url=f'https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{year}.parquet'
 try:
  response=requests.get(url,timeout=180,headers={'User-Agent':'NFL-Edge-Predictor/17'})
  response.raise_for_status()
  df=pd.read_parquet(io.BytesIO(response.content),columns=cols)
  df=df[df['season_type'].eq('REG') & df['play_type'].isin(['pass','run']) & df['posteam'].notna() & df['epa'].notna()].copy()
  df['epa']=pd.to_numeric(df['epa'],errors='coerce')
  df=df.dropna(subset=['epa'])
  df['season']=year
  frames.append(df)
  print(year,len(df))
 except Exception as e:
  print('Failed',year,str(e))
if not frames:
 raise RuntimeError('No PBP seasons could be downloaded. Existing EPA CSV will remain unchanged.')
data=pd.concat(frames,ignore_index=True)
# EPA per play includes pass/run plays only, excluding special teams and no-plays.
agg=data.groupby(['game_id','posteam','play_type'])['epa'].agg(['sum','count']).reset_index()
piv=agg.pivot(index=['game_id','posteam'],columns='play_type',values=['sum','count']).fillna(0)
rows=[];now=dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
for (gid,team),r in piv.iterrows():
 pcount=int(r.get(('count','pass'),0));rcount=int(r.get(('count','run'),0))
 if pcount<1 or rcount<1:continue
 ps=float(r.get(('sum','pass'),0));rs=float(r.get(('sum','run'),0))
 rows.append({'game_id':gid,'team':team,'epa_per_play':round((ps+rs)/(pcount+rcount),5),'pass_epa_per_play':round(ps/pcount,5),'rush_epa_per_play':round(rs/rcount,5),'generated_utc':now})
if len(rows)<200:raise RuntimeError('Insufficient data: refusing to overwrite existing EPA CSV')
rows.sort(key=lambda r:(r['game_id'],r['team']))
with OUT.open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print('Wrote',len(rows),'rows to',OUT)

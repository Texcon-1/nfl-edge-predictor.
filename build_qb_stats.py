#!/usr/bin/env python3
"""Build NFL Edge weekly passing stats from current nflverse season-specific player files.

The legacy combined player_stats.csv was frozen after 2024. We fetch season-specific
stats_player_week_<year>.parquet releases instead. The script fails rather than
silently publishing stale data if the most recent seasons are absent.
"""
import csv
import io
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

START_SEASON = 2022
CURRENT_SEASON = datetime.now(timezone.utc).year
OUT = Path(__file__).with_name('qb_weekly_stats.csv')
FIELDS = ['season', 'week', 'team', 'player_name', 'attempts', 'passing_yards', 'passing_tds', 'interceptions']
URL = 'https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{season}.parquet'

def get_col(frame, *candidates):
    return next((name for name in candidates if name in frame.columns), None)

def load_season(season):
    url = URL.format(season=season)
    request = urllib.request.Request(url, headers={'User-Agent': 'NFL-Edge-Predictor/2.0'})
    with urllib.request.urlopen(request, timeout=150) as response:
        data = response.read()
    frame = pd.read_parquet(io.BytesIO(data))
    required = {
        'season': get_col(frame, 'season'),
        'week': get_col(frame, 'week'),
        'team': get_col(frame, 'team', 'recent_team', 'posteam'),
        'player_name': get_col(frame, 'player_name', 'player_display_name', 'display_name'),
        'attempts': get_col(frame, 'attempts', 'passing_attempts'),
        'passing_yards': get_col(frame, 'passing_yards'),
    }
    absent = [key for key, col in required.items() if col is None]
    if absent:
        raise ValueError(f'{season} stats missing required columns {absent}; got {list(frame.columns)}')
    optional = {
        'passing_tds': get_col(frame, 'passing_tds', 'passing_touchdowns'),
        'interceptions': get_col(frame, 'passing_interceptions', 'interceptions'),
    }
    output = []
    for _, row in frame.iterrows():
        try:
            yr = int(row[required['season']]); week = int(row[required['week']])
            attempts = int(float(row[required['attempts']]))
            if yr != season or not 1 <= week <= 18 or attempts < 1:
                continue
            team = str(row[required['team']]).strip()
            player = str(row[required['player_name']]).strip()
            if not team or team.lower() in ('nan', 'none') or not player or player.lower() in ('nan','none'):
                continue
            rec = dict(season=yr, week=week, team=team, player_name=player, attempts=attempts)
            for field, col in [('passing_yards', required['passing_yards']), *optional.items()]:
                val = row[col] if col else 0
                rec[field] = int(float(val)) if pd.notna(val) and str(val) != '' else 0
            output.append(rec)
        except (ValueError, TypeError, OverflowError):
            continue
    if not output:
        raise ValueError(f'{season} had no qualifying weekly passer rows')
    print(f'{season}: {len(output)} passing rows, latest week {max(r["week"] for r in output)}')
    return output

def main():
    all_rows = []
    for season in range(START_SEASON, CURRENT_SEASON + 1):
        all_rows.extend(load_season(season))
    all_rows.sort(key=lambda r: (r['season'], r['week'], r['team'], r['player_name']))
    with OUT.open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader(); writer.writerows(all_rows)
    print(f'Wrote {len(all_rows)} passing rows through {CURRENT_SEASON} to {OUT}')
    print('Passing history only: no assertions about confirmed starters or injuries.')

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Build qb_weekly_stats.csv from nflverse weekly player statistics.

Runs on GitHub Actions (internet required). Does not infer QB starts or injuries.
"""
import io
import csv
import urllib.request
from pathlib import Path

SOURCES = [
    'https://github.com/nflverse/nflverse-data/releases/download/player_stats/player_stats.csv',
    'https://github.com/nflverse/nflverse-data/releases/download/player_stats/player_stats.csv.gz',
]
OUT = Path(__file__).with_name('qb_weekly_stats.csv')
FIELDS = ['season', 'week', 'team', 'player_name', 'attempts', 'passing_yards', 'passing_tds', 'interceptions']

def download():
    import gzip
    errors = []
    for url in SOURCES:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'NFL-Edge-Predictor/1.0'})
            with urllib.request.urlopen(req, timeout=90) as response:
                data = response.read()
            if url.endswith('.gz'):
                data = gzip.decompress(data)
            return data.decode('utf-8-sig'), url
        except Exception as e:
            errors.append(f'{url}: {e}')
    raise RuntimeError('Could not download NFLverse player stats: ' + '; '.join(errors))

def main():
    data, source = download()
    reader = csv.DictReader(io.StringIO(data))
    names = set(reader.fieldnames or [])
    def col(*choices):
        return next((c for c in choices if c in names), None)
    columns = {
        'season': col('season'), 'week': col('week'),
        'team': col('recent_team', 'team', 'posteam'),
        'player_name': col('player_name', 'player_display_name', 'display_name'),
        'attempts': col('attempts', 'passing_attempts'),
        'passing_yards': col('passing_yards'),
        'passing_tds': col('passing_tds', 'passing_touchdowns'),
        'interceptions': col('interceptions', 'passing_interceptions'),
    }
    required = ('season','week','team','player_name','attempts','passing_yards')
    missing = [k for k in required if not columns[k]]
    if missing:
        raise ValueError(f'Missing required source columns: {missing}; available: {sorted(names)}')
    rows = []
    for row in reader:
        try:
            season = int(float(row[columns['season']]))
            week = int(float(row[columns['week']]))
            attempts = float(row[columns['attempts']] or 0)
        except (ValueError, TypeError):
            continue
        if season < 2022 or week < 1 or week > 18 or attempts < 1:
            continue
        team = (row[columns['team']] or '').strip()
        player = (row[columns['player_name']] or '').strip()
        if not team or not player:
            continue
        record = {'season': season, 'week': week, 'team': team, 'player_name': player}
        for key in ('attempts', 'passing_yards', 'passing_tds', 'interceptions'):
            column = columns[key]
            raw = row[column] if column else ''
            try:
                record[key] = str(int(float(raw or 0)))
            except (ValueError, TypeError):
                record[key] = '0'
        rows.append(record)
    if not rows:
        raise ValueError('No valid quarterback rows found; output not written')
    rows.sort(key=lambda r: (r['season'], r['week'], r['team'], r['player_name']))
    with OUT.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f'Wrote {len(rows)} QB passing rows to {OUT.name} from {source}')
    print('This is observed passing history, not confirmed starts, injuries, or pregame forecasts.')

if __name__ == '__main__':
    main()

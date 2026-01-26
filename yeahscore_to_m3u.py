import requests
import json
import time
from datetime import datetime, timedelta
import sys

class YeahScoreAPI:
    def __init__(self):
        self.base_url = "https://yeahscore1.com/api"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://yeahscore1.com/"
        }
    
    def get_timestamp(self, days_offset=0):
        target_date = datetime.now() + timedelta(days=days_offset)
        target_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        return int(target_date.timestamp())
    
    def fetch_fixtures(self, date_timestamp=None):
        if date_timestamp is None:
            date_timestamp = self.get_timestamp()
        
        try:
            url = f"{self.base_url}/fixtures"
            params = {"date": date_timestamp}
            
            print(f"Fetching fixtures for timestamp: {date_timestamp}")
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            print(f"API Response Status: {data.get('status', 'unknown')}")
            
            if isinstance(data, dict):
                fixtures = data.get('data', [])
                if not fixtures and 'fixtures' in data:
                    fixtures = data.get('fixtures', [])
            elif isinstance(data, list):
                fixtures = data
            else:
                fixtures = []
            
            print(f"Found {len(fixtures)} fixtures")
            return fixtures
            
        except Exception as e:
            print(f"Error fetching fixtures: {e}")
            return []
    
    def fetch_livestreams(self):
        try:
            url = f"{self.base_url}/fixtures/livestream"
            print("Fetching livestreams...")
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if isinstance(data, dict):
                streams = data.get('data', [])
                if not streams and 'streams' in data:
                    streams = data.get('streams', [])
                if not streams and 'livestreams' in data:
                    streams = data.get('livestreams', [])
            elif isinstance(data, list):
                streams = data
            else:
                streams = []
            
            print(f"Found {len(streams)} livestreams")
            return streams
            
        except Exception as e:
            print(f"Error fetching livestreams: {e}")
            return []
    
    def extract_stream_url(self, fixture):
        possible_fields = ['stream_url', 'stream', 'live_url', 'hls_url', 'm3u8_url', 'url']
        
        for field in possible_fields:
            if field in fixture and fixture[field]:
                urls = fixture[field]
                if isinstance(urls, str):
                    return urls
                elif isinstance(urls, list) and urls:
                    return urls[0] if isinstance(urls[0], str) else str(urls[0])
                elif isinstance(urls, dict) and 'url' in urls:
                    return urls['url']
        
        if 'broadcast' in fixture:
            broadcast = fixture['broadcast']
            if isinstance(broadcast, dict) and 'streams' in broadcast:
                streams = broadcast['streams']
                if isinstance(streams, list) and streams:
                    stream = streams[0]
                    if isinstance(stream, dict) and 'url' in stream:
                        return stream['url']
        
        return None
    
    def get_team_names(self, fixture):
        home_team = "Home"
        away_team = "Away"
        
        home_fields = ['home_team', 'homeTeam', 'home', 'team_home']
        for field in home_fields:
            if field in fixture:
                home_value = fixture[field]
                if isinstance(home_value, dict):
                    home_team = home_value.get('name', home_team)
                else:
                    home_team = str(home_value)
                break
        
        away_fields = ['away_team', 'awayTeam', 'away', 'team_away']
        for field in away_fields:
            if field in fixture:
                away_value = fixture[field]
                if isinstance(away_value, dict):
                    away_team = away_value.get('name', away_team)
                else:
                    away_team = str(away_value)
                break
        
        return home_team, away_team

def main():
    print("=" * 50)
    print("YeahScore M3U Playlist Generator")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    api = YeahScoreAPI()
    all_matches = []
    
    for day_offset in range(3):
        timestamp = api.get_timestamp(day_offset)
        fixtures = api.fetch_fixtures(timestamp)
        
        for fixture in fixtures:
            home_team, away_team = api.get_team_names(fixture)
            stream_url = api.extract_stream_url(fixture)
            
            if stream_url:
                match_info = {
                    'home': home_team,
                    'away': away_team,
                    'stream_url': stream_url,
                    'time': fixture.get('time', ''),
                    'competition': fixture.get('competition', 'Football')
                }
                all_matches.append(match_info)
    
    livestreams = api.fetch_livestreams()
    for stream in livestreams:
        home_team, away_team = api.get_team_names(stream)
        stream_url = api.extract_stream_url(stream)
        
        if stream_url:
            match_info = {
                'home': home_team,
                'away': away_team,
                'stream_url': stream_url,
                'time': stream.get('time', ''),
                'competition': stream.get('competition', 'Football')
            }
            all_matches.append(match_info)
    
    seen_urls = set()
    unique_matches = []
    for match in all_matches:
        if match['stream_url'] and match['stream_url'] not in seen_urls:
            seen_urls.add(match['stream_url'])
            unique_matches.append(match)
    
    print(f"\nTotal unique matches: {len(unique_matches)}")
    
    m3u_lines = [
        '#EXTM3U',
        f'# YeahScore Playlist - Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
        f'# Total streams: {len(unique_matches)}',
        ''
    ]
    
    for idx, match in enumerate(unique_matches, 1):
        title = f"{match['home']} vs {match['away']}"
        if match.get('time'):
            title = f"{match['time']} | {title}"
        
        m3u_lines.append(f'#EXTINF:-1, {title}')
        m3u_lines.append(match['stream_url'])
        m3u_lines.append('')
    
    if len(unique_matches) == 0:
        m3u_lines.append('# No streams available')
        m3u_lines.append('# Check back later')
    
    with open("yeahscore.m3u", "w", encoding="utf-8") as f:
        f.write('\n'.join(m3u_lines))
    
    print(f"Playlist saved to: yeahscore.m3u")
    
    debug_info = {
        'generated_at': datetime.now().isoformat(),
        'total_matches': len(unique_matches),
        'matches': unique_matches
    }
    
    with open("debug_info.json", "w", encoding="utf-8") as f:
        json.dump(debug_info, f, indent=2)
    
    print("Debug info saved to: debug_info.json")
    print("=" * 50)
    
    return len(unique_matches)

if __name__ == "__main__":
    try:
        count = main()
        if count == 0:
            print("Warning: No streams found")
            sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

import json
import re
import time
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def get_stream_url(page, match_url):
    """
    Membuka halaman detail dan menangkap request .m3u8
    """
    m3u8_url = None

    def handle_request(request):
        nonlocal m3u8_url
        if ".m3u8" in request.url and m3u8_url is None:
            m3u8_url = request.url

    try:
        page.on("request", handle_request)
        # Timeout 20 detik per halaman match
        page.goto(match_url, timeout=20000)
        
        # Coba tunggu iframe atau canvas player
        try:
            page.wait_for_selector('iframe, canvas', timeout=5000)
        except:
            pass
            
        page.wait_for_timeout(4000) # Tunggu network traffic
        page.remove_listener("request", handle_request)
        return m3u8_url
    except Exception as e:
        return None

def clean_text(text):
    if not text: return ""
    return text.strip()

def main():
    all_matches = []
    base_url = "https://yeahscore1.com"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Menggunakan User Agent agar tidak terdeteksi bot
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print("1. Membuka Halaman Utama...")
        try:
            page.goto(base_url + "/", timeout=60000)
            page.wait_for_timeout(5000) # Tunggu render VUE JS
            
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')

            # ==========================================
            # BAGIAN 1: SCRAPE LIVE MATCHES
            # ==========================================
            print("--- Memproses Live Matches ---")
            live_container = soup.select_one('.b-live-matches')
            if live_container:
                # Di dalam live, biasanya dikelompokkan per Liga di dalam .collapse-group
                league_groups = live_container.select('.collapse-group')
                
                for group in league_groups:
                    # Ambil Nama Liga
                    league_title_el = group.select_one('.collapse-nav-title-name')
                    full_league_name = clean_text(league_title_el.get_text()) if league_title_el else "Live League"
                    
                    sport_name = "Football" # Default
                    
                    # Cari match di dalam grup liga ini
                    matches = group.select('.collapse-match')
                    for match in matches:
                        try:
                            link_tag = match.select_one('a.link-wrapper')
                            if not link_tag: continue
                            match_url = base_url + link_tag['href']

                            # Ambil nama tim
                            home_el = match.select_one('.left-column .name-club')
                            away_el = match.select_one('.right-column .name-club')
                            home = clean_text(home_el.get_text()) if home_el else "Home"
                            away = clean_text(away_el.get_text()) if away_el else "Away"

                            # Waktu (Menit main)
                            inplay_el = match.select_one('.inplay')
                            game_time = clean_text(inplay_el.get_text()) if inplay_el else "LIVE"

                            all_matches.append({
                                "type": "LIVE",
                                "sport": sport_name,
                                "league": full_league_name,
                                "teams": f"{home} vs {away}",
                                "time_display": f"LIVE {game_time}",
                                "url_page": match_url,
                                "stream_url": None 
                            })
                        except: continue

            # ==========================================
            # BAGIAN 2: SCRAPE SCHEDULE / UPCOMING
            # ==========================================
            print("--- Memproses Upcoming Schedule ---")
            schedule_container = soup.select_one('.b-live-schedule')
            if schedule_container:
                # Cari Header Sport (Football, Basketball, Cricket, dll)
                sport_headers = schedule_container.select('h2.b-bg-secondary')
                
                for h2 in sport_headers:
                    # 1. Ambil Nama Sport (Misal: "Football (15)")
                    raw_sport = clean_text(h2.get_text())
                    sport_name = re.sub(r'\s*\(\d+\)', '', raw_sport)
                    
                    # 2. Cari Div konten setelah h2
                    content_wrapper = h2.find_next_sibling('div')
                    if not content_wrapper: continue

                    # 3. Loop Liga di dalam Sport tersebut
                    league_groups = content_wrapper.select('.collapse-group')
                    
                    for l_group in league_groups:
                        l_title_el = l_group.select_one('.collapse-nav-title-name')
                        league_name = clean_text(l_title_el.get_text()) if l_title_el else "Unknown League"

                        # 4. Loop Match di dalam Liga tersebut
                        items = l_group.select('.item')
                        for item in items:
                            try:
                                link_tag = item.select_one('a.link-wrapper')
                                if not link_tag: continue
                                match_url = base_url + link_tag['href']

                                # Nama Tim
                                home_el = item.select_one('.left-column .name-club')
                                away_el = item.select_one('.right-column .name-club')
                                
                                if home_el and away_el:
                                    teams = f"{clean_text(home_el.get_text())} vs {clean_text(away_el.get_text())}"
                                else:
                                    title_el = item.select_one('.item-title')
                                    teams = clean_text(title_el.get_text()) if title_el else "Event"

                                # Waktu
                                time_el = item.select_one('.time')
                                match_time = clean_text(time_el.get_text(" ")) if time_el else ""

                                all_matches.append({
                                    "type": "UPCOMING",
                                    "sport": sport_name,
                                    "league": league_name,
                                    "teams": teams,
                                    "time_display": match_time,
                                    "url_page": match_url,
                                    "stream_url": None
                                })
                            except: continue
        except Exception as e:
            print(f"Error membuka halaman utama: {e}")

        # ==========================================
        # BAGIAN 3: AMBIL LINK STREAM (Deep Scraping)
        # ==========================================
        print(f"Total Match Terdeteksi: {len(all_matches)}")
        print("Mulai mengambil link stream (Max 30 match prioritas)...")

        processed_matches = []
        # Slice [:30] hanya ambil 30 pertama untuk mencegah timeout di github actions
        for i, match in enumerate(all_matches[:30]): 
            print(f"[{i+1}/{len(all_matches[:30])}] Checking: {match['teams']} ({match['league']})")
            
            detail_page = context.new_page()
            stream = get_stream_url(detail_page, match['url_page'])
            detail_page.close()
            
            match['stream_url'] = stream
            match['referer'] = base_url
            processed_matches.append(match)
            
            if stream:
                print(f"   -> STREAM FOUND!")
            else:
                print(f"   -> No Stream / Belum mulai")

        browser.close()

    # Simpan JSON
    with open("matches.json", "w", encoding="utf-8") as f:
        json.dump(processed_matches, f, indent=4)
        print("Data tersimpan di matches.json")

if __name__ == "__main__":
    main()

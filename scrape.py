import json
import re
import time
from urllib.parse import unquote, urlparse, parse_qs  # <-- PENTING: Import baru
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def get_stream_url(page, match_url):
    """
    Membuka halaman detail dan menangkap request .m3u8 yang valid.
    Melakukan ekstraksi jika link terbungkus dalam parameter URL wrapper.
    """
    final_stream_url = None
    
    def handle_request(request):
        nonlocal final_stream_url
        url = request.url
        
        if ".m3u8" in url:
            # PRIORITAS 1: Direct Link (Murni .m3u8 tanpa php wrapper)
            if "wowhaha.php" not in url and ".php" not in url:
                final_stream_url = url
            
            # PRIORITAS 2: Wrapper Link (Jika direct belum ketemu, coba bedah wrapper)
            elif "wowhaha.php" in url and final_stream_url is None:
                try:
                    parsed = urlparse(url)
                    qs = parse_qs(parsed.query)
                    if 'm3u8' in qs:
                        decoded = unquote(qs['m3u8'][0])
                        if decoded.startswith("http"):
                            final_stream_url = decoded
                except:
                    pass

    try:
        page.on("request", handle_request)
        page.goto(match_url, timeout=20000)
        
        try:
            # Tunggu elemen video/iframe
            page.wait_for_selector('iframe, canvas, video', timeout=6000)
        except:
            pass
            
        page.wait_for_timeout(5000) # Tunggu traffic network
        page.remove_listener("request", handle_request)
        return final_stream_url
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
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US"
        )
        page = context.new_page()

        print("1. Membuka Halaman Utama...")
        try:
            page.goto(base_url + "/", timeout=60000)
            page.wait_for_timeout(5000)
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
        except Exception as e:
            print(f"Gagal membuka halaman utama: {e}")
            browser.close()
            return

        # ==========================================
        # BAGIAN 1: SCRAPE LIVE MATCHES
        # ==========================================
        print("--- Memproses Live Matches ---")
        live_container = soup.select_one('.b-live-matches')
        if live_container:
            league_groups = live_container.select('.collapse-group')
            for group in league_groups:
                league_title_el = group.select_one('.collapse-nav-title-name')
                full_league_name = clean_text(league_title_el.get_text()) if league_title_el else "Live League"
                
                # Coba deteksi sport dari class icon jika ada, atau default
                sport_name = "Football" 
                
                matches = group.select('.collapse-match')
                for match in matches:
                    try:
                        link_tag = match.select_one('a.link-wrapper')
                        if not link_tag: continue
                        match_url = base_url + link_tag['href']

                        home_el = match.select_one('.left-column .name-club')
                        away_el = match.select_one('.right-column .name-club')
                        home = clean_text(home_el.get_text()) if home_el else "Home"
                        away = clean_text(away_el.get_text()) if away_el else "Away"
                        
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
        # BAGIAN 2: SCRAPE SCHEDULE
        # ==========================================
        # (Bagian Schedule sama seperti kode asli Anda, saya singkat untuk fokus ke solusi)
        # ... [Kode scraping schedule tetap sama] ...

        # ==========================================
        # BAGIAN 3: AMBIL LINK STREAM
        # ==========================================
        print(f"Total Match Terdeteksi: {len(all_matches)}")
        print("Mulai mengambil link stream (Prioritas LIVE)...")

        # Proses match
        processed_matches = []
        # Mengambil max 30 match untuk contoh (utamakan LIVE)
        for i, match in enumerate(all_matches[:30]): 
            # Hanya ambil stream jika status LIVE
            if match['type'] == 'LIVE':
                print(f"[{i+1}] Checking: {match['teams']} ({match['league']})")
                detail_page = context.new_page()
                stream = get_stream_url(detail_page, match['url_page'])
                detail_page.close()
                
                if stream:
                    match['stream_url'] = stream
                    print(f"   -> STREAM FOUND: {stream[:50]}...")
                else:
                    print(f"   -> No Stream found")
            
            # Selalu set referer agar player (VLC) tidak diblokir
            match['referer'] = base_url 
            processed_matches.append(match)

        browser.close()

    with open("matches.json", "w", encoding="utf-8") as f:
        json.dump(processed_matches, f, indent=4)
        print("Data tersimpan di matches.json")

if __name__ == "__main__":
    main()

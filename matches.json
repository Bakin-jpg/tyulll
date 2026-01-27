import json
import re
import time
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def get_real_stream_url(context, match_url):
    """
    Membuka halaman match, mencari wrapper (xiaolin/wowhaha),
    lalu mengekstrak link asli dari dalam source code wrapper tersebut.
    """
    page = context.new_page()
    wrapper_url = None
    final_m3u8 = None

    # 1. Listener untuk menangkap URL wrapper (iframe)
    def handle_request(request):
        nonlocal wrapper_url
        url = request.url
        # Cari URL yang mengandung wowhaha atau xiaolin
        if ("wowhaha.php" in url or "xiaolin" in url) and "m3u8=" in url:
            wrapper_url = url

    try:
        # Pasang listener
        page.on("request", handle_request)
        
        # Buka halaman match
        # Timeout dipercepat karena kita cuma butuh request network awal
        try:
            page.goto(match_url, timeout=15000, wait_until="domcontentloaded")
            # Tunggu sebentar agar iframe termuat di network
            page.wait_for_timeout(3000) 
        except:
            pass # Lanjut cek apakah wrapper_url dapet

        # Hapus listener
        page.remove_listener("request", handle_request)

        # 2. Jika wrapper ketemu, kita bongkar isinya
        if wrapper_url:
            print(f"      [DEBUG] Wrapper found: {wrapper_url[:50]}...")
            
            # Kita fetch source code dari wrapper_url tanpa membuka tab baru (hemat resource)
            # Menggunakan API request bawaan playwright
            response = page.request.get(wrapper_url)
            if response.status == 200:
                html_content = response.text()
                
                # 3. REGEX: Cari teks -> var m3u8 = 'LINK_ASLI';
                # Pola ini sesuai dengan source code yang Anda kirim
                match = re.search(r"var\s+m3u8\s*=\s*'([^']+)'", html_content)
                if match:
                    final_m3u8 = match.group(1)
                    print(f"      [SUCCESS] Extracted real M3U8!")
                else:
                    print(f"      [FAIL] Pattern 'var m3u8' not found in wrapper.")
            else:
                print(f"      [FAIL] Could not fetch wrapper content.")
        else:
            print("      [INFO] No wrapper/iframe detected.")

    except Exception as e:
        print(f"      [ERROR] {e}")
    finally:
        page.close()

    return final_m3u8

def clean_text(text):
    if not text: return ""
    return text.strip()

def main():
    all_matches = []
    base_url = "https://yeahscore1.com"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # User Agent penting agar tidak diblokir saat fetch wrapper
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ignore_https_errors=True
        )
        page = context.new_page()

        print("1. Membuka Halaman Utama...")
        try:
            page.goto(base_url + "/", timeout=60000)
            page.wait_for_timeout(5000) # Tunggu render
            
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')

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
            print("--- Memproses Upcoming Schedule ---")
            schedule_container = soup.select_one('.b-live-schedule')
            if schedule_container:
                sport_headers = schedule_container.select('h2.b-bg-secondary')
                for h2 in sport_headers:
                    raw_sport = clean_text(h2.get_text())
                    sport_name = re.sub(r'\s*\(\d+\)', '', raw_sport)
                    
                    content_wrapper = h2.find_next_sibling('div')
                    if not content_wrapper: continue

                    league_groups = content_wrapper.select('.collapse-group')
                    for l_group in league_groups:
                        l_title_el = l_group.select_one('.collapse-nav-title-name')
                        league_name = clean_text(l_title_el.get_text()) if l_title_el else "Unknown League"

                        items = l_group.select('.item')
                        for item in items:
                            try:
                                link_tag = item.select_one('a.link-wrapper')
                                if not link_tag: continue
                                match_url = base_url + link_tag['href']

                                home_el = item.select_one('.left-column .name-club')
                                away_el = item.select_one('.right-column .name-club')
                                if home_el and away_el:
                                    teams = f"{clean_text(home_el.get_text())} vs {clean_text(away_el.get_text())}"
                                else:
                                    title_el = item.select_one('.item-title')
                                    teams = clean_text(title_el.get_text()) if title_el else "Event"

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
        # BAGIAN 3: AMBIL LINK STREAM (EXTRACTION)
        # ==========================================
        print(f"Total Match Terdeteksi: {len(all_matches)}")
        print("Mulai mengambil link stream dan mengekstrak token...")

        processed_matches = []
        
        # Batasi jumlah match agar tidak timeout (misal 30 match prioritas)
        target_matches = all_matches[:30] 

        for i, match in enumerate(target_matches): 
            print(f"[{i+1}/{len(target_matches)}] {match['teams']}")
            
            # Panggil fungsi extraction baru
            real_stream = get_real_stream_url(context, match['url_page'])
            
            match['stream_url'] = real_stream
            
            # Referer kadang dibutuhkan player, kita set ke referer aslinya wrapper
            # atau biarkan yeahscore sebagai fallback
            match['referer'] = "https://xiaolin3.live/" if real_stream else base_url
            
            processed_matches.append(match)

        browser.close()

    # Simpan JSON
    with open("matches.json", "w", encoding="utf-8") as f:
        json.dump(processed_matches, f, indent=4)
        print("Data tersimpan di matches.json")

if __name__ == "__main__":
    main()

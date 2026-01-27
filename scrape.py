import json
import re
import time
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

# --- FUNGSI UTAMA PENGAMBIL STREAM ---
def get_real_stream_url(context, match_url):
    """
    Mencoba mendapatkan link m3u8 asli dengan 2 metode:
    1. Sniffing Network (Menangkap request background)
    2. DOM Inspection (Mencari src di dalam tag iframe)
    """
    page = context.new_page()
    wrapper_url = None
    final_m3u8 = None

    # --- METODE 1: Network Sniffer ---
    def handle_request(request):
        nonlocal wrapper_url
        url = request.url
        # Keyword umum player di website ini
        keywords = ["wowhaha.php", "xiaolin", "embed", "player", "rum.php"]
        if any(x in url for x in keywords) and "m3u8=" in url:
            wrapper_url = url

    try:
        page.on("request", handle_request)
        
        # Buka halaman match
        try:
            # wait_until='networkidle' memastikan halaman diam sejenak (semua loading kelar)
            page.goto(match_url, timeout=20000, wait_until="networkidle") 
        except:
            pass # Lanjut ke pengecekan manual jika timeout

        # --- METODE 2: DOM Inspection (Backup jika Network gagal) ---
        if not wrapper_url:
            # Cari semua iframe di halaman
            iframes = page.query_selector_all("iframe")
            for frame in iframes:
                src = frame.get_attribute("src")
                if src and ("m3u8=" in src):
                    wrapper_url = src
                    if not wrapper_url.startswith("http"): # Handle relative URL
                        wrapper_url = "https:" + wrapper_url if src.startswith("//") else src
                    print(f"      [INFO] Wrapper found via DOM (Iframe)!")
                    break

        page.remove_listener("request", handle_request)

        # --- EKSEKUSI: Ambil Token dari Wrapper ---
        if wrapper_url:
            # Bersihkan URL jika ada karakter aneh
            print(f"      [DEBUG] Wrapper URL: {wrapper_url[:60]}...")
            
            # Fetch source code wrapper tanpa render browser (cepat)
            response = page.request.get(wrapper_url)
            
            if response.status == 200:
                html_content = response.text()
                
                # REGEX: Cari var m3u8 = '...' atau var m3u8="..."
                # Menangani kutip satu (') maupun kutip dua (")
                pattern = r"var\s+m3u8\s*=\s*['\"]([^'\"]+)['\"]"
                match = re.search(pattern, html_content)
                
                if match:
                    final_m3u8 = match.group(1)
                    print(f"      [SUCCESS] Stream URL Extracted!")
                else:
                    print(f"      [FAIL] Token pattern not found inside wrapper.")
                    # Debug: Simpan potongan html untuk dicek
                    # print(html_content[:500]) 
            else:
                print(f"      [FAIL] Wrapper unreachable (Status {response.status}).")
        else:
            print("      [FAIL] No wrapper/iframe detected.")

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
        # headless=True agar berjalan di background. Ubah ke False jika ingin melihat browser.
        browser = p.chromium.launch(headless=True)
        
        # Context dengan User Agent PC agar dianggap user asli
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 720},
            ignore_https_errors=True
        )
        page = context.new_page()

        print("1. Membuka Halaman Utama...")
        try:
            page.goto(base_url + "/", timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000) # Tunggu render Vue/React
            
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
                    sport_name = "Football" # Default, bisa diperbaiki dengan cek icon/header
                    
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
        # BAGIAN 3: AMBIL LINK STREAM (Deep Extraction)
        # ==========================================
        total_found = len(all_matches)
        print(f"\nTotal Match Terdeteksi: {total_found}")
        print("Mulai mengambil link stream...")

        processed_matches = []
        
        # Filter: Hanya proses match yang "LIVE" atau match yang akan main dalam waktu dekat
        # Agar tidak buang waktu scan match yang masih 2 hari lagi
        # Untuk tes, kita ambil 10 LIVE teratas dan 5 UPCOMING teratas
        
        live_matches = [m for m in all_matches if m['type'] == 'LIVE']
        upcoming_matches = [m for m in all_matches if m['type'] == 'UPCOMING'][:15] # Batasi 15 upcoming
        
        target_list = live_matches + upcoming_matches

        for i, match in enumerate(target_list): 
            print(f"[{i+1}/{len(target_list)}] {match['teams']} ({match['type']})")
            
            # Jika Upcoming masih lama, biasanya belum ada stream, tapi kita coba cek
            real_stream = get_real_stream_url(context, match['url_page'])
            
            match['stream_url'] = real_stream
            
            # Jika berhasil dapat stream, referernya pakai domain wrapper (biasanya xiaolin)
            # Jika gagal, default ke yeahscore
            match['referer'] = "https://xiaolin3.live/" if real_stream else base_url
            
            processed_matches.append(match)

        browser.close()

    # Simpan JSON
    with open("matches.json", "w", encoding="utf-8") as f:
        json.dump(processed_matches, f, indent=4)
        print("\nData tersimpan di matches.json")

if __name__ == "__main__":
    main()

import json
import re
import time
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

# --- FUNGSI UTAMA PENGAMBIL STREAM ---
def get_real_stream_url(context, match_url):
    page = context.new_page()
    wrapper_url = None
    final_m3u8 = None

    def handle_request(request):
        nonlocal wrapper_url
        url = request.url
        # Keyword umum player
        keywords = ["wowhaha.php", "xiaolin", "embed", "player", "rum.php"]
        if any(x in url for x in keywords) and "m3u8=" in url:
            wrapper_url = url

    try:
        page.on("request", handle_request)
        try:
            page.goto(match_url, timeout=15000, wait_until="domcontentloaded")
        except:
            pass 

        if not wrapper_url:
            # Cek DOM Iframe
            iframes = page.query_selector_all("iframe")
            for frame in iframes:
                src = frame.get_attribute("src")
                if src and ("m3u8=" in src):
                    wrapper_url = src
                    if not wrapper_url.startswith("http"):
                        wrapper_url = "https:" + wrapper_url if src.startswith("//") else src
                    break

        page.remove_listener("request", handle_request)

        if wrapper_url:
            try:
                response = page.request.get(wrapper_url, timeout=5000)
                if response.status == 200:
                    html_content = response.text()
                    pattern = r"var\s+m3u8\s*=\s*['\"]([^'\"]+)['\"]"
                    match = re.search(pattern, html_content)
                    if match:
                        final_m3u8 = match.group(1)
            except:
                pass
    except Exception as e:
        print(f"      [ERROR Stream] {e}")
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
        # --- PERBAIKAN 1: Tambahkan argumen agar tidak terdeteksi sebagai Bot ---
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled', # PENTING: Sembunyikan identitas bot
                '--no-sandbox',
                '--disable-setuid-sandbox'
            ]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1366, 'height': 768},
            ignore_https_errors=True
        )
        page = context.new_page()

        print("1. Membuka Halaman Utama...")
        try:
            page.goto(base_url + "/", timeout=60000)
            
            # --- PERBAIKAN 2: Tunggu Elemen Muncul (Bukan cuma sleep) ---
            print("   -> Menunggu daftar match muncul...")
            try:
                # Kita tunggu sampai container match muncul, max 15 detik
                page.wait_for_selector(".b-live-matches, .b-live-schedule", timeout=15000)
                print("   -> Elemen website terdeteksi!")
            except Exception as e:
                print("   -> [WARNING] Website lambat atau memblokir bot. Mengambil screenshot...")
                page.screenshot(path="debug_error.png") # Screenshot untuk debug
                print("   -> Screenshot disimpan sebagai debug_error.png")
            
            # Tambahan waktu render JS
            page.wait_for_timeout(3000)

            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')

            # ==========================================
            # BAGIAN SCRAPING (SAMA SEPERTI SEBELUMNYA)
            # ==========================================
            
            # 1. LIVE
            live_container = soup.select_one('.b-live-matches')
            if live_container:
                league_groups = live_container.select('.collapse-group')
                for group in league_groups:
                    league_title_el = group.select_one('.collapse-nav-title-name')
                    full_league_name = clean_text(league_title_el.get_text()) if league_title_el else "Live League"
                    
                    matches = group.select('.collapse-match')
                    for match in matches:
                        try:
                            link_tag = match.select_one('a.link-wrapper')
                            if not link_tag: continue
                            
                            # Filter: Hanya ambil yang ada linknya
                            match_url = base_url + link_tag['href']
                            
                            home_el = match.select_one('.left-column .name-club')
                            away_el = match.select_one('.right-column .name-club')
                            home = clean_text(home_el.get_text()) if home_el else "Home"
                            away = clean_text(away_el.get_text()) if away_el else "Away"
                            inplay_el = match.select_one('.inplay')
                            game_time = clean_text(inplay_el.get_text()) if inplay_el else "LIVE"

                            all_matches.append({
                                "type": "LIVE",
                                "sport": "Football", # Default
                                "league": full_league_name,
                                "teams": f"{home} vs {away}",
                                "time_display": f"LIVE {game_time}",
                                "url_page": match_url,
                                "stream_url": None 
                            })
                        except: continue
            
            # 2. UPCOMING
            schedule_container = soup.select_one('.b-live-schedule')
            if schedule_container:
                # Cek apakah ada header sport
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
        # BAGIAN AMBIL STREAM
        # ==========================================
        total_found = len(all_matches)
        print(f"\nTotal Match Terdeteksi: {total_found}")
        
        # JIKA HASIL 0, hentikan dan simpan debug
        if total_found == 0:
            print("!!! PERINGATAN: Tidak ada match ditemukan. Website mungkin memblokir IP GitHub.")
            print("Cek screenshot 'debug_error.png' jika Anda menjalankannya secara lokal/artifact.")
        else:
            print("Mulai mengambil link stream...")

            processed_matches = []
            
            # Prioritas: Live Match + Top 5 Upcoming
            live_matches = [m for m in all_matches if m['type'] == 'LIVE']
            upcoming_matches = [m for m in all_matches if m['type'] == 'UPCOMING'][:10]
            target_list = live_matches + upcoming_matches

            for i, match in enumerate(target_list): 
                print(f"[{i+1}/{len(target_list)}] {match['teams']} ({match['type']})")
                
                real_stream = get_real_stream_url(context, match['url_page'])
                match['stream_url'] = real_stream
                match['referer'] = "https://xiaolin3.live/" if real_stream else base_url
                
                processed_matches.append(match)

            # Simpan JSON
            with open("matches.json", "w", encoding="utf-8") as f:
                json.dump(processed_matches, f, indent=4)
                print("\nData tersimpan di matches.json")

        browser.close()

if __name__ == "__main__":
    main()

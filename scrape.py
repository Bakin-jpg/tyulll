import json
import re
import time
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def get_real_stream_url(page, match_url):
    """
    Fungsi ini masuk ke dalam Iframe player dan mengekstrak variabel 'var m3u8'
    """
    try:
        print(f"   -> Membuka halaman match: {match_url}")
        page.goto(match_url, timeout=30000, wait_until="domcontentloaded")
        
        # 1. Cari Iframe Player
        # Player biasanya ada di dalam iframe yang src-nya mengandung 'xiaolin3' atau 'wowhaha'
        try:
            iframe_element = page.wait_for_selector("iframe[src*='xiaolin3'], iframe[src*='wowhaha'], iframe[src*='m3u8=']", timeout=5000)
        except:
            print("   -> Iframe player tidak ditemukan via selector, mencoba sniffing...")
            return None

        if iframe_element:
            player_url = iframe_element.get_attribute("src")
            print(f"   -> Player Wrapper ditemukan: {player_url}")
            
            # 2. Buka URL Player tersebut secara langsung
            # Kita buka di tab yang sama agar cepat
            page.goto(player_url, timeout=30000, wait_until="domcontentloaded")
            
            # 3. Ambil Source Code HTML
            player_html = page.content()
            
            # 4. Cari variabel var m3u8 = '...'; menggunakan Regex
            # Pola: var m3u8 = 'LINK';
            match = re.search(r"var\s+m3u8\s*=\s*'([^']+)'", player_html)
            
            if match:
                real_url = match.group(1)
                print(f"   -> BERHASIL! Link asli didapat.")
                return real_url
            else:
                print("   -> Gagal mengekstrak var m3u8 dari HTML.")
                return None
                
    except Exception as e:
        print(f"   -> Error extracting: {e}")
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
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print("1. Mengambil Daftar Pertandingan...")
        try:
            page.goto(base_url + "/", timeout=60000)
            page.wait_for_timeout(3000)
            
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')

            # --- LOGIKA SCRAPE LIST MATCH (Sama seperti sebelumnya) ---
            # Kita gabungkan Live & Upcoming jadi satu loop sederhana
            
            # 1. Cari Live Matches
            live_items = soup.select('.b-live-matches .collapse-match')
            for item in live_items:
                try:
                    link = item.select_one('a.link-wrapper')['href']
                    home = clean_text(item.select_one('.left-column .name-club').get_text())
                    away = clean_text(item.select_one('.right-column .name-club').get_text())
                    
                    # Cari nama liga (naik ke parent)
                    league_el = item.find_parent(class_='collapse-group').select_one('.collapse-nav-title-name')
                    league = clean_text(league_el.get_text()) if league_el else "Live League"

                    all_matches.append({
                        "teams": f"{home} vs {away}",
                        "league": league,
                        "time": "LIVE",
                        "type": "LIVE",
                        "url_page": base_url + link,
                        "stream_url": None
                    })
                except: continue

            # 2. Cari Upcoming (Batasi 15 teratas agar cepat)
            upcoming_items = soup.select('.b-live-schedule .item')
            for item in upcoming_items[:15]: 
                try:
                    link_tag = item.select_one('a.link-wrapper')
                    if not link_tag: continue
                    link = link_tag['href']
                    
                    # Logic nama tim
                    home_el = item.select_one('.left-column .name-club')
                    away_el = item.select_one('.right-column .name-club')
                    if home_el and away_el:
                        teams = f"{clean_text(home_el.get_text())} vs {clean_text(away_el.get_text())}"
                    else:
                        teams = clean_text(item.select_one('.item-title').get_text())

                    time_val = clean_text(item.select_one('.time').get_text())
                    
                    # Cari nama liga
                    league_el = item.find_parent(class_='collapse-group').select_one('.collapse-nav-title-name')
                    league = clean_text(league_el.get_text()) if league_el else "Upcoming"

                    all_matches.append({
                        "teams": teams,
                        "league": league,
                        "time": time_val,
                        "type": "UPCOMING",
                        "url_page": base_url + link,
                        "stream_url": None
                    })
                except: continue

            print(f"Total Match ditemukan: {len(all_matches)}")

            # --- PROCESS DEEP LINKING ---
            print("2. Mengekstrak Link Stream (Deep Extraction)...")
            
            # Proses hanya 20 match pertama untuk menghindari Timeout GitHub Actions
            for i, match in enumerate(all_matches[:50]):
                print(f"[{i+1}] {match['teams']} ({match['type']})")
                
                # Hanya proses jika LIVE atau main hari ini (ada kata 'Today' atau jam tanpa tanggal)
                # Sederhananya: kita proses yang LIVE dulu
                if match['type'] == 'LIVE' or ':' in match['time']: 
                    page_extractor = context.new_page()
                    real_link = get_real_stream_url(page_extractor, match['url_page'])
                    page_extractor.close()
                    
                    if real_link:
                        match['stream_url'] = real_link
                    else:
                        match['stream_url'] = None
                
            browser.close()

        except Exception as e:
            print(f"Critical Error: {e}")
            browser.close()

    # Simpan
    with open("matches.json", "w", encoding="utf-8") as f:
        json.dump(all_matches, f, indent=4)
        print("Selesai. Data tersimpan.")

if __name__ == "__main__":
    main()

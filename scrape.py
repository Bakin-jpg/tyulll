import json
import re
import time
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def get_stream_token(context, iframe_url, referer):
    """
    Buka URL iframe secara langsung (background request) dan ambil token lewat Regex HTML.
    Metode ini jauh lebih cepat dan akurat daripada menunggu video loading.
    """
    try:
        print(f"      -> Bedah Iframe: {iframe_url[:60]}...")
        page = context.new_page()
        
        # Request source code halaman player (tanpa render gambar/video)
        # Kita set referer agar server player mengira kita dari yeahscore
        response = page.request.get(
            iframe_url, 
            headers={"Referer": referer}
        )
        
        if response.status == 200:
            html_content = response.text()
            # Regex menangkap: var m3u8 = 'https://...';
            match = re.search(r"var\s+m3u8\s*=\s*['\"]([^'\"]+)['\"]", html_content)
            if match:
                print("      [SUKSES] Token M3U8 ditemukan!")
                page.close()
                return match.group(1)
            else:
                print("      [GAGAL] Pattern m3u8 tidak ditemukan di source iframe.")
        else:
            print(f"      [GAGAL] HTTP Status: {response.status}")
        
        page.close()
    except Exception as e:
        print(f"      [ERROR] {e}")
    
    return None

def main():
    all_matches = []
    base_url = "https://yeahscore1.com"

    with sync_playwright() as p:
        # Browser Setup Anti-Bot
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ]
        )
        context = browser.new_context()
        page = context.new_page()

        print("1. Membuka Halaman Utama...")
        try:
            page.goto(base_url + "/", timeout=60000, wait_until="domcontentloaded")
            
            # Tunggu elemen match muncul (Live atau Schedule)
            try:
                page.wait_for_selector("a.link-wrapper", timeout=15000)
                print("   -> Data website berhasil dimuat.")
            except:
                print("   -> Waktu tunggu habis, mencoba parsing apa adanya...")

            # Parse HTML
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # =========================================================
            # LOGIKA BARU: FLAT SEARCH (Berdasarkan HTML Debug Anda)
            # =========================================================
            
            # Cari semua link match (Live & Upcoming strukturnya mirip)
            # Kita cari elemen 'a' dengan class 'link-wrapper' karena itu pasti link detail
            link_elements = soup.select('a.link-wrapper')
            
            print(f"   -> Menemukan {len(link_elements)} potensi pertandingan.")

            for link in link_elements:
                try:
                    match_url = base_url + link['href']
                    
                    # Cari container pembungkus (Parent)
                    # Di HTML Anda: class="b-collapse collapse-match" (Live) ATAU class="item" (Upcoming)
                    container = link.find_parent(class_=['collapse-match', 'item'])
                    if not container: continue

                    # Ambil Nama Tim
                    # Struktur: .left-column .name-club VS .right-column .name-club
                    home_el = container.select_one('.left-column .name-club')
                    away_el = container.select_one('.right-column .name-club')
                    
                    if home_el and away_el:
                        home = home_el.get_text(strip=True)
                        away = away_el.get_text(strip=True)
                        teams = f"{home} vs {away}"
                    else:
                        # Fallback jika nama tim tidak standar (misal Tennis: "Court 7")
                        title_el = container.select_one('.item-title') or container.select_one('.name-club')
                        teams = title_el.get_text(strip=True) if title_el else "Unknown Match"

                    # Ambil Waktu / Status
                    # Live ada di .inplay atau .time, Upcoming di .time
                    time_el = container.select_one('.inplay') or container.select_one('.time')
                    time_raw = time_el.get_text(" ", strip=True) if time_el else ""
                    
                    # Tentukan Tipe (LIVE atau UPCOMING)
                    # Cek apakah container ada di dalam bagian LIVE
                    is_live = False
                    parent_section = container.find_parent(class_='b-live-matches')
                    if parent_section:
                        is_live = True
                    
                    match_type = "LIVE" if is_live else "UPCOMING"
                    display_time = "LIVE NOW" if is_live else time_raw
                    
                    # Ambil Liga (Agak tricky karena struktur nested, kita defaultkan dulu)
                    league = "International" # Default
                    # Coba cari header grup terdekat
                    group_header = container.find_parent(class_='collapse-group')
                    if group_header:
                        league_el = group_header.select_one('.collapse-nav-title-name') or group_header.select_one('h3')
                        if league_el:
                            league = league_el.get_text(strip=True)

                    all_matches.append({
                        "type": match_type,
                        "league": league,
                        "teams": teams,
                        "time_display": display_time,
                        "url_page": match_url,
                        "stream_url": None,
                        "referer": base_url
                    })
                except Exception as e:
                    continue # Skip item yang error

        except Exception as e:
            print(f"Error parse halaman utama: {e}")

        # ==========================================
        # BAGIAN AMBIL LINK STREAM (Deep Scrape)
        # ==========================================
        print(f"\nTotal Match Valid: {len(all_matches)}")
        
        # Filter: Ambil Semua LIVE dan 15 UPCOMING Teratas
        targets = [m for m in all_matches if m['type'] == 'LIVE']
        upcoming = [m for m in all_matches if m['type'] == 'UPCOMING'][:15]
        targets.extend(upcoming)
        
        final_data = []

        for i, match in enumerate(targets):
            print(f"[{i+1}/{len(targets)}] {match['teams']} ({match['type']})")
            
            # 1. Buka Halaman Detail Match
            detail_page = context.new_page()
            iframe_src = None
            
            try:
                detail_page.goto(match['url_page'], timeout=15000, wait_until="domcontentloaded")
                
                # 2. Cari Iframe Player
                # Di HTML Anda iframe ada ID aneh, tapi SRC nya pasti mengandung domain player
                try:
                    detail_page.wait_for_selector('iframe[src*="wowhaha"], iframe[src*="xiaolin"], iframe[src*="embed"]', timeout=5000)
                except: pass
                
                iframes = detail_page.query_selector_all("iframe")
                for frame in iframes:
                    src = frame.get_attribute("src")
                    if src and ("wowhaha" in src or "xiaolin" in src or "embed" in src):
                        iframe_src = src
                        # Fix protocol relative url (//domain.com -> https://domain.com)
                        if src.startswith("//"): iframe_src = "https:" + src
                        break
            except:
                print("      [SKIP] Gagal load detail page.")
            finally:
                detail_page.close()

            # 3. Jika iframe ketemu, ambil tokennya
            if iframe_src:
                token_url = get_stream_token(context, iframe_src, match['url_page'])
                match['stream_url'] = token_url
                # Set referer ke xiaolin agar player VLC tidak diblokir
                if token_url:
                    match['referer'] = "https://xiaolin3.live/"
            else:
                print("      [INFO] Tidak ada player/iframe.")

            final_data.append(match)

        browser.close()

    # Simpan JSON
    with open("matches.json", "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=4)
        print("\nSelesai. Data tersimpan di matches.json")

if __name__ == "__main__":
    main()

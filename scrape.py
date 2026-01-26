import json
import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def clean_text(text):
    """Membersihkan text dari newlines dan spasi berlebih"""
    if not text: return ""
    return " ".join(text.split())

def get_real_stream_url(page, match_url):
    """Mencari Link M3U8 dan Referer Player"""
    try:
        print(f"   -> Membuka: {match_url}")
        page.goto(match_url, timeout=40000, wait_until="domcontentloaded")
        
        # 1. Cari Iframe Player
        # Kita perluas pencariannya, jangan cuma xiaolin, tapi semua iframe yang mencurigakan
        iframe_element = None
        try:
            # Cari iframe yang punya src mengandung m3u8, token, xiaolin, atau wowhaha
            iframe_element = page.wait_for_selector(
                "iframe[src*='xiaolin3'], iframe[src*='wowhaha'], iframe[src*='m3u8'], iframe[src*='token']", 
                timeout=8000
            )
        except:
            print("   -> Iframe player spesifik tidak ketemu.")
            return None, None

        if iframe_element:
            player_referer_url = iframe_element.get_attribute("src")
            print(f"   -> Player Wrapper ditemukan: {player_referer_url}")
            
            # 2. Buka URL Player
            page.goto(player_referer_url, timeout=30000, wait_until="networkidle") 
            
            # 3. Ambil Konten HTML
            player_html = page.content()
            
            # 4. Regex Mencari Token M3U8
            # Pola 1: var m3u8 = '...'
            match = re.search(r"var\s+m3u8\s*=\s*['\"]([^'\"]+)['\"]", player_html)
            
            # Pola 2: file: "..." 
            if not match:
                match = re.search(r"file\s*:\s*['\"]([^'\"]+\.m3u8[^'\"]*)['\"]", player_html)

            # Pola 3: Link mentah https://...m3u8...
            if not match:
                match = re.search(r"(https?://[^'\"]+\.m3u8[^'\"]*)", player_html)

            if match:
                real_m3u8 = match.group(1)
                print(f"   -> SUKSES: {real_m3u8[:40]}...")
                return real_m3u8, player_referer_url
            else:
                print("   -> Gagal extract regex m3u8 dari source player.")
                return None, player_referer_url
        else:
            return None, None
                
    except Exception as e:
        print(f"   -> Error Deep Scrape: {e}")
        return None, None

def main():
    live_matches = []
    upcoming_matches = []
    seen_urls = set()
    base_url = "https://yeahscore1.com"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print("=== 1. SCRAPE DAFTAR PERTANDINGAN ===")
        try:
            page.goto(base_url + "/", timeout=60000)
            page.wait_for_timeout(4000)
            
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')

            # --- A. AMBIL LIVE MATCHES (SEMUANYA) ---
            print("Processing Live Section...")
            live_items = soup.select('.b-live-matches .collapse-match')
            for item in live_items:
                try:
                    link_tag = item.select_one('a.link-wrapper')
                    if not link_tag: continue
                    
                    full_link = base_url + link_tag['href']
                    if full_link in seen_urls: continue
                    seen_urls.add(full_link)

                    # Info Tim
                    home = clean_text(item.select_one('.left-column .name-club').get_text())
                    away = clean_text(item.select_one('.right-column .name-club').get_text())
                    
                    # Info Liga
                    group = item.find_parent(class_='collapse-group')
                    league = clean_text(group.select_one('.collapse-nav-title-name').get_text()) if group else "Live League"

                    # Info Waktu
                    inplay = item.select_one('.inplay')
                    time_display = clean_text(inplay.get_text()) if inplay else "LIVE"

                    live_matches.append({
                        "teams": f"{home} vs {away}",
                        "league": league,
                        "time": f"LIVE {time_display}",
                        "type": "LIVE",
                        "url_page": full_link
                    })
                except Exception as e: 
                    print(f"Error parse live item: {e}")
                    continue

            # --- B. AMBIL UPCOMING MATCHES ---
            print("Processing Upcoming Section...")
            upcoming_items = soup.select('.b-live-schedule .item')
            for item in upcoming_items: 
                try:
                    link_tag = item.select_one('a.link-wrapper')
                    if not link_tag: continue
                    full_link = base_url + link_tag['href']
                    
                    if full_link in seen_urls: continue
                    seen_urls.add(full_link)

                    # Info Tim (Handle nama tim atau nama event)
                    home_el = item.select_one('.left-column .name-club')
                    away_el = item.select_one('.right-column .name-club')
                    if home_el and away_el:
                        teams = f"{clean_text(home_el.get_text())} vs {clean_text(away_el.get_text())}"
                    else:
                        title_el = item.select_one('.item-title')
                        teams = clean_text(title_el.get_text()) if title_el else "Match"

                    time_val = clean_text(item.select_one('.time').get_text())
                    
                    group = item.find_parent(class_='collapse-group')
                    league = clean_text(group.select_one('.collapse-nav-title-name').get_text()) if group else "Upcoming"

                    upcoming_matches.append({
                        "teams": teams,
                        "league": league,
                        "time": time_val,
                        "type": "UPCOMING",
                        "url_page": full_link
                    })
                except: continue

            print(f"Total LIVE ditemukan: {len(live_matches)}")
            print(f"Total UPCOMING ditemukan: {len(upcoming_matches)}")

            # === 2. DEEP SCRAPING (AMBIL LINK STREAM) ===
            print("\n=== 2. MENCARI LINK STREAM ===")
            
            final_data = []

            # A. PROSES SEMUA LIVE MATCHES (TANPA LIMIT)
            print("--- Mengambil Stream LIVE Matches ---")
            for i, match in enumerate(live_matches):
                print(f"[LIVE {i+1}/{len(live_matches)}] {match['teams']}")
                
                page_extractor = context.new_page()
                real_m3u8, player_referer = get_real_stream_url(page_extractor, match['url_page'])
                
                match['stream_url'] = real_m3u8
                match['referer'] = player_referer
                final_data.append(match)
                
                page_extractor.close()

            # B. PROSES UPCOMING (LIMIT 15 AGAR TIDAK TIMEOUT)
            # Kamu bisa ubah angka 15 jadi lebih besar kalau mau ambil lebih banyak upcoming
            limit_upcoming = 15 
            print(f"\n--- Mengambil Stream UPCOMING Matches (Limit {limit_upcoming}) ---")
            
            for i, match in enumerate(upcoming_matches[:limit_upcoming]):
                print(f"[UPCOMING {i+1}/{limit_upcoming}] {match['teams']}")
                
                # Cek sekilas, kalau masih lama mainnya (misal besok), gak usah cek stream biar cepet
                # Tapi kalau mau cek semua, biarkan saja baris ini:
                
                page_extractor = context.new_page()
                real_m3u8, player_referer = get_real_stream_url(page_extractor, match['url_page'])
                
                match['stream_url'] = real_m3u8
                match['referer'] = player_referer
                final_data.append(match)
                
                page_extractor.close()

            browser.close()

        except Exception as e:
            print(f"Critical Error: {e}")
            browser.close()

    # Simpan Hasil Akhir
    with open("matches.json", "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=4)
        print("\nSelesai! Data tersimpan di matches.json")

if __name__ == "__main__":
    main()

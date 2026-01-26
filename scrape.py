import json
import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def clean_text(text):
    """Membersihkan text dari newlines dan spasi berlebih"""
    if not text: return ""
    # Mengganti semua whitespace (tab, enter, spasi ganda) menjadi 1 spasi
    return " ".join(text.split())

def get_real_stream_url(page, match_url):
    """Mencari Link M3U8 dan Referer Player"""
    try:
        print(f"   -> Membuka: {match_url}")
        page.goto(match_url, timeout=40000, wait_until="domcontentloaded")
        
        # 1. Cari Iframe Player
        try:
            iframe_element = page.wait_for_selector("iframe[src*='xiaolin3'], iframe[src*='wowhaha'], iframe[src*='m3u8=']", timeout=8000)
        except:
            return None, None

        if iframe_element:
            player_referer_url = iframe_element.get_attribute("src")
            print(f"   -> Player Wrapper: {player_referer_url}")
            
            # 2. Buka URL Player
            page.goto(player_referer_url, timeout=30000, wait_until="networkidle") # Tunggu sampai network tenang
            
            # 3. Ambil Konten HTML
            player_html = page.content()
            
            # 4. Regex Mencari Token M3U8 (Lebih fleksibel)
            # Pola 1: var m3u8 = '...'
            match = re.search(r"var\s+m3u8\s*=\s*['\"]([^'\"]+)['\"]", player_html)
            
            # Pola 2: file: "..." (JWPlayer style)
            if not match:
                match = re.search(r"file\s*:\s*['\"]([^'\"]+\.m3u8[^'\"]*)['\"]", player_html)

            # Pola 3: Cari string mentah apa saja yang berakhiran .m3u8 dan ada tokennya
            if not match:
                match = re.search(r"(https?://[^'\"]+\.m3u8[^'\"]*)", player_html)

            if match:
                real_m3u8 = match.group(1)
                print(f"   -> SUKSES: {real_m3u8[:50]}...")
                return real_m3u8, player_referer_url
            else:
                print("   -> Gagal extract m3u8.")
                return None, player_referer_url
                
    except Exception as e:
        print(f"   -> Error: {e}")
        return None, None

def main():
    all_matches = []
    seen_urls = set() # Untuk mencegah duplikat
    base_url = "https://yeahscore1.com"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print("1. Scrape List Pertandingan...")
        try:
            page.goto(base_url + "/", timeout=60000)
            page.wait_for_timeout(4000)
            
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')

            # --- AMBIL DATA LIVE MATCHES ---
            live_items = soup.select('.b-live-matches .collapse-match')
            for item in live_items:
                try:
                    link_tag = item.select_one('a.link-wrapper')
                    if not link_tag: continue
                    
                    full_link = base_url + link_tag['href']
                    
                    # Cek Duplikat
                    if full_link in seen_urls: continue
                    seen_urls.add(full_link)

                    home = clean_text(item.select_one('.left-column .name-club').get_text())
                    away = clean_text(item.select_one('.right-column .name-club').get_text())
                    league = clean_text(item.find_parent(class_='collapse-group').select_one('.collapse-nav-title-name').get_text())

                    all_matches.append({
                        "teams": f"{home} vs {away}",
                        "league": league,
                        "time": "LIVE",
                        "type": "LIVE",
                        "url_page": full_link
                    })
                except: continue

            # --- AMBIL DATA UPCOMING (Limit 20) ---
            upcoming_items = soup.select('.b-live-schedule .item')
            for item in upcoming_items[:20]: 
                try:
                    link_tag = item.select_one('a.link-wrapper')
                    if not link_tag: continue
                    
                    full_link = base_url + link_tag['href']
                    
                    # Cek Duplikat (Jangan ambil kalau sudah ada di LIVE)
                    if full_link in seen_urls: continue
                    seen_urls.add(full_link)

                    # Logic Tim
                    home_el = item.select_one('.left-column .name-club')
                    away_el = item.select_one('.right-column .name-club')
                    if home_el and away_el:
                        teams = f"{clean_text(home_el.get_text())} vs {clean_text(away_el.get_text())}"
                    else:
                        teams = clean_text(item.select_one('.item-title').get_text())

                    time_val = clean_text(item.select_one('.time').get_text())
                    league = clean_text(item.find_parent(class_='collapse-group').select_one('.collapse-nav-title-name').get_text())

                    all_matches.append({
                        "teams": teams,
                        "league": league,
                        "time": time_val,
                        "type": "UPCOMING",
                        "url_page": full_link
                    })
                except: continue

            print(f"Total Match Unik: {len(all_matches)}")

            # --- DEEP SCRAPING ---
            print("2. Mencari Link Stream...")
            
            # Kita proses semua LIVE, dan sebagian UPCOMING
            for i, match in enumerate(all_matches):
                # Batasi hanya 25 match pertama totalnya untuk hemat waktu
                if i >= 25: break 
                
                print(f"[{i+1}] {match['teams']}")
                
                # Proses jika LIVE atau ada indikasi main hari ini
                # Kita coba ambil streamnya
                page_extractor = context.new_page()
                real_m3u8, player_referer = get_real_stream_url(page_extractor, match['url_page'])
                
                match['stream_url'] = real_m3u8
                match['referer'] = player_referer
                
                page_extractor.close()
            
            browser.close()

        except Exception as e:
            print(f"Error: {e}")
            browser.close()

    with open("matches.json", "w", encoding="utf-8") as f:
        json.dump(all_matches, f, indent=4)
        print("Done.")

if __name__ == "__main__":
    main()

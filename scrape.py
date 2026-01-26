import json
import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def get_real_stream_url(page, match_url):
    """
    Mengembalikan tuple: (real_m3u8_url, player_referer_url)
    """
    try:
        print(f"   -> Membuka match: {match_url}")
        page.goto(match_url, timeout=30000, wait_until="domcontentloaded")
        
        # 1. Cari Iframe Player (sumber referer)
        try:
            # Cari iframe yang mengarah ke player xiaolin3 atau wowhaha
            iframe_element = page.wait_for_selector("iframe[src*='xiaolin3'], iframe[src*='wowhaha'], iframe[src*='m3u8=']", timeout=6000)
        except:
            print("   -> Iframe player tidak ketemu.")
            return None, None

        if iframe_element:
            # INI REFERER PENTINGNYA!
            player_referer_url = iframe_element.get_attribute("src")
            print(f"   -> Referer didapat: {player_referer_url}")
            
            # 2. Buka URL Player untuk ambil token m3u8
            page.goto(player_referer_url, timeout=30000, wait_until="domcontentloaded")
            player_html = page.content()
            
            # 3. Regex ambil variabel m3u8
            match = re.search(r"var\s+m3u8\s*=\s*'([^']+)'", player_html)
            
            if match:
                real_m3u8 = match.group(1)
                print(f"   -> Link M3U8 didapat.")
                return real_m3u8, player_referer_url
            else:
                print("   -> Gagal regex m3u8.")
                return None, player_referer_url
                
    except Exception as e:
        print(f"   -> Error: {e}")
        return None, None

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

        print("1. Scrape Daftar Match...")
        try:
            page.goto(base_url + "/", timeout=60000)
            page.wait_for_timeout(3000)
            
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')

            # --- AMBIL DATA LIVE MATCHES ---
            live_items = soup.select('.b-live-matches .collapse-match')
            for item in live_items:
                try:
                    link = item.select_one('a.link-wrapper')['href']
                    home = clean_text(item.select_one('.left-column .name-club').get_text())
                    away = clean_text(item.select_one('.right-column .name-club').get_text())
                    
                    league_el = item.find_parent(class_='collapse-group').select_one('.collapse-nav-title-name')
                    league = clean_text(league_el.get_text()) if league_el else "Live League"

                    all_matches.append({
                        "teams": f"{home} vs {away}",
                        "league": league,
                        "time": "LIVE",
                        "type": "LIVE",
                        "url_page": base_url + link
                    })
                except: continue

            # --- AMBIL DATA UPCOMING (Limit 15) ---
            upcoming_items = soup.select('.b-live-schedule .item')
            for item in upcoming_items[:15]: 
                try:
                    link = item.select_one('a.link-wrapper')['href']
                    # ... (Logika ambil nama tim sama kayak sebelumnya) ...
                    # Biar singkat saya pakai fallback title
                    title_el = item.select_one('.item-title')
                    teams = clean_text(title_el.get_text()) if title_el else "Match"
                    time_val = clean_text(item.select_one('.time').get_text())
                    
                    league_el = item.find_parent(class_='collapse-group').select_one('.collapse-nav-title-name')
                    league = clean_text(league_el.get_text()) if league_el else "Upcoming"

                    all_matches.append({
                        "teams": teams,
                        "league": league,
                        "time": time_val,
                        "type": "UPCOMING",
                        "url_page": base_url + link
                    })
                except: continue

            print(f"Total Match: {len(all_matches)}")

            # --- DEEP SCRAPING ---
            print("2. Ambil Link & Referer...")
            
            for i, match in enumerate(all_matches[:20]): # Limit 20 biar gak timeout
                print(f"[{i+1}] {match['teams']}")
                
                # Proses jika LIVE atau ada indikasi main
                page_extractor = context.new_page()
                
                # PANGGIL FUNGSI BARU
                real_m3u8, player_referer = get_real_stream_url(page_extractor, match['url_page'])
                
                match['stream_url'] = real_m3u8
                match['referer'] = player_referer # Simpan Referer Spesifik (xiaolin3...)
                
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

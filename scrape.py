import json
import re
import requests
import time
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

# URL Hosting PHP lo (BRIDGE)
PHP_BRIDGE_URL = "https://forfreetech.biz.id/status.php" 

def get_stream_via_proxy(iframe_url, referer_origin):
    # (Logika proxy sama seperti sebelumnya, tidak berubah)
    # ... Copy paste fungsi get_stream_via_proxy dari script sebelumnya di sini ...
    # Agar tidak kepanjangan, saya singkat di jawaban ini. 
    # PASTIKAN FUNGSI get_stream_via_proxy TETAP ADA!
    final_url = None
    try:
        payload = {"url": iframe_url, "referer": referer_origin}
        resp = requests.get(PHP_BRIDGE_URL, params=payload, timeout=20)
        data = resp.json()
        if data.get('status') == 'success':
            html_content = data['content']
            match = re.search(r"var\s+m3u8\s*=\s*['\"]([^'\"]+)['\"]", html_content)
            if match:
                master_url = match.group(1)
                payload_m3u8 = {"url": master_url, "referer": "https://xiaolin3.live/"}
                resp_m3u8 = requests.get(PHP_BRIDGE_URL, params=payload_m3u8, timeout=20)
                data_m3u8 = resp_m3u8.json()
                if data_m3u8.get('status') == 'success':
                    lines = data_m3u8['content'].split('\n')
                    for line in lines:
                        if line.strip().startswith("http"):
                            final_url = line.strip()
                            break
                    if not final_url: final_url = master_url
    except Exception: pass
    return final_url

def main():
    all_matches = []
    base_url = "https://yeahscore1.com"

    with sync_playwright() as p:
        # 1. SETUP BROWSER LEBIH REALISTIS
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox', 
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled', # PENTING: Anti-bot
                '--start-maximized'
            ]
        )
        
        # Atur resolusi layar PC
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        page = context.new_page()

        # PENTING: Script untuk menghilangkan jejak robot
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        print("1. Membuka Halaman Utama Yeahscore...")
        try:
            page.goto(base_url + "/", timeout=60000, wait_until="domcontentloaded")
            
            # CEK JUDUL HALAMAN (Debugging)
            page_title = page.title()
            print(f"   -> Judul Halaman: {page_title}")

            # Tunggu elemen max 20 detik
            try:
                page.wait_for_selector("a.link-wrapper", timeout=20000)
                print("   -> Elemen match ditemukan.")
            except:
                print("   -> [WARNING] Timeout menunggu elemen!")
                # AMBIL SCREENSHOT JIKA GAGAL
                page.screenshot(path="debug_error.png")
                print("   -> Screenshot disimpan: debug_error.png")

            # Parsing
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # Coba selektor alternatif jika selektor utama gagal
            link_elements = soup.select('a.link-wrapper')
            if not link_elements:
                 print("   -> Mencoba selektor alternatif...")
                 link_elements = soup.select('.item a') # Selector cadangan

            print(f"   -> Menemukan {len(link_elements)} potensi pertandingan.")

            for link in link_elements:
                try:
                    href = link.get('href', '')
                    if "match" not in href: continue # Validasi link match
                    
                    match_url = base_url + href
                    container = link.find_parent(class_=['collapse-match', 'item'])
                    if not container: continue

                    # Ambil Nama Tim
                    home_el = container.select_one('.left-column .name-club')
                    away_el = container.select_one('.right-column .name-club')
                    
                    if home_el and away_el:
                        teams = f"{home_el.get_text(strip=True)} vs {away_el.get_text(strip=True)}"
                    else:
                        title_el = container.select_one('.item-title') or container.select_one('.name-club')
                        teams = title_el.get_text(strip=True) if title_el else "Unknown"

                    is_live = bool(container.find_parent(class_='b-live-matches'))
                    match_type = "LIVE" if is_live else "UPCOMING"
                    
                    all_matches.append({
                        "type": match_type,
                        "teams": teams,
                        "url_page": match_url,
                        "stream_url": None,
                        "referer": "https://xiaolin3.live/"
                    })
                except: continue

        except Exception as e:
            print(f"Error parse: {e}")
            page.screenshot(path="debug_crash.png")

        print(f"\n2. Deep Scraping ({len(all_matches)} Match Valid)...")
        
        # Filter & Limit
        targets = [m for m in all_matches if m['type'] == 'LIVE']
        upcoming = [m for m in all_matches if m['type'] == 'UPCOMING'][:10]
        targets.extend(upcoming)
        
        final_data = []

        for i, match in enumerate(targets):
            print(f"[{i+1}] {match['teams']}")
            try:
                page_match = context.new_page()
                page_match.goto(match['url_page'], timeout=20000, wait_until="domcontentloaded")
                
                # Cari iframe
                iframe_src = None
                try:
                    page_match.wait_for_selector('iframe', timeout=5000)
                    iframes = page_match.query_selector_all("iframe")
                    for frame in iframes:
                        src = frame.get_attribute("src")
                        if src and ("wowhaha" in src or "xiaolin" in src or "embed" in src):
                            iframe_src = "https:" + src if src.startswith("//") else src
                            break
                except: pass
                
                page_match.close()

                if iframe_src:
                    token = get_stream_via_proxy(iframe_src, match['url_page'])
                    match['stream_url'] = token
                    print(f"      -> Token: {'DAPAT' if token else 'NULL'}")
                
            except Exception as e:
                print(f"      -> Skip: {e}")
            
            final_data.append(match)

        browser.close()

    with open("matches.json", "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=4)
        print("\nSelesai.")

if __name__ == "__main__":
    main()

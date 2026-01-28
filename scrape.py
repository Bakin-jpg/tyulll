import json
import re
import requests
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time

PHP_BRIDGE_URL = "https://forfreetech.biz.id/status.php"

def get_stream_via_proxy(iframe_url, referer_origin):
    final_url = None
    try:
        print(f"      -> [PROXY] Request Source Iframe...")
        payload = {"url": iframe_url, "referer": referer_origin}
        resp = requests.get(PHP_BRIDGE_URL, params=payload, timeout=20)
        data = resp.json()
        
        if data.get('status') == 'success':
            html_content = data['content']
            match = re.search(r"var\s+m3u8\s*=\s*['\"]([^'\"]+)['\"]", html_content)
            
            if match:
                master_url = match.group(1)
                print(f"      -> [PROXY] Master URL ditemukan: {master_url[:50]}...")
                
                payload_m3u8 = {"url": master_url, "referer": "https://xiaolin3.live/"}
                resp_m3u8 = requests.get(PHP_BRIDGE_URL, params=payload_m3u8, timeout=20)
                data_m3u8 = resp_m3u8.json()
                
                if data_m3u8.get('status') == 'success':
                    playlist_content = data_m3u8['content']
                    lines = playlist_content.split('\n')
                    for line in lines:
                        clean_line = line.strip()
                        if clean_line.startswith("http"):
                            final_url = clean_line
                            print("      -> [SUKSES] Final Stream URL ditemukan!")
                            break
                    if not final_url:
                        final_url = master_url
                else:
                    print(f"      -> [GAGAL] Gagal baca Master Playlist.")
            else:
                print("      -> [GAGAL] Token m3u8 tidak ditemukan.")
        else:
            print(f"      -> [ERROR] PHP Bridge Error: {data.get('message')}")
    except Exception as e:
        print(f"      -> [ERROR] Exception: {e}")
    return final_url

def main():
    all_matches = []
    base_url = "https://yeahscore1.com"

    with sync_playwright() as p:
        # Coba dengan headless false dulu untuk debugging
        browser = p.chromium.launch(
            headless=False,  # Ganti ke True setelah testing
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage'
            ]
        )
        
        context = browser.new_context(
            viewport={'width': 1366, 'height': 768},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        page = context.new_page()

        print("1. Membuka Halaman Utama Yeahscore...")
        try:
            # Coba dengan networkidle
            page.goto(base_url + "/", timeout=60000, wait_until="networkidle")
            
            # Tunggu dan screenshot untuk debugging
            page.wait_for_timeout(3000)
            page.screenshot(path='debug_homepage.png')
            print("   -> Screenshot disimpan: debug_homepage.png")
            
            # Coba beberapa selector
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # DEBUG: Print sebagian HTML untuk inspeksi
            print("   -> Sample HTML (500 chars):", html[:500])
            
            # Coba berbagai selector
            selectors = [
                'a.link-wrapper',
                'a[href*="/match/"]',
                '.item a',
                '.collapse-match a',
                '.match-item a',
                'div[class*="match"] a'
            ]
            
            link_elements = []
            for selector in selectors:
                elements = soup.select(selector)
                if elements:
                    print(f"   -> Found {len(elements)} elements with selector: {selector}")
                    link_elements.extend(elements)
                    break
            
            # Fallback: Cari semua link yang mengandung '/match/'
            if not link_elements:
                all_links = soup.find_all('a', href=True)
                for link in all_links:
                    if '/match/' in link['href']:
                        link_elements.append(link)
                print(f"   -> Found {len(link_elements)} links with '/match/' pattern")
            
            print(f"   -> Total {len(link_elements)} potensi pertandingan.")

            for link in link_elements[:10]:  # Batasi untuk testing
                try:
                    href = link.get('href', '')
                    if not href.startswith('http'):
                        match_url = base_url + href if href.startswith('/') else base_url + '/' + href
                    else:
                        match_url = href
                    
                    # Cari container pertandingan
                    container = None
                    parent = link.find_parent(['div', 'li', 'article'])
                    while parent and not container:
                        if parent.get('class'):
                            classes = ' '.join(parent.get('class', []))
                            if any(x in classes.lower() for x in ['match', 'item', 'collapse']):
                                container = parent
                                break
                        parent = parent.find_parent(['div', 'li', 'article'])
                    
                    # Ambil nama tim
                    home_el = container.select_one('.left-column .name-club, .home .name, .team-home') if container else None
                    away_el = container.select_one('.right-column .name-club, .away .name, .team-away') if container else None
                    
                    if home_el and away_el:
                        teams = f"{home_el.get_text(strip=True)} vs {away_el.get_text(strip=True)}"
                    else:
                        teams = link.get_text(strip=True) or f"Match {match_url}"
                    
                    # Cek live
                    is_live = False
                    if container:
                        live_parent = container.find_parent(class_='b-live-matches')
                        if not live_parent:
                            live_parent = container.find_parent(class_=re.compile(r'live', re.I))
                        is_live = bool(live_parent)
                    
                    match_type = "LIVE" if is_live else "UPCOMING"
                    
                    all_matches.append({
                        "type": match_type,
                        "teams": teams,
                        "url_page": match_url,
                        "stream_url": None,
                        "referer": match_url
                    })
                    print(f"   -> Added: {teams}")
                    
                except Exception as e:
                    print(f"   -> Error processing link: {e}")
                    continue

        except Exception as e:
            print(f"Error halaman utama: {e}")
            import traceback
            traceback.print_exc()

        print(f"\nTotal matches found: {len(all_matches)}")
        
        if not all_matches:
            print("Tidak ada pertandingan ditemukan. Mungkin perlu:")
            print("1. Periksa website Yeahscore masih aktif")
            print("2. Periksa selector di file debug_homepage.png")
            print("3. Coba akses manual di browser")
            browser.close()
            return

        # Lanjutkan dengan scraping deep seperti sebelumnya...
        targets = [m for m in all_matches if m['type'] == 'LIVE']
        upcoming = [m for m in all_matches if m['type'] == 'UPCOMING'][:10]
        targets.extend(upcoming)
        
        final_data = []
        
        print(f"\n2. Deep Scraping ({len(targets)} Match)...")
        
        for i, match in enumerate(targets):
            print(f"[{i+1}/{len(targets)}] {match['teams']}")
            
            try:
                page_match = context.new_page()
                page_match.goto(match['url_page'], timeout=30000, wait_until="domcontentloaded")
                page_match.wait_for_timeout(2000)
                
                iframe_src = None
                try:
                    page_match.wait_for_selector('iframe', timeout=10000)
                    iframes = page_match.query_selector_all("iframe")
                    for frame in iframes:
                        src = frame.get_attribute("src")
                        if src:
                            if src.startswith("//"):
                                src = "https:" + src
                            if any(x in src for x in ["wowhaha", "xiaolin", "embed", "player"]):
                                iframe_src = src
                                print(f"      -> Found iframe: {src[:80]}...")
                                break
                except:
                    print("      -> No iframe found within timeout")
                
                page_match.close()

                if iframe_src:
                    final_stream_url = get_stream_via_proxy(iframe_src, match['url_page'])
                    match['stream_url'] = final_stream_url
                else:
                    print("      -> Tidak ada iframe player.")

            except Exception as e:
                print(f"      -> Error: {e}")
                
            final_data.append(match)

        browser.close()

    # Simpan JSON
    with open("matches.json", "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=4)
    
    print(f"\nSelesai. Disimpan {len(final_data)} pertandingan ke matches.json")

if __name__ == "__main__":
    main()

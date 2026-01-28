import json
import re
import time
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def get_stream_token(context, iframe_url, referer):
    """
    1. Buka Iframe -> Ambil URL Wrapper (cdn-rum...).
    2. Request URL Wrapper -> Ambil URL Final (livecdn...) dari dalam isinya.
    """
    page = context.new_page()
    final_url = None

    try:
        print(f"      -> Bedah Iframe: {iframe_url[:60]}...")
        
        # --- LANGKAH 1: Request Source Iframe ---
        response = page.request.get(
            iframe_url, 
            headers={"Referer": referer}
        )
        
        wrapper_url = None
        if response.status == 200:
            html_content = response.text()
            # Regex menangkap: var m3u8 = 'https://...';
            match = re.search(r"var\s+m3u8\s*=\s*['\"]([^'\"]+)['\"]", html_content)
            if match:
                wrapper_url = match.group(1)
                print(f"      [INFO] Wrapper URL ditemukan: {wrapper_url[:40]}...")
            else:
                print("      [GAGAL] Pattern m3u8 tidak ditemukan di source iframe.")
        else:
            print(f"      [GAGAL] Iframe Status: {response.status}")

        # --- LANGKAH 2: Fetch Isi Wrapper untuk dapat Final URL ---
        if wrapper_url:
            try:
                # Request ke URL wrapper (cdn-rum...)
                # Kita pakai referer dari player (xiaolin/wowhaha) agar tidak ditolak
                m3u8_resp = page.request.get(
                    wrapper_url,
                    headers={
                        "Referer": "https://xiaolin3.live/",
                        "Origin": "https://xiaolin3.live"
                    }
                )

                if m3u8_resp.status == 200:
                    content = m3u8_resp.text()
                    # Parsing isi file M3U8 baris per baris
                    # Kita cari baris yang dimulai dengan http dan bukan komentar (#)
                    lines = content.strip().split('\n')
                    for line in lines:
                        line = line.strip()
                        if line.startswith("http"):
                            final_url = line
                            print("      [SUKSES] Final Stream URL didapatkan!")
                            break
                else:
                    print(f"      [GAGAL] Gagal fetch wrapper. Status: {m3u8_resp.status}")

            except Exception as e:
                print(f"      [ERROR] Gagal request wrapper: {e}")

    except Exception as e:
        print(f"      [ERROR] Global: {e}")
    finally:
        page.close()
    
    return final_url

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
            
            try:
                page.wait_for_selector("a.link-wrapper", timeout=15000)
                print("   -> Data website berhasil dimuat.")
            except:
                print("   -> Waktu tunggu habis, mencoba parsing apa adanya...")

            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            link_elements = soup.select('a.link-wrapper')
            print(f"   -> Menemukan {len(link_elements)} potensi pertandingan.")

            for link in link_elements:
                try:
                    match_url = base_url + link['href']
                    container = link.find_parent(class_=['collapse-match', 'item'])
                    if not container: continue

                    home_el = container.select_one('.left-column .name-club')
                    away_el = container.select_one('.right-column .name-club')
                    
                    if home_el and away_el:
                        home = home_el.get_text(strip=True)
                        away = away_el.get_text(strip=True)
                        teams = f"{home} vs {away}"
                    else:
                        title_el = container.select_one('.item-title') or container.select_one('.name-club')
                        teams = title_el.get_text(strip=True) if title_el else "Unknown Match"

                    time_el = container.select_one('.inplay') or container.select_one('.time')
                    time_raw = time_el.get_text(" ", strip=True) if time_el else ""
                    
                    is_live = False
                    parent_section = container.find_parent(class_='b-live-matches')
                    if parent_section:
                        is_live = True
                    
                    match_type = "LIVE" if is_live else "UPCOMING"
                    display_time = "LIVE NOW" if is_live else time_raw
                    
                    league = "International"
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
                    continue

        except Exception as e:
            print(f"Error parse halaman utama: {e}")

        # ==========================================
        # BAGIAN DEEP SCRAPE
        # ==========================================
        print(f"\nTotal Match Valid: {len(all_matches)}")
        
        targets = [m for m in all_matches if m['type'] == 'LIVE']
        upcoming = [m for m in all_matches if m['type'] == 'UPCOMING'][:15]
        targets.extend(upcoming)
        
        final_data = []

        for i, match in enumerate(targets):
            print(f"[{i+1}/{len(targets)}] {match['teams']} ({match['type']})")
            
            detail_page = context.new_page()
            iframe_src = None
            
            try:
                detail_page.goto(match['url_page'], timeout=15000, wait_until="domcontentloaded")
                
                try:
                    detail_page.wait_for_selector('iframe[src*="wowhaha"], iframe[src*="xiaolin"], iframe[src*="embed"]', timeout=5000)
                except: pass
                
                iframes = detail_page.query_selector_all("iframe")
                for frame in iframes:
                    src = frame.get_attribute("src")
                    if src and ("wowhaha" in src or "xiaolin" in src or "embed" in src):
                        iframe_src = src
                        if src.startswith("//"): iframe_src = "https:" + src
                        break
            except:
                print("      [SKIP] Gagal load detail page.")
            finally:
                detail_page.close()

            if iframe_src:
                token_url = get_stream_token(context, iframe_src, match['url_page'])
                match['stream_url'] = token_url
                if token_url:
                    match['referer'] = "https://xiaolin3.live/"
            else:
                print("      [INFO] Tidak ada player/iframe.")

            final_data.append(match)

        browser.close()

    with open("matches.json", "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=4)
        print("\nSelesai. Data tersimpan di matches.json")

if __name__ == "__main__":
    main()

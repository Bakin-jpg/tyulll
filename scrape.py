import json
import re
import time
import socket  # Tambahan untuk cek IP manual jika perlu
from urllib.parse import urlparse # Tambahan untuk parsing domain
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def get_stream_token(context, iframe_url, referer):
    """
    1. Buka Iframe -> Ambil URL Wrapper (cdn-rum...).
    2. Request Wrapper -> Ambil URL Final.
    3. DEBUG: Request URL Final -> Print Info Server, IP, dan Isi .ts
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
            match = re.search(r"var\s+m3u8\s*=\s*['\"]([^'\"]+)['\"]", html_content)
            if match:
                wrapper_url = match.group(1)
            else:
                print("      [GAGAL] Pattern m3u8 tidak ditemukan di source iframe.")
        else:
            print(f"      [GAGAL] Iframe Status: {response.status}")

        # --- LANGKAH 2: Fetch Wrapper ---
        if wrapper_url:
            try:
                # Header wajib buat player ini
                headers_stream = {
                    "Referer": "https://xiaolin3.live/",
                    "Origin": "https://xiaolin3.live",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }

                m3u8_resp = page.request.get(wrapper_url, headers=headers_stream)

                if m3u8_resp.status == 200:
                    content = m3u8_resp.text()
                    lines = content.strip().split('\n')
                    for line in lines:
                        line = line.strip()
                        if line.startswith("http"):
                            final_url = line
                            break
                    
                    # --- LANGKAH 3: DEBUG INFO SERVER & ISI M3U8 ---
                    if final_url:
                        print(f"      [SUKSES] Link Final didapatkan.")
                        print(f"      [DEBUG] Menganalisis Server & Konten...")
                        
                        try:
                            # Request ke URL final
                            debug_resp = page.request.get(final_url, headers=headers_stream)
                            
                            if debug_resp.status == 200:
                                # ============================================================
                                # TAMBAHAN: CEK INFO SERVER & IP
                                # ============================================================
                                print("\n" + "="*20 + " INFO SERVER & IP " + "="*20)
                                
                                # 1. Ambil Header Server
                                all_headers = debug_resp.headers
                                server_soft = all_headers.get("server", "Hidden/Unknown")
                                content_type = all_headers.get("content-type", "-")
                                
                                print(f"      [SERVER HEADER]   : {server_soft}")
                                print(f"      [CONTENT TYPE]    : {content_type}")

                                # 2. Ambil IP Address
                                # Playwright APIResponse terkadang tidak mengekspos IP langsung jika lewat proxy internal,
                                # jadi kita gunakan fallback socket python murni agar akurat.
                                server_ip = "Unknown"
                                try:
                                    # Cara 1: Coba fitur Playwright (tersedia di versi baru)
                                    addr = debug_resp.server_addr()
                                    if addr:
                                        server_ip = addr['ipAddress']
                                        print(f"      [IP (Playwright)] : {server_ip}:{addr['port']}")
                                    else:
                                        raise Exception("No info")
                                except:
                                    # Cara 2: Fallback pakai Socket DNS Lookup
                                    try:
                                        parsed_uri = urlparse(final_url)
                                        domain = parsed_uri.netloc.split(':')[0] # Hapus port jika ada
                                        server_ip = socket.gethostbyname(domain)
                                        print(f"      [IP (DNS Lookup)] : {server_ip}")
                                    except Exception as dns_err:
                                        print(f"      [IP ERROR]        : Gagal resolve ({dns_err})")

                                print("="*56)
                                # ============================================================

                                debug_content = debug_resp.text()
                                print("\n" + "="*20 + " ISI FILE M3U8 " + "="*20)
                                preview_lines = debug_content.split('\n')[:10] 
                                print('\n'.join(preview_lines))
                                print("... (dan seterusnya)")
                                print("="*55 + "\n")
                            else:
                                print(f"      [DEBUG ERROR] Gagal baca isi final m3u8. Status: {debug_resp.status}")
                        except Exception as d:
                            print(f"      [DEBUG ERROR] {d}")

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
            except: pass

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
                    if container.find_parent(class_='b-live-matches'):
                        is_live = True
                    
                    match_type = "LIVE" if is_live else "UPCOMING"
                    display_time = "LIVE NOW" if is_live else time_raw
                    
                    all_matches.append({
                        "type": match_type,
                        "teams": teams,
                        "time_display": display_time,
                        "url_page": match_url,
                        "stream_url": None,
                        "referer": base_url
                    })
                except: continue

        except Exception as e:
            print(f"Error parse halaman utama: {e}")

        # ==========================================
        # BAGIAN DEEP SCRAPE
        # ==========================================
        print(f"\nTotal Match Valid: {len(all_matches)}")
        
        targets = [m for m in all_matches if m['type'] == 'LIVE']
        upcoming = [m for m in all_matches if m['type'] == 'UPCOMING'][:5] 
        targets.extend(upcoming)
        
        final_data = []

        for i, match in enumerate(targets):
            print(f"[{i+1}/{len(targets)}] {match['teams']} ({match['type']})")
            
            detail_page = context.new_page()
            iframe_src = None
            
            try:
                detail_page.goto(match['url_page'], timeout=15000, wait_until="domcontentloaded")
                
                try:
                    detail_page.wait_for_selector('iframe[src*="wowhaha"], iframe[src*="xiaolin"]', timeout=3000)
                except: pass
                
                iframes = detail_page.query_selector_all("iframe")
                for frame in iframes:
                    src = frame.get_attribute("src")
                    if src and ("wowhaha" in src or "xiaolin" in src or "embed" in src):
                        iframe_src = src
                        if src.startswith("//"): iframe_src = "https:" + src
                        break
            except: pass
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

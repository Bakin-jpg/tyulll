import json
import re
import requests # Kita butuh requests buat nembak PHP
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

# ==========================================
# CONFIG: GANTI DENGAN URL PHP DI HOSTING INDO KAMU
# ==========================================
PHP_BRIDGE_URL = "https://forfreetech.biz.id/status.php" 

def get_stream_via_proxy(iframe_url, referer_origin):
    """
    Menggunakan Hosting Indo untuk bypass geoblock dan mengambil Final URL.
    Flow:
    1. Python -> PHP (Request Iframe Source)
    2. PHP (IP Indo) -> Server Video
    3. Python (Regex) -> Dapat Master M3U8
    4. Python -> PHP (Request Master M3U8 Content)
    5. Python -> Dapat Final URL (Chunks)
    """
    final_url = None
    
    try:
        print(f"      -> [PROXY] Request Source Iframe...")
        
        # 1. Minta PHP ambilkan Source Code Iframe
        payload = {"url": iframe_url, "referer": referer_origin}
        resp = requests.get(PHP_BRIDGE_URL, params=payload, timeout=20)
        data = resp.json()
        
        if data.get('status') == 'success':
            html_content = data['content']
            
            # 2. Regex cari variabel m3u8
            match = re.search(r"var\s+m3u8\s*=\s*['\"]([^'\"]+)['\"]", html_content)
            
            if match:
                master_url = match.group(1)
                print(f"      -> [PROXY] Master URL didapat. Mencari Final URL...")
                
                # 3. Minta PHP ambilkan isi dari Master M3U8 (Resolve Chunks)
                # Referer diganti jadi xiaolin/domain player agar valid
                payload_m3u8 = {"url": master_url, "referer": "https://xiaolin3.live/"}
                resp_m3u8 = requests.get(PHP_BRIDGE_URL, params=payload_m3u8, timeout=20)
                data_m3u8 = resp_m3u8.json()
                
                if data_m3u8.get('status') == 'success':
                    playlist_content = data_m3u8['content']
                    
                    # 4. Parsing isi playlist untuk cari URL http yang asli
                    lines = playlist_content.split('\n')
                    for line in lines:
                        clean_line = line.strip()
                        # Biasanya URL chunks diawali http/https dan tidak diawali #
                        if clean_line.startswith("http"):
                            final_url = clean_line
                            print("      -> [SUKSES] Final Stream URL ditemukan!")
                            break
                    
                    # Fallback: Kalau isi playlist cuma relatif path atau master doang
                    if not final_url:
                        # Logika tambahan jika redirect atau format beda
                        final_url = master_url 
                else:
                    print(f"      -> [GAGAL] Gagal baca Master Playlist.")
            else:
                print("      -> [GAGAL] Token m3u8 tidak ditemukan di source iframe.")
        else:
            print(f"      -> [ERROR] PHP Bridge Error: {data.get('message')}")
            
    except Exception as e:
        print(f"      -> [ERROR] Exception: {e}")

    return final_url

def main():
    all_matches = []
    base_url = "https://yeahscore1.com"

    with sync_playwright() as p:
        # Browser biasa (IP GitHub Action / US) untuk buka web utama
        # Web utamanya (Yeahscore) biasanya tidak butuh IP Indo
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        context = browser.new_context()
        page = context.new_page()

        print("1. Membuka Halaman Utama Yeahscore...")
        try:
            page.goto(base_url + "/", timeout=60000, wait_until="domcontentloaded")
            
            # Parsing HTML Dasar
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            link_elements = soup.select('a.link-wrapper')
            print(f"   -> Menemukan {len(link_elements)} potensi pertandingan.")

            for link in link_elements:
                try:
                    match_url = base_url + link['href']
                    container = link.find_parent(class_=['collapse-match', 'item'])
                    if not container: continue

                    # Ambil data Tim, Waktu, Liga (Sama seperti script sebelumnya)
                    home_el = container.select_one('.left-column .name-club')
                    away_el = container.select_one('.right-column .name-club')
                    teams = f"{home_el.get_text(strip=True)} vs {away_el.get_text(strip=True)}" if home_el and away_el else "Unknown"

                    # Deteksi Live
                    is_live = bool(container.find_parent(class_='b-live-matches'))
                    match_type = "LIVE" if is_live else "UPCOMING"
                    
                    # Simpan data dasar
                    all_matches.append({
                        "type": match_type,
                        "teams": teams,
                        "url_page": match_url,
                        "stream_url": None,
                        "referer": "https://xiaolin3.live/" # Default referer player
                    })
                except: continue

        except Exception as e:
            print(f"Error halaman utama: {e}")

        # Filter Target
        targets = [m for m in all_matches if m['type'] == 'LIVE']
        upcoming = [m for m in all_matches if m['type'] == 'UPCOMING'][:10]
        targets.extend(upcoming)
        
        final_data = []

        print(f"\n2. Deep Scraping ({len(targets)} Match)...")
        
        for i, match in enumerate(targets):
            print(f"[{i+1}/{len(targets)}] {match['teams']}")
            
            # Langkah 1: Buka Page Match pake Playwright (IP US gak masalah buat buka page ini)
            try:
                page_match = context.new_page()
                page_match.goto(match['url_page'], timeout=15000, wait_until="domcontentloaded")
                
                iframe_src = None
                try:
                    # Cari iframe player
                    page_match.wait_for_selector('iframe', timeout=5000)
                    iframes = page_match.query_selector_all("iframe")
                    for frame in iframes:
                        src = frame.get_attribute("src")
                        if src and ("wowhaha" in src or "xiaolin" in src or "embed" in src):
                            iframe_src = "https:" + src if src.startswith("//") else src
                            break
                except: pass
                
                page_match.close()

                # Langkah 2: Jika iframe ketemu, Gunakan Proxy PHP Indo buat ambil token
                if iframe_src:
                    # Ini bagian kuncinya. Kita oper ke fungsi proxy
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
        print("\nSelesai.")

if __name__ == "__main__":
    main()

import json
import re
import requests
import time
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

# ==========================================
# CONFIG
# ==========================================
PHP_BRIDGE_URL = "https://forfreetech.biz.id/status.php" 

def check_bridge_ip():
    """
    Fungsi untuk mengecek apakah script berjalan menggunakan IP Hosting Indo
    melalui perantara PHP Bridge.
    """
    print("\n[INIT] Mengecek IP Address via PHP Bridge...")
    try:
        # Kita minta PHP untuk menembak API Cek IP
        payload = {
            "url": "https://api.ipify.org?format=json",
            "referer": "https://google.com"
        }
        resp = requests.get(PHP_BRIDGE_URL, params=payload, timeout=15)
        data = resp.json()
        
        if data.get('status') == 'success':
            # Parsing isi content yang didapat PHP
            content = json.loads(data['content'])
            ip = content.get('ip')
            print(f"      -> [OK] IP Bridge Terdeteksi: {ip}")
            return True
        else:
            print(f"      -> [ERROR] Bridge merespon error: {data.get('message')}")
            return False
            
    except Exception as e:
        print(f"      -> [FATAL] Gagal menghubungi PHP Bridge: {e}")
        return False

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
                # print(f"      -> [PROXY] Master URL: {master_url}")
                
                # Resolve master content
                payload_m3u8 = {"url": master_url, "referer": "https://xiaolin3.live/"}
                resp_m3u8 = requests.get(PHP_BRIDGE_URL, params=payload_m3u8, timeout=20)
                data_m3u8 = resp_m3u8.json()
                
                if data_m3u8.get('status') == 'success':
                    playlist = data_m3u8['content']
                    for line in playlist.split('\n'):
                        if line.strip().startswith("http"):
                            final_url = line.strip()
                            print("      -> [SUKSES] Final Stream URL didapat!")
                            break
                    if not final_url: final_url = master_url
                else:
                    final_url = master_url # Fallback
            else:
                print("      -> [GAGAL] Token m3u8 tidak ditemukan.")
    except Exception as e:
        print(f"      -> [ERROR] {e}")

    return final_url

def main():
    # 1. Cek IP dulu
    check_bridge_ip()

    all_matches = []
    base_url = "https://yeahscore1.com"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print("\n1. Membuka Halaman Utama Yeahscore...")
        try:
            page.goto(base_url + "/", timeout=60000)
            page.wait_for_timeout(5000) # Tunggu loading vue component
            
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # Selector utama: Link wrapper
            link_elements = soup.select('a.link-wrapper')
            print(f"   -> Menemukan {len(link_elements)} item mentah.")

            for link in link_elements:
                try:
                    match_url = base_url + link['href']
                    
                    # LOGIKA BARU BERDASARKAN HTML KAMU:
                    # Cek Parent apakah dia LIVE (collapse-match) atau UPCOMING (item)
                    
                    # 1. Coba cari parent item biasa (Upcoming/Schedule)
                    container = link.find_parent(class_='item')
                    match_type = "UPCOMING"
                    
                    # 2. Jika tidak ada, coba cari parent collapse-match (Live)
                    if not container:
                        container = link.find_parent(class_='collapse-match')
                        match_type = "LIVE"
                    
                    if not container:
                        continue # Skip jika tidak punya parent valid

                    # Ambil Nama Tim (Strukturnya beda dikit antara live dan upcoming)
                    # Kita pakai selector css yang mencakup keduanya
                    home_el = container.select_one('.left-column .name-club')
                    away_el = container.select_one('.right-column .name-club')

                    # Jika di dalam .left-column tidak ketemu, coba cari siblings (kadang text doang)
                    if not home_el or not away_el:
                         # Fallback ambil text dari area judul
                         full_text = container.get_text(separator=" ", strip=True)
                         # Simpan text kasar dulu kalau gagal parse tim
                         teams = full_text 
                    else:
                        teams = f"{home_el.get_text(strip=True)} vs {away_el.get_text(strip=True)}"

                    # Validasi Live via Icon/Parent Class
                    if container.find_parent(class_='b-live-matches') or "LIVE" in match_type:
                        match_type = "LIVE"

                    # Debug print untuk memastikan data masuk
                    # print(f"      Found: [{match_type}] {teams}")

                    all_matches.append({
                        "type": match_type,
                        "teams": teams,
                        "url_page": match_url,
                        "stream_url": None,
                        "referer": "https://xiaolin3.live/"
                    })
                except Exception as e:
                    continue

        except Exception as e:
            print(f"Error halaman utama: {e}")

        # Filter: Prioritaskan Live, kalau kosong ambil Upcoming
        targets = [m for m in all_matches if m['type'] == 'LIVE']
        
        # DEBUG: Jika Live 0, ambil 5 upcoming buat ngetes apakah script jalan
        if len(targets) == 0:
            print("   -> Tidak ada pertandingan LIVE, mengambil 5 UPCOMING untuk tes...")
            targets = [m for m in all_matches if m['type'] == 'UPCOMING'][:5]
        
        final_data = []

        print(f"\n2. Deep Scraping ({len(targets)} Match)...")
        
        for i, match in enumerate(targets):
            print(f"[{i+1}/{len(targets)}] {match['teams']}")
            
            try:
                page_match = context.new_page()
                page_match.goto(match['url_page'], timeout=15000)
                
                # Cari iframe
                iframe_src = None
                try:
                    page_match.wait_for_selector('iframe', timeout=5000)
                    iframes = page_match.query_selector_all("iframe")
                    for frame in iframes:
                        src = frame.get_attribute("src")
                        # Filter iframe pemain video
                        if src and ("xiaolin" in src or "wowhaha" in src or "embed" in src):
                            iframe_src = "https:" + src if src.startswith("//") else src
                            break
                except: pass
                
                page_match.close()

                if iframe_src:
                    stream = get_stream_via_proxy(iframe_src, match['url_page'])
                    match['stream_url'] = stream
                else:
                    print("      -> Tidak ada iframe player.")

            except Exception as e:
                print(f"      -> Error page match: {e}")
                
            final_data.append(match)

        browser.close()

    # Simpan JSON
    with open("matches.json", "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=4)
        print("\nSelesai.")

if __name__ == "__main__":
    main()

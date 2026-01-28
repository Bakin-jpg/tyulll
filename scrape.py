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
    print("\n[INIT] Mengecek IP Address via PHP Bridge...")
    try:
        payload = {"url": "https://api.ipify.org?format=json", "referer": "https://google.com"}
        resp = requests.get(PHP_BRIDGE_URL, params=payload, timeout=15)
        data = resp.json()
        if data.get('status') == 'success':
            content = json.loads(data['content'])
            print(f"      -> [OK] IP Bridge: {content.get('ip')}")
            return True
    except:
        print("      -> [WARNING] Gagal cek IP, lanjut terus...")
    return False

def get_stream_via_proxy(iframe_url, referer_origin):
    # (Fungsi ini sama seperti sebelumnya, tidak berubah)
    final_url = None
    try:
        # print(f"      -> [PROXY] Resolving Iframe: {iframe_url}...")
        payload = {"url": iframe_url, "referer": referer_origin}
        resp = requests.get(PHP_BRIDGE_URL, params=payload, timeout=20)
        data = resp.json()
        
        if data.get('status') == 'success':
            match = re.search(r"var\s+m3u8\s*=\s*['\"]([^'\"]+)['\"]", data['content'])
            if match:
                master_url = match.group(1)
                payload_m3u8 = {"url": master_url, "referer": "https://xiaolin3.live/"}
                resp_m3u8 = requests.get(PHP_BRIDGE_URL, params=payload_m3u8, timeout=20)
                if resp_m3u8.json().get('status') == 'success':
                    playlist = resp_m3u8.json()['content']
                    for line in playlist.split('\n'):
                        if line.strip().startswith("http"):
                            final_url = line.strip()
                            break
                    if not final_url: final_url = master_url
    except Exception as e:
        print(f"      -> [ERROR Proxy] {e}")
    return final_url

def parse_main_page(html):
    soup = BeautifulSoup(html, 'html.parser')
    matches_data = []

    # 1. Loop per "Group" (Biasanya mewakili Liga/Kompetisi)
    # Class 'collapse-group' membungkus Header Liga + List Pertandingan
    league_groups = soup.select('.collapse-group')
    
    print(f"   -> Menemukan {len(league_groups)} grup liga.")

    for group in league_groups:
        # A. Ambil Nama Liga
        league_el = group.select_one('.collapse-nav-title-name, .collapse-nav-title h3')
        league_name = league_el.get_text(strip=True) if league_el else "Unknown League"

        # B. Cari semua item match dalam grup ini
        # Live matches pakai class 'collapse-match', Upcoming pakai class 'item'
        match_items = group.select('.collapse-match, .item')

        for item in match_items:
            try:
                # -- 1. Link & URL --
                link = item.select_one('a.link-wrapper')
                if not link: continue
                match_url = "https://yeahscore1.com" + link['href']

                # -- 2. Waktu & Status --
                time_el = item.select_one('.time')
                match_time = time_el.get_text(strip=True) if time_el else ""
                
                # Cek tanda-tanda status
                status_el = item.select_one('span[title="Not Started"]') # Biasanya ada "NS"
                is_ns = True if status_el else False
                
                # Cek apakah tanggal ada di text waktu (misal "Jan 28, 20:00") -> Upcoming
                has_date = len(match_time) > 6 
                
                # Tentukan Type
                if is_ns or has_date:
                    match_type = "UPCOMING"
                else:
                    match_type = "LIVE"

                # -- 3. Nama Tim (Parsing lebih rapi) --
                home_team = "Unknown"
                away_team = "Unknown"
                
                # Coba struktur standar (Kiri vs Kanan)
                left_col = item.select_one('.left-column .name-club')
                right_col = item.select_one('.right-column .name-club')
                
                if left_col and right_col:
                    home_team = left_col.get_text(strip=True)
                    away_team = right_col.get_text(strip=True)
                    teams_str = f"{home_team} vs {away_team}"
                else:
                    # Struktur Single Title (misal Tennis / Event khusus)
                    # Ambil text dari .name-club yang muncul, atau collapse-nav-title
                    single_title = item.select_one('.name-club, .collapse-nav-title-name')
                    if single_title:
                        teams_str = single_title.get_text(strip=True)
                    else:
                        teams_str = "Event Unknown"

                # Bersihkan nama tim dari kata "Watch Now" atau jam jika kebawa
                teams_str = teams_str.replace("Watch Now", "").strip()

                matches_data.append({
                    "league": league_name,
                    "type": match_type,
                    "time": match_time,
                    "teams": teams_str,
                    "url_page": match_url,
                    "stream_url": None,
                    "referer": "https://xiaolin3.live/"
                })
            except Exception as e:
                continue
                
    return matches_data

def main():
    check_bridge_ip()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 ...")
        page = context.new_page()

        print("\n1. Membuka Halaman Utama...")
        page.goto("https://yeahscore1.com/", timeout=60000)
        page.wait_for_timeout(5000) # Tunggu render vue
        
        # Parsing HTML
        html = page.content()
        all_matches = parse_main_page(html)
        print(f"   -> Total Match Terdeteksi: {len(all_matches)}")

        # Filter: Hanya ambil LIVE untuk di-scrape stream-nya
        # (Opsional: ambil upcoming juga kalau mau disimpan datanya tanpa link stream)
        live_targets = [m for m in all_matches if m['type'] == 'LIVE']
        
        # Jika LIVE kosong, ambil top 5 upcoming untuk demo data
        process_targets = live_targets
        if not process_targets:
            print("   -> Tidak ada LIVE. Mengambil sample UPCOMING...")
            process_targets = [m for m in all_matches if m['type'] == 'UPCOMING'][:5]

        print(f"\n2. Deep Scraping ({len(process_targets)} Match)...")
        
        for i, match in enumerate(process_targets):
            print(f"[{i+1}/{len(process_targets)}] {match['teams']} ({match['type']})")
            
            try:
                # Buka halaman match untuk cari iframe
                p_match = context.new_page()
                p_match.goto(match['url_page'], timeout=15000)
                
                iframe_src = None
                try:
                    p_match.wait_for_selector('iframe', timeout=4000)
                    for frame in p_match.query_selector_all("iframe"):
                        src = frame.get_attribute("src")
                        if src and ("xiaolin" in src or "wowhaha" in src or "embed" in src):
                            iframe_src = "https:" + src if src.startswith("//") else src
                            break
                except: pass
                p_match.close()

                if iframe_src:
                    stream = get_stream_via_proxy(iframe_src, match['url_page'])
                    match['stream_url'] = stream
                    if stream:
                        print(f"      -> Stream OK")
                else:
                    print("      -> No Iframe")
                    
            except Exception as e:
                print(f"      -> Error: {e}")

            # Update data asli di all_matches dengan hasil stream
            # (Karena dictionary di python pass-by-reference, object di all_matches ikut berubah)

        browser.close()

    # Simpan Hasil Lengkap (Live & Upcoming)
    # Urutkan biar yang LIVE paling atas
    all_matches.sort(key=lambda x: x['type'] == 'UPCOMING') 
    
    with open("matches.json", "w", encoding="utf-8") as f:
        json.dump(all_matches, f, indent=4)
        print("\nSelesai. Data disimpan ke matches.json")

if __name__ == "__main__":
    main()

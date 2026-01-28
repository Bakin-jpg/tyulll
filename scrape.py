import json
import re
import requests
import time
from datetime import datetime, timedelta
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
    final_url = None
    try:
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
        pass
    return final_url

def format_full_date(raw_time_str):
    """
    Mengubah format "Jan 28, 20:00" atau "20:00" menjadi "28 January 2025 20:00"
    """
    try:
        now = datetime.now()
        current_year = now.year
        
        # Bersihkan string
        clean_time = raw_time_str.strip().replace(",", "") # Hapus koma
        
        # Kasus 1: Ada Bulan dan Tanggal (e.g., "Jan 28 20:00")
        # Regex menangkap: (Jan) (28) (20:00)
        match_full = re.search(r"([A-Za-z]+)\s+(\d+)\s+(\d{2}:\d{2})", clean_time)
        
        if match_full:
            month_str = match_full.group(1)
            day_str = match_full.group(2)
            time_str = match_full.group(3)
            
            # Parse ke datetime object
            dt_obj = datetime.strptime(f"{day_str} {month_str} {current_year} {time_str}", "%d %b %Y %H:%M")
            return dt_obj.strftime("%d %B %Y %H:%M")

        # Kasus 2: Cuma Jam (e.g., "20:00" atau "00:00") -> Anggap Hari Ini
        match_time_only = re.search(r"(\d{2}:\d{2})", clean_time)
        if match_time_only:
            time_str = match_time_only.group(1)
            # Gabungkan tanggal hari ini dengan jam tersebut
            dt_obj = datetime.strptime(f"{now.strftime('%d %B %Y')} {time_str}", "%d %B %Y %H:%M")
            return dt_obj.strftime("%d %B %Y %H:%M")
            
        return raw_time_str # Return as is kalau gagal
    except:
        return raw_time_str

def parse_main_page(html):
    soup = BeautifulSoup(html, 'html.parser')
    matches_data = []

    league_groups = soup.select('.collapse-group')
    
    print(f"   -> Menemukan {len(league_groups)} grup liga.")

    for group in league_groups:
        # 1. Ambil Nama Liga
        league_el = group.select_one('.collapse-nav-title-name, .collapse-nav-title h3')
        league_name = league_el.get_text(strip=True) if league_el else ""
        
        # Fix jika nama liga kosong atau aneh
        if not league_name or league_name == "Today" or "null" in str(league_el):
            # Coba cari parent category (misal section Football)
            # Tapi untuk simple fix, kita namakan "Others / Friendly"
            league_name = "Others / International"

        match_items = group.select('.collapse-match, .item')

        for item in match_items:
            try:
                # Link
                link = item.select_one('a.link-wrapper')
                if not link: continue
                match_url = "https://yeahscore1.com" + link['href']

                # Waktu
                time_el = item.select_one('.time')
                raw_time = time_el.get_text(" ", strip=True) if time_el else ""
                
                # FORMAT TANGGAL LENGKAP
                formatted_time = format_full_date(raw_time)
                
                # Tipe
                status_el = item.select_one('span[title="Not Started"]')
                match_type = "UPCOMING" if (status_el or len(raw_time) > 6) else "LIVE"

                # 3. NAMA TIM (LOGIC BARU)
                home_team = None
                away_team = None
                teams_str = "Unknown vs Unknown"

                # Cari elemen kolom kiri dan kanan
                left_col = item.select_one('.left-column .name-club')
                right_col = item.select_one('.right-column .name-club')

                if left_col and right_col:
                    # Kasus Standard: Tim A vs Tim B
                    teams_str = f"{left_col.get_text(strip=True)} vs {right_col.get_text(strip=True)}"
                else:
                    # Kasus Tennis/Single Event (Margaret Court Arena)
                    # Biasanya ada di div.text-center atau div.middle-column
                    center_text = item.select_one('.text-center span, .middle-column')
                    if center_text:
                        # Ambil teks, buang kata 'vs' jika ada
                        raw_center = center_text.get_text(strip=True)
                        if raw_center.lower() != "vs":
                            teams_str = raw_center
                        else:
                            # Kalau isinya cuma 'vs', berarti struktur error, coba ambil title atribut img
                            imgs = item.select('img.team-logo')
                            if len(imgs) >= 2:
                                teams_str = f"{imgs[0].get('alt', 'Home')} vs {imgs[1].get('alt', 'Away')}"
                    
                    # Fallback Terakhir: Ambil text dari collapse-nav-title match ini
                    if teams_str == "Unknown vs Unknown":
                         title_fallback = item.select_one('.collapse-nav-title-name, .name-club')
                         if title_fallback:
                             teams_str = title_fallback.get_text(strip=True)

                # Bersihkan kata "Watch Now"
                teams_str = teams_str.replace("Watch Now", "").strip()

                matches_data.append({
                    "league": league_name,
                    "type": match_type,
                    "time": formatted_time, # Hasil format baru
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
        # Headless TRUE agar cepat
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        page = context.new_page()

        print("\n1. Membuka Halaman Utama...")
        try:
            page.goto("https://yeahscore1.com/", timeout=60000)
            page.wait_for_timeout(5000) 
            
            html = page.content()
            all_matches = parse_main_page(html)
            print(f"   -> Total Match: {len(all_matches)}")

            # Prioritas LIVE
            live_targets = [m for m in all_matches if m['type'] == 'LIVE']
            
            # Jika tidak ada LIVE, ambil 5 Upcoming teratas untuk data dummy
            process_targets = live_targets
            if not process_targets:
                print("   -> Tidak ada LIVE. Mengambil sample UPCOMING...")
                # Sortir upcoming berdasarkan waktu terdekat (opsional)
                process_targets = [m for m in all_matches if m['type'] == 'UPCOMING'][:5]

            print(f"\n2. Deep Scraping ({len(process_targets)} Match)...")
            
            for i, match in enumerate(process_targets):
                print(f"[{i+1}/{len(process_targets)}] {match['teams']} ({match['time']})")
                
                try:
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
                        if stream: print(f"      -> Stream OK")
                    else:
                        print("      -> No Iframe")
                        
                except Exception as e:
                    print(f"      -> Error: {e}")

        except Exception as e:
            print(f"Main Error: {e}")
        finally:
            browser.close()

    # Sort: Live diatas, lalu urutkan tanggal
    all_matches.sort(key=lambda x: (x['type'] == 'UPCOMING', x['time'])) 
    
    with open("matches.json", "w", encoding="utf-8") as f:
        json.dump(all_matches, f, indent=4)
        print("\nSelesai. Data disimpan ke matches.json")

if __name__ == "__main__":
    main()

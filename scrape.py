import json
import re
import requests
import time
from datetime import datetime
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
    try:
        now = datetime.now()
        current_year = now.year
        # Bersihkan string dari enter/spasi berlebih
        clean_time = " ".join(raw_time_str.split()).replace(",", "")
        
        # Regex: (Jan) (28) (20:00)
        match_full = re.search(r"([A-Za-z]+)\s+(\d+)\s+(\d{2}:\d{2})", clean_time)
        
        if match_full:
            month_str = match_full.group(1)
            day_str = match_full.group(2)
            time_str = match_full.group(3)
            dt_obj = datetime.strptime(f"{day_str} {month_str} {current_year} {time_str}", "%d %b %Y %H:%M")
            return dt_obj.strftime("%d %B %Y %H:%M")

        # Regex: Cuma Jam (20:00) -> Hari Ini
        match_time_only = re.search(r"(\d{2}:\d{2})", clean_time)
        if match_time_only:
            time_str = match_time_only.group(1)
            dt_obj = datetime.strptime(f"{now.strftime('%d %B %Y')} {time_str}", "%d %B %Y %H:%M")
            return dt_obj.strftime("%d %B %Y %H:%M")
            
        return raw_time_str
    except:
        return raw_time_str

def parse_main_page(html):
    soup = BeautifulSoup(html, 'html.parser')
    
    # Dictionary untuk Mencegah Duplikasi
    unique_matches = {}

    league_groups = soup.select('.collapse-group')
    print(f"   -> Scanning {len(league_groups)} grup section...")

    for group in league_groups:
        # Ambil Nama Liga
        league_el = group.select_one('.collapse-nav-title-name, .collapse-nav-title h3')
        raw_league = league_el.get_text(strip=True) if league_el else ""
        
        is_generic_league = False
        # Filter nama liga "sampah"
        if not raw_league or raw_league in ["Today", "Hot Matches", "Tomorrow", "Schedule", "Upcoming schedule today"] or "Matches" in raw_league:
            league_name = "Others / International"
            is_generic_league = True
        else:
            league_name = raw_league

        match_items = group.select('.collapse-match, .item')

        for item in match_items:
            try:
                link = item.select_one('a.link-wrapper')
                if not link: continue
                match_url = "https://yeahscore1.com" + link['href']

                # --- LOGIC DEDUPLIKASI ---
                if match_url in unique_matches:
                    existing_league = unique_matches[match_url]['league']
                    if existing_league != "Others / International":
                        continue 
                    if is_generic_league:
                        continue 

                # --- PARSE WAKTU ---
                time_el = item.select_one('.time')
                if time_el:
                    # Ambil text, gabungkan jika ada span lain (misal tanggal dan jam terpisah)
                    raw_time = time_el.get_text(" ", strip=True) 
                    # Kadang tanggal ada di sibling element sebelumnya (item-status)
                    parent_status = item.select_one('.item-status')
                    if parent_status:
                        raw_time = parent_status.get_text(" ", strip=True)
                else:
                    raw_time = ""
                
                formatted_time = format_full_date(raw_time)
                
                # --- PARSE TYPE ---
                status_el = item.select_one('span[title="Not Started"]')
                # Jika ada "NS" atau teks tanggal panjang -> UPCOMING
                match_type = "UPCOMING" if (status_el or len(raw_time) > 6) else "LIVE"

                # --- PARSE TEAMS (LOGIC PERBAIKAN) ---
                teams_str = "Unknown"
                
                # 1. Cek Layout Desktop (Kiri vs Kanan)
                left_col = item.select_one('.left-column .name-club')
                right_col = item.select_one('.right-column .name-club')

                # 2. Cek Layout Mobile/Stacked (Dua tim di dalam .right-column)
                # Ini yang memperbaiki kasus "Unknown" di JSON kamu sebelumnya
                right_col_wrapper = item.select_one('.right-column')
                stacked_teams = right_col_wrapper.select('.name-club') if right_col_wrapper else []

                if left_col and right_col:
                    # Layout Standar
                    teams_str = f"{left_col.get_text(strip=True)} vs {right_col.get_text(strip=True)}"
                
                elif len(stacked_teams) >= 2:
                    # Layout Mobile (Tim menumpuk)
                    teams_str = f"{stacked_teams[0].get_text(strip=True)} vs {stacked_teams[1].get_text(strip=True)}"
                
                else:
                    # 3. Cek Single Title (Tennis / Event Lain)
                    # Cari sembarang class .name-club yang ada
                    single_name = item.select_one('.name-club')
                    if single_name:
                        teams_str = single_name.get_text(strip=True)
                    else:
                        # Fallback Judul Group/Match
                        center_text = item.select_one('.text-center span, .middle-column')
                        if center_text and "vs" not in center_text.get_text().lower():
                            teams_str = center_text.get_text(strip=True)
                        else:
                            title_fallback = item.select_one('.collapse-nav-title-name')
                            if title_fallback: teams_str = title_fallback.get_text(strip=True)

                # Bersihkan string
                teams_str = teams_str.replace("Watch Now", "").strip()

                # Simpan Data
                unique_matches[match_url] = {
                    "league": league_name,
                    "type": match_type,
                    "time": formatted_time,
                    "teams": teams_str,
                    "url_page": match_url,
                    "stream_url": None,
                    "referer": "https://xiaolin3.live/"
                }
            except Exception:
                continue
    
    return list(unique_matches.values())

def main():
    check_bridge_ip()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        page = context.new_page()

        print("\n1. Membuka Halaman Utama...")
        try:
            page.goto("https://yeahscore1.com/", timeout=60000)
            page.wait_for_timeout(5000)
            
            html = page.content()
            all_matches = parse_main_page(html)
            print(f"   -> Total Match Unik: {len(all_matches)}")

            live_targets = [m for m in all_matches if m['type'] == 'LIVE']
            process_targets = live_targets if live_targets else [m for m in all_matches if m['type'] == 'UPCOMING'][:5]

            print(f"\n2. Deep Scraping ({len(process_targets)} Match)...")
            
            for i, match in enumerate(process_targets):
                print(f"[{i+1}/{len(process_targets)}] {match['teams']}")
                try:
                    p_match = context.new_page()
                    p_match.goto(match['url_page'], timeout=15000)
                    iframe_src = None
                    try:
                        p_match.wait_for_selector('iframe', timeout=4000)
                        frames = p_match.query_selector_all("iframe")
                        for frame in frames:
                            src = frame.get_attribute("src")
                            if src and ("xiaolin" in src or "wowhaha" in src or "embed" in src):
                                iframe_src = "https:" + src if src.startswith("//") else src
                                break
                    except: pass
                    p_match.close()

                    if iframe_src:
                        stream = get_stream_via_proxy(iframe_src, match['url_page'])
                        match['stream_url'] = stream
                        if stream: print("      -> Stream OK")
                    else:
                        print("      -> No Iframe")
                except Exception as e:
                    print(f"      -> Skip: {e}")

        except Exception as e:
            print(f"Error Main: {e}")
        finally:
            browser.close()

    # Sorting
    all_matches.sort(key=lambda x: (x['type'] == 'UPCOMING', x['time'])) 
    
    with open("matches.json", "w", encoding="utf-8") as f:
        # PENTING: ensure_ascii=False agar nama tim terbaca normal (bukan kode unicode)
        json.dump(all_matches, f, indent=4, ensure_ascii=False)
        print("\nSelesai. Data disimpan ke matches.json")

if __name__ == "__main__":
    main()

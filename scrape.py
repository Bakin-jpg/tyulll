import json
import time
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re

def get_stream_url(page, match_url):
    """
    Fungsi ini membuka halaman detail pertandingan dan mencari link .m3u8
    menggunakan teknik network sniffing.
    """
    m3u8_url = None
    
    # Handler untuk menangkap request network
    def handle_request(request):
        nonlocal m3u8_url
        # Cari URL yang berakhiran .m3u8 atau berisi keyword token streaming
        if ".m3u8" in request.url and m3u8_url is None:
            m3u8_url = request.url

    try:
        # Pasang pendengar network
        page.on("request", handle_request)
        
        print(f"   --> Membuka detail: {match_url}")
        page.goto(match_url, timeout=30000)
        
        # Tunggu player loading. Kadang butuh klik tombol play atau close iklan
        try:
            # Coba cari iframe player jika ada
            page.wait_for_selector('iframe', timeout=5000)
        except:
            pass
            
        # Tunggu sebentar agar network request .m3u8 muncul
        page.wait_for_timeout(4000)
        
        # Lepas pendengar
        page.remove_listener("request", handle_request)
        
        return m3u8_url

    except Exception as e:
        print(f"   --> Gagal ambil stream: {e}")
        return None

def main():
    data_matches = []
    base_url = "https://yeahscore1.com"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Gunakan User Agent agar tidak dianggap bot
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        # Halaman utama untuk list match
        page = context.new_page()

        print("1. Membuka Halaman Utama...")
        try:
            page.goto(base_url + "/", timeout=60000)
            page.wait_for_timeout(5000)
            
            html_content = page.content()
            soup = BeautifulSoup(html_content, 'html.parser')

            # Ambil semua elemen match (Live & Upcoming)
            match_elements = soup.select('.collapse-match, .item')
            print(f"Ditemukan {len(match_elements)} pertandingan. Memulai deep scraping...")

            # Batasi jumlah match agar GitHub Action tidak timeout (misal max 20 match teratas)
            # Kalau mau semua, hapus [:20]
            for index, el in enumerate(match_elements[:25]): 
                try:
                    # --- Parsing Basic Info ---
                    link_tag = el.select_one('a.link-wrapper')
                    if not link_tag:
                        continue
                    
                    match_url = base_url + link_tag['href']
                    
                    # Logika Nama Tim (Handle Unknown)
                    home_el = el.select_one('.left-column .name-club')
                    away_el = el.select_one('.right-column .name-club')
                    
                    if home_el and away_el:
                        home_team = home_el.get_text(strip=True)
                        away_team = away_el.get_text(strip=True)
                        match_title = f"{home_team} vs {away_team}"
                    else:
                        # Fallback untuk event non-team (Tennis/Wrestling/dll)
                        title_el = el.select_one('.item-title')
                        match_title = title_el.get_text(strip=True) if title_el else "Unknown Event"
                        home_team = "Event"
                        away_team = "Event"

                    # Logika Waktu
                    time_el = el.select_one('.time')
                    inplay_el = el.select_one('.inplay')
                    
                    status = "Upcoming"
                    display_time = ""

                    if inplay_el:
                        status = "LIVE"
                        game_time = inplay_el.get_text(strip=True)
                        display_time = f"LIVE {game_time}"
                    elif time_el:
                        # time_el text contoh: "Jan 27, 09:00" atau "09:00"
                        raw_time = time_el.get_text(" ", strip=True) 
                        display_time = raw_time
                    
                    # --- DEEP SCRAPING STREAM URL ---
                    # Kita gunakan tab/page baru agar page utama tidak reload
                    stream_url = None
                    if status == "LIVE" or "Today" in display_time or "Jan" in display_time:
                         # Hanya cari stream jika LIVE atau main hari ini untuk hemat waktu
                         detail_page = context.new_page()
                         stream_url = get_stream_url(detail_page, match_url)
                         detail_page.close()
                    
                    # Susun Data
                    match_data = {
                        "status": status,
                        "time_display": display_time,
                        "teams": match_title,
                        "url_page": match_url,
                        "stream_url": stream_url if stream_url else None,
                        "referer": base_url # Kadang butuh referer agar stream jalan
                    }
                    
                    data_matches.append(match_data)
                    print(f"[{index+1}] {status} - {match_title} | Stream: {'DAPAT' if stream_url else 'KOSONG'}")

                except Exception as e:
                    print(f"Error parsing item {index}: {e}")
                    continue

        except Exception as e:
            print(f"Global Error: {e}")
        finally:
            browser.close()

    # Simpan JSON
    with open("matches.json", "w", encoding="utf-8") as f:
        json.dump(data_matches, f, indent=4)
        print("Selesai! Data tersimpan ke matches.json")

if __name__ == "__main__":
    main()

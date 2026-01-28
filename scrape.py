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

def get_stream_via_proxy(iframe_url, referer_origin):
    # ... (Fungsi ini biarkan sama seperti sebelumnya) ...
    # Supaya tidak kepanjangan, saya skip copy-paste isi fungsi ini
    # karena masalahmu ada di "Main" (Halaman utama 0 match).
    return None 

def main():
    all_matches = []
    base_url = "https://yeahscore1.com"

    with sync_playwright() as p:
        # Gunakan User-Agent layaknya browser asli agar tidak dikira bot polos
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print("1. Membuka Halaman Utama Yeahscore...")
        try:
            page.goto(base_url + "/", timeout=60000)
            
            # ============================================================
            # DEBUGGING MODE: ON
            # ============================================================
            print("   -> [DEBUG] Menunggu 5 detik untuk loading konten...")
            page.wait_for_timeout(5000) # Tunggu barangkali loading lambat
            
            print("   -> [DEBUG] Mengambil Screenshot (debug_view.png)...")
            try:
                page.screenshot(path="debug_view.png", full_page=True)
            except:
                page.screenshot(path="debug_view.png") # Fallback jika full_page error

            print("   -> [DEBUG] Menyimpan HTML Source (debug_source.html)...")
            html = page.content()
            with open("debug_source.html", "w", encoding="utf-8") as f:
                f.write(html)
            # ============================================================

            # Lanjut Parsing
            soup = BeautifulSoup(html, 'html.parser')
            
            # Coba selector yang lebih umum jika .link-wrapper gagal
            link_elements = soup.select('a.link-wrapper')
            
            print(f"   -> Menemukan {len(link_elements)} potensi pertandingan.")

            # Jika 0, cek apakah ada text 'Cloudflare' atau blokir
            if len(link_elements) == 0:
                title = soup.title.string if soup.title else "No Title"
                print(f"   -> [WARNING] Judul Halaman: {title}")
                print("   -> [INFO] Silakan buka file 'debug_view.png' untuk melihat tampilan asli.")

            for link in link_elements:
                try:
                    match_url = base_url + link['href']
                    container = link.find_parent(class_=['collapse-match', 'item'])
                    if not container: continue

                    home_el = container.select_one('.left-column .name-club')
                    away_el = container.select_one('.right-column .name-club')
                    teams = f"{home_el.get_text(strip=True)} vs {away_el.get_text(strip=True)}" if home_el and away_el else "Unknown"

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
            print(f"Error halaman utama: {e}")

        # Filter & Deep Scraping (Logic disederhanakan agar fokus ke debug awal)
        targets = [m for m in all_matches if m['type'] == 'LIVE']
        if not targets:
             targets = [m for m in all_matches if m['type'] == 'UPCOMING'][:2]

        print(f"\n2. Deep Scraping ({len(targets)} Match)...")
        # (Loop deep scraping kamu bisa ditaruh sini)
        
        browser.close()

    # Simpan JSON
    with open("matches.json", "w", encoding="utf-8") as f:
        json.dump(all_matches, f, indent=4)
    
    print("\nSelesai. Cek file 'debug_view.png' dan 'debug_source.html' sekarang.")

if __name__ == "__main__":
    main()

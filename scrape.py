import json
import re
import time
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def get_stream_from_iframe(context, iframe_url, referer_match):
    """
    Fungsi khusus untuk membuka URL player (xiaolin/wowhaha),
    mengklik player, dan mencuri link m3u8.
    """
    page = context.new_page()
    final_m3u8 = None
    
    # 1. Siapkan perangkap Network (Sniffing)
    def handle_request(request):
        nonlocal final_m3u8
        # Kita cari request yang mengandung .m3u8 DAN token (biasanya panjang)
        if ".m3u8" in request.url and "token=" in request.url:
            final_m3u8 = request.url
            
    page.on("request", handle_request)

    try:
        print(f"      -> Membedah Player: {iframe_url[:50]}...")
        
        # Set referer agar tidak diblokir (pura-pura dari yeahscore)
        page.set_extra_http_headers({"Referer": referer_match})
        
        # Buka langsung URL iframenya
        page.goto(iframe_url, timeout=20000, wait_until="domcontentloaded")
        
        # 2. METODE 1: REGEX Source Code (Paling Cepat)
        # Cek apakah variabel m3u8 ada di HTML mentah sebelum JS jalan
        content = page.content()
        # Pola regex sesuai sample Anda: var m3u8 = 'LINK';
        match = re.search(r"var\s+m3u8\s*=\s*['\"]([^'\"]+)['\"]", content)
        if match:
            found_link = match.group(1)
            # Pastikan bukan link kosong/template
            if "http" in found_link:
                print("      [SUKSES] Link ditemukan via Regex HTML!")
                final_m3u8 = found_link
        
        # 3. METODE 2: Pancing dengan KLIK (Jika Regex gagal)
        if not final_m3u8:
            print("      -> Regex gagal, mencoba memancing player dengan klik...")
            try:
                # Tunggu player container muncul
                page.wait_for_selector("video, #video, .jw-video", timeout=5000)
                page.wait_for_timeout(1000)
                
                # KLIK TENGAH LAYAR (Force Play)
                # Ini yang sering dilewatkan bot biasa
                video_el = page.query_selector("video") or page.query_selector("#video") or page.query_selector("body")
                if video_el:
                    video_el.click()
                    print("      -> Klik dikirim ke player...")
                    
                # Tunggu network merespon klik
                page.wait_for_timeout(4000)
            except:
                pass

    except Exception as e:
        print(f"      [ERROR Player] {e}")
    finally:
        page.close()
        
    return final_m3u8

def main():
    all_matches = []
    base_url = "https://yeahscore1.com"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, # Ubah False jika ingin melihat prosesnya (Local PC)
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print("1. Mengambil Daftar Match...")
        try:
            page.goto(base_url + "/", timeout=60000, wait_until="domcontentloaded")
            page.wait_for_selector(".b-live-matches, .b-live-schedule", timeout=15000)
            
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')

            # --- SCRAPING DAFTAR MATCH (Live & Upcoming) ---
            # (Kode scraping list sama seperti sebelumnya, dipersingkat di sini)
            containers = [
                ('.b-live-matches', 'LIVE'), 
                ('.b-live-schedule', 'UPCOMING')
            ]
            
            for selector, m_type in containers:
                container = soup.select_one(selector)
                if not container: continue
                
                # Logic untuk extract groups & items
                groups = container.select('.collapse-group')
                for group in groups:
                    league = group.select_one('.collapse-nav-title-name')
                    league_name = league.get_text(strip=True) if league else "League"
                    
                    items = group.select('.collapse-match, .item')
                    for item in items:
                        link = item.select_one('a.link-wrapper')
                        if not link: continue
                        
                        full_url = base_url + link['href']
                        
                        # Ambil nama tim
                        home = item.select_one('.left-column .name-club')
                        away = item.select_one('.right-column .name-club')
                        
                        if home and away:
                            teams = f"{home.get_text(strip=True)} vs {away.get_text(strip=True)}"
                        else:
                            teams = item.select_one('.item-title').get_text(strip=True) if item.select_one('.item-title') else "Match"

                        # Waktu
                        time_el = item.select_one('.inplay') or item.select_one('.time')
                        time_txt = time_el.get_text(" ", strip=True) if time_el else "Check"
                        
                        if m_type == 'LIVE': time_txt = "LIVE NOW"

                        all_matches.append({
                            "type": m_type,
                            "league": league_name,
                            "teams": teams,
                            "time_display": time_txt,
                            "url_page": full_url,
                            "stream_url": None,
                            "referer": base_url
                        })

        except Exception as e:
            print(f"Gagal load halaman utama: {e}")

        # --- FASE EKSEKUSI: Deep Scrape ---
        print(f"\nTotal Match: {len(all_matches)}")
        
        # Prioritas: LIVE + 20 Upcoming Teratas
        targets = [m for m in all_matches if m['type'] == 'LIVE']
        upcoming = [m for m in all_matches if m['type'] == 'UPCOMING'][:20]
        targets.extend(upcoming)

        final_data = []

        for i, match in enumerate(targets):
            print(f"[{i+1}/{len(targets)}] {match['teams']} ({match['type']})")
            
            # 1. Buka Halaman Match Detail
            detail_page = context.new_page()
            iframe_src = None
            
            try:
                detail_page.goto(match['url_page'], timeout=10000, wait_until="domcontentloaded")
                
                # 2. Cari URL Iframe (xiaolin/wowhaha) di dalam DOM
                # Kita tidak perlu regex network dulu, cukup cari elemen <iframe>
                try:
                    # Tunggu sebentar iframe muncul
                    detail_page.wait_for_selector("iframe", timeout=4000)
                except: pass

                iframes = detail_page.query_selector_all("iframe")
                for frame in iframes:
                    src = frame.get_attribute("src")
                    # Ciri-ciri iframe player target
                    if src and ("wowhaha" in src or "xiaolin" in src or "embed" in src):
                        iframe_src = src
                        if src.startswith("//"): iframe_src = "https:" + src
                        break
            except Exception as e:
                print(f"      [SKIP] Gagal buka detail: {e}")
            finally:
                detail_page.close()

            # 3. Jika ketemu URL Iframe, kita "Bedah"
            if iframe_src:
                real_stream = get_stream_from_iframe(context, iframe_src, match['url_page'])
                match['stream_url'] = real_stream
                
                # Fix Referer untuk VLC
                if real_stream:
                     match['referer'] = "https://xiaolin3.live/"
            else:
                print("      [INFO] Tidak ada iframe player (Mungkin belum mulai).")

            final_data.append(match)

        browser.close()

    # Simpan
    with open("matches.json", "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=4)
        print("\nSelesai. Data tersimpan di matches.json")

if __name__ == "__main__":
    main()

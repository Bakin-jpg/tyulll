import json
import os
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def main():
    data_matches = []
    base_url = "https://yeahscore1.com"

    with sync_playwright() as p:
        # 1. Buka Browser
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print("Membuka website...")
        try:
            page.goto(base_url + "/", timeout=60000)
            page.wait_for_timeout(5000) # Tunggu loading vue js
            
            # Ambil HTML
            html_content = page.content()
            soup = BeautifulSoup(html_content, 'html.parser')

            # 2. Parsing HTML (Berdasarkan Inspect Element kamu)
            
            # Mencari container Live Matches dan Upcoming
            # Class .item biasanya untuk upcoming/schedule, .collapse-match untuk live
            match_elements = soup.select('.collapse-match, .item')

            for el in match_elements:
                try:
                    # Ambil Link
                    link_tag = el.select_one('a.link-wrapper')
                    if not link_tag:
                        continue
                    
                    match_url = base_url + link_tag['href']
                    
                    # Ambil Nama Tim Home
                    home_el = el.select_one('.left-column .name-club')
                    home_team = home_el.get_text(strip=True) if home_el else "Unknown Home"
                    
                    # Ambil Nama Tim Away
                    away_el = el.select_one('.right-column .name-club')
                    away_team = away_el.get_text(strip=True) if away_el else "Unknown Away"

                    # Ambil Waktu / Status
                    time_el = el.select_one('.time-info .time')
                    inplay_el = el.select_one('.time-info .inplay')
                    
                    status = "Upcoming"
                    time_str = ""

                    if inplay_el:
                        status = "LIVE"
                        time_str = inplay_el.get_text(strip=True) # Misal: 66'
                    elif time_el:
                        time_str = time_el.get_text(strip=True) # Misal: 20:00
                    
                    # Coba cari nama Liga (Naik ke parent terdekat)
                    # Ini agak tricky karena struktur nested, kita set default dulu
                    league_name = "Sports Event"
                    
                    # Simpan data
                    match_data = {
                        "status": status,
                        "time": time_str,
                        "home": home_team,
                        "away": away_team,
                        "match_title": f"{home_team} vs {away_team}",
                        "url": match_url,
                        "league": league_name
                    }
                    
                    data_matches.append(match_data)

                except Exception as e:
                    print(f"Error parsing item: {e}")
                    continue

        except Exception as e:
            print(f"Global Error: {e}")
        finally:
            browser.close()

    # 3. Simpan ke JSON (Ini yang jadi API kamu)
    with open("matches.json", "w", encoding="utf-8") as f:
        json.dump(data_matches, f, indent=4)
        print("Data tersimpan ke matches.json")

if __name__ == "__main__":
    main()

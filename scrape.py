import time
from playwright.sync_api import sync_playwright

def main():
    print("--- MULAI DEBUG MODE ---")
    
    with sync_playwright() as p:
        # Gunakan argumen browser yang lebih lengkap untuk anti-deteksi
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-infobars',
                '--window-position=0,0',
                '--ignore-certifcate-errors',
                '--ignore-certifcate-errors-spki-list',
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ]
        )
        
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        url = "https://yeahscore1.com/"
        print(f"1. Membuka URL: {url}")
        
        try:
            response = page.goto(url, timeout=60000, wait_until="domcontentloaded")
            print(f"   -> Status Code: {response.status}")
        except Exception as e:
            print(f"   -> Error Loading: {e}")

        # Tunggu loading sejenak
        print("2. Menunggu rendering (5 detik)...")
        time.sleep(5)

        # === BAGIAN DEBUG VITAL ===
        print("3. MENGAMBIL BUKTI TAMPILAN BOT...")
        
        # A. Cek Judul Halaman
        title = page.title()
        print(f"   -> Judul Halaman: {title}")
        
        # B. Ambil Screenshot (Biar kita tau bot liat apa: Putih doang? Cloudflare? Atau websitenya?)
        page.screenshot(path="debug_screenshot.png", full_page=True)
        print("   -> Screenshot disimpan: debug_screenshot.png")
        
        # C. Simpan Source Code HTML Mentah
        html_content = page.content()
        with open("debug_source.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print("   -> Source HTML disimpan: debug_source.html")
        
        # === ANALISA SEDERHANA ===
        if "Just a moment" in title or "Attention Required" in title or "Cloudflare" in title:
            print("\n[VONIS] BOT DIBLOKIR CLOUDFLARE!")
            print("Website mendeteksi ini adalah bot. IP GitHub Actions sudah ditandai.")
            
        elif len(html_content) < 500:
            print("\n[VONIS] WEBSITE KOSONG/PUTIH")
            print("Website tidak me-load konten apa-apa.")
            
        elif "b-live-matches" in html_content:
            print("\n[VONIS] KONTEN ADA, TAPI SELEKTOR MUNGKIN SALAH")
            print("Class '.b-live-matches' ditemukan di HTML. Masalah ada di logika parsing (BeautifulSoup).")
        else:
            print("\n[VONIS] KONTEN BERUBAH ATAU BELUM LOAD")
            print("Halaman terbuka tapi class match tidak ditemukan. Cek screenshot.")

        browser.close()
        print("--- SELESAI ---")

if __name__ == "__main__":
    main()

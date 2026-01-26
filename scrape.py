import time
from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        # 1. Jalankan browser (Headless Chrome)
        browser = p.chromium.launch(headless=True)
        
        # 2. Buat context dengan User Agent agar tidak dideteksi sebagai bot
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print("Sedang membuka website...")
        url = "https://yeahscore1.com/"
        
        try:
            # 3. Buka URL
            page.goto(url, timeout=60000)
            
            # 4. Tunggu sebentar agar JavaScript/Data loading selesai (5 detik)
            # Kamu bisa naikkan angkanya jika webnya lambat
            page.wait_for_timeout(5000) 
            
            # 5. Ambil seluruh konten HTML (Ini adalah "Inspect Element" nya)
            content = page.content()
            
            # 6. Simpan ke file
            filename = "hasil_inspect.html"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)
            
            print(f"Berhasil! File tersimpan sebagai {filename}")
            
        except Exception as e:
            print(f"Terjadi error: {e}")
        
        finally:
            browser.close()

if __name__ == "__main__":
    run()

from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import requests, json, time
from datetime import datetime

# --- 1. Fetch the list of events from the original API ---
def fetch_event_list():
    """Gets the list of matches/fixtures from the YeahScore API."""
    url = "https://yeahscore1.com/api/fixtures/livestream"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # Adapt this based on the actual API response structure
        events = data.get('data', []) if isinstance(data, dict) else data
        print(f"[INFO] Fetched {len(events)} events from API.")
        return events
    except Exception as e:
        print(f"[ERROR] Failed to fetch event list: {e}")
        return []

# --- 2. Scrape the actual stream URL from an event page ---
def scrape_stream_url(event_page_url):
    """
    Opens an event page with a hidden browser and captures the .m3u8 request.
    This is the core function that finds the real stream.
    """
    # Configure Chrome to log network performance data[citation:5]
    caps = DesiredCapabilities.CHROME
    caps["goog:loggingPrefs"] = {"performance": "ALL"}

    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Run without GUI
    options.add_argument("--mute-audio")
    options.add_argument("--disable-gpu")
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    # Use a common user-agent
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

    driver = None
    try:
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options,
            desired_capabilities=caps
        )
        print(f"[SCRAPE] Opening: {event_page_url}")
        driver.get(event_page_url)
        # Wait for page and potential video player to load
        time.sleep(7)

        # Analyze all network logs[citation:5]
        logs = driver.get_log("performance")
        m3u8_urls = set()  # Use a set to avoid duplicates

        for entry in logs:
            log = json.loads(entry["message"])["message"]
            # Focus on network responses and requests
            if "Network.response" in log["method"] or "Network.request" in log["method"]:
                if 'request' in log.get("params", {}):
                    request_url = log["params"]["request"].get("url", "")
                    # Look for the key indicator of a video stream
                    if '.m3u8' in request_url and 'blob:' not in request_url:
                        m3u8_urls.add(request_url)

        if m3u8_urls:
            # Return the first found m3u8 URL. Sometimes there are multiple.
            final_url = list(m3u8_urls)[0]
            print(f"[SUCCESS] Found stream: {final_url[:80]}...")
            return final_url
        else:
            print(f"[WARNING] No .m3u8 stream found on page.")
            return None

    except Exception as e:
        print(f"[ERROR] Scraping failed for {event_page_url}: {e}")
        return None
    finally:
        if driver:
            driver.quit()

# --- 3. Main function to create the API-like data ---
def build_stream_api():
    """
    Combines the event list with scraped stream URLs to build a clean JSON.
    """
    events = fetch_event_list()
    api_result = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "source": "yeahscore1.com",
        "success": True,
        "data": []
    }

    for event in events[:5]:  # LIMIT to 5 events for testing. Remove [:] for all.
        # Assuming the event dict has at least an 'id' and a 'url' or 'link' field to the page
        event_id = event.get('id', 'N/A')
        # You need to find or construct the actual page URL from the event data.
        # This is an example - you must inspect the site to find the correct pattern.
        page_url = event.get('link') or f"https://yeahscore1.com/match/{event_id}"
        
        print(f"\n--- Processing Event ID: {event_id} ---")
        stream_url = scrape_stream_url(page_url)
        
        if stream_url:
            api_result["data"].append({
                "event_id": event_id,
                "home_team": event.get('home_team', 'Unknown'),
                "away_team": event.get('away_team', 'Unknown'),
                "league": event.get('competition', 'Unknown'),
                "stream_url": stream_url,  # The valuable scraped link
                "event_page": page_url,
                "scraped_at": datetime.utcnow().isoformat() + "Z"
            })
        time.sleep(2)  # Be polite to the server between requests

    print(f"\n[SUMMARY] Successfully enriched {len(api_result['data'])} events with stream URLs.")
    return api_result

# --- Run the script ---
if __name__ == "__main__":
    print("Starting YeahScore Stream Scraper...")
    final_api_data = build_stream_api()

    # Save to a JSON file
    with open('yeahscore_streams_api.json', 'w', encoding='utf-8') as f:
        json.dump(final_api_data, f, indent=2, ensure_ascii=False)
    print("Data saved to 'yeahscore_streams_api.json'")

    # Print a sample to console
    print("\nSample API output structure:")
    if final_api_data["data"]:
        sample = final_api_data["data"][0]
        print(json.dumps(sample, indent=2))

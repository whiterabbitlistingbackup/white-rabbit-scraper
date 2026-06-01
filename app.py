import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import time

# Browser headers that work
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
    "Referer": "https://www.ebay.co.uk/"
}

st.set_page_config(page_title="White Rabbit", layout="wide")
st.title("🐇 White Rabbit eBay Scraper")

def get_title(soup):
    h1 = soup.find("h1")
    return h1.get_text(strip=True) if h1 else "Unknown"

def get_images(soup, html):
    """Extract images from HTML carousel"""
    images = set()
    
    # Method 1: Direct img tags in carousel
    for img in soup.select("div.ux-image-carousel-item img"):
        src = img.get("src") or img.get("data-src")
        if src and "ebayimg" in src:
            images.add(src)
    
    # Method 2: Extract from JSON in page
    json_urls = re.findall(r'"iUrl":"(https:\/\/i\.ebayimg\.com\/[^"]+)"', html)
    images.update(json_urls)
    
    # Normalize to full resolution
    images = [re.sub(r's-l\d+', 's-l1600', url) for url in images if 'ebayimg' in url]
    return list(dict.fromkeys(images))

def scrape_url(url):
    """Scrape single eBay listing"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        html = resp.text
        soup = BeautifulSoup(html, "html.parser")
        
        title = get_title(soup)
        images = get_images(soup, html)
        
        return {
            "title": title,
            "images": len(images),
            "urls": images,
            "error": None
        }
    except Exception as e:
        return {
            "title": "Error",
            "images": 0,
            "urls": [],
            "error": str(e)[:50]
        }

# UI
urls_input = st.text_area("Paste URLs (one per line):", height=120)

if st.button("🔍 Scrape", type="primary"):
    urls = [u.strip() for u in urls_input.split("\n") if u.strip().startswith("http")]
    
    if not urls:
        st.error("No URLs provided")
    else:
        progress = st.progress(0)
        status = st.empty()
        
        results = []
        for i, url in enumerate(urls):
            progress.progress((i + 1) / len(urls))
            status.text(f"{i + 1}/{len(urls)}")
            
            data = scrape_url(url)
            results.append({
                "URL": url,
                "Title": data["title"],
                "Images": data["images"],
                "Status": "✅" if data["images"] > 0 else ("❌" if data["error"] else "⚠️")
            })
            
            time.sleep(0.3)
        
        progress.empty()
        status.empty()
        
        df = pd.DataFrame(results)
        st.success(f"Done! {len([r for r in results if r['Images'] > 0])}/{len(urls)} with images")
        st.dataframe(df, use_container_width=True)
        
        csv = df.to_csv(index=False)
        st.download_button("📥 Download CSV", csv, "results.csv", "text/csv")

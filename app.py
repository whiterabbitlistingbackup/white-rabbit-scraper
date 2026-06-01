import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import time
import os
from datetime import datetime

# Browser headers that work
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
    "Referer": "https://www.ebay.co.uk/"
}

st.set_page_config(page_title="White Rabbit", layout="wide")
st.title("🐇 White Rabbit eBay Scraper")
st.write("Extract complete eBay listings with images, details & metadata")

def get_title(soup):
    h1 = soup.find("h1")
    return h1.get_text(strip=True) if h1 else "Unknown"

def get_condition(soup):
    tag = soup.select_one(".x-item-condition-text")
    if tag:
        return tag.get_text(strip=True).replace("More information - About this item condition", "").strip()
    return "Unknown"

def get_price(soup):
    selectors = [".x-price-primary", "#prcIsum", "#mm-saleDscPrc"]
    for sel in selectors:
        tag = soup.select_one(sel)
        if tag:
            return tag.get_text(strip=True)
    return "Unknown"

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

def get_description(soup):
    """Extract seller description"""
    # Try iframe method
    iframe = soup.find("iframe", {"id": "desc_ifr"})
    if iframe and iframe.get("src"):
        try:
            r = requests.get(iframe["src"], headers=HEADERS, timeout=5)
            desc_soup = BeautifulSoup(r.text, "html.parser")
            text = desc_soup.get_text(strip=True)
            if text:
                return text[:1000]
        except:
            pass
    
    # Fallback: direct div
    for pid in ["desc_div", "viTabs_0_is"]:
        tag = soup.find(id=pid)
        if tag:
            return tag.get_text(strip=True)[:1000]
    
    return "No description"

def scrape_url(url):
    """Scrape single eBay listing"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        html = resp.text
        
        # Check for bot detection
        if "Checking your browser" in html:
            return {
                "title": "Blocked",
                "condition": "-",
                "price": "-",
                "images": 0,
                "description": "-",
                "urls": [],
                "error": "eBay bot detection"
            }
        
        soup = BeautifulSoup(html, "html.parser")
        
        return {
            "title": get_title(soup),
            "condition": get_condition(soup),
            "price": get_price(soup),
            "description": get_description(soup),
            "images": len(get_images(soup, html)),
            "urls": get_images(soup, html),
            "error": None
        }
    except Exception as e:
        return {
            "title": "Error",
            "condition": "-",
            "price": "-",
            "images": 0,
            "description": "-",
            "urls": [],
            "error": str(e)[:50]
        }

# --- Main UI ---
tab1, tab2 = st.tabs(["Scrape URLs", "Batch Import"])

with tab1:
    urls_input = st.text_area("Paste eBay URLs (one per line):", height=120)
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col2:
        delay = st.number_input("Delay (seconds):", min_value=0.1, max_value=5.0, value=0.3, step=0.1)
    with col3:
        scrape_btn = st.button("🔍 Scrape", type="primary", use_container_width=True)
    
    if scrape_btn:
        urls = [u.strip() for u in urls_input.split("\n") if u.strip().startswith("http")]
        
        if not urls:
            st.error("No URLs provided")
        else:
            progress = st.progress(0)
            status = st.empty()
            
            results = []
            all_data = []
            
            for i, url in enumerate(urls):
                progress.progress((i + 1) / len(urls))
                status.text(f"Scraping {i + 1}/{len(urls)}")
                
                data = scrape_url(url)
                results.append({
                    "URL": url,
                    "Title": data["title"],
                    "Condition": data["condition"],
                    "Price": data["price"],
                    "Images": data["images"],
                    "Status": "✅" if data["images"] > 0 else "❌"
                })
                all_data.append(data)
                
                time.sleep(delay)
            
            progress.empty()
            status.empty()
            
            successful = len([r for r in results if r['Images'] > 0])
            st.success(f"✅ Done! {successful}/{len(urls)} with images")
            
            # Show results table
            df = pd.DataFrame(results)
            st.dataframe(df, use_container_width=True)
            
            # Stats
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total URLs", len(urls))
            with col2:
                st.metric("With Images", successful)
            with col3:
                total_imgs = sum(r['Images'] for r in results)
                st.metric("Total Images", total_imgs)
            
            # Download options
            st.divider()
            st.subheader("📥 Export Options")
            
            col1, col2 = st.columns(2)
            
            with col1:
                csv = df.to_csv(index=False)
                st.download_button("📊 Download CSV", csv, f"ebay_scrape_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "text/csv")
            
            with col2:
                # Create detailed export
                detailed = []
                for url, data in zip(urls, all_data):
                    detailed.append({
                        "URL": url,
                        "Title": data["title"],
                        "Condition": data["condition"],
                        "Price": data["price"],
                        "Images": data["images"],
                        "Description": data["description"],
                        "Image URLs": "\n".join(data["urls"][:5])  # First 5 images
                    })
                df_detailed = pd.DataFrame(detailed)
                detailed_csv = df_detailed.to_csv(index=False)
                st.download_button("📋 Download Detailed", detailed_csv, f"ebay_detailed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "text/csv")

with tab2:
    st.write("Import URLs from a file")
    uploaded_file = st.file_uploader("Upload CSV or TXT file", type=["csv", "txt"])
    
    if uploaded_file:
        if uploaded_file.name.endswith('.csv'):
            df_upload = pd.read_csv(uploaded_file)
            urls_list = df_upload.iloc[:, 0].tolist()
        else:
            content = uploaded_file.read().decode()
            urls_list = [u.strip() for u in content.split("\n") if u.strip().startswith("http")]
        
        st.write(f"Found {len(urls_list)} URLs")
        
        if st.button("🔍 Scrape Batch", type="primary"):
            progress = st.progress(0)
            status = st.empty()
            
            results = []
            for i, url in enumerate(urls_list):
                progress.progress((i + 1) / len(urls_list))
                status.text(f"{i + 1}/{len(urls_list)}")
                
                data = scrape_url(url)
                results.append({
                    "URL": url,
                    "Title": data["title"],
                    "Condition": data["condition"],
                    "Price": data["price"],
                    "Images": data["images"],
                    "Status": "✅" if data["images"] > 0 else "❌"
                })
                
                time.sleep(0.3)
            
            progress.empty()
            status.empty()
            
            df_results = pd.DataFrame(results)
            st.dataframe(df_results, use_container_width=True)
            
            csv_out = df_results.to_csv(index=False)
            st.download_button("📥 Download Results", csv_out, "batch_results.csv", "text/csv")

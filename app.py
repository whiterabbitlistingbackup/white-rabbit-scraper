import streamlit as st
import pandas as pd
import requests
import re
import os
import io
import zipfile
from bs4 import BeautifulSoup
from urllib.parse import urlparse

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
    "Referer": "https://www.ebay.co.uk/",
    "Cookie": "ebay=%5Esbf%3D%23000000%5E"
}

st.title("🐇 White Rabbit eBay Scraper")
st.write("Extract full eBay listings with images, condition, price, and more.")

# --- Helpers ---
def clean_title(title):
    title = title.strip()
    title = re.sub(r"[^A-Za-z0-9]+", "_", title)
    return title[:60] or "item"

def extract_title(soup):
    tag = soup.find("h1")
    if not tag:
        return "item"
    return clean_title(tag.get_text())

def extract_condition(soup):
    tag = soup.select_one(".x-item-condition-text")
    if tag:
        text = tag.get_text(" ", strip=True)
        text = text.replace("More information - About this item condition", "")
        text = " ".join(dict.fromkeys(text.split()))
        return text.strip()
    
    tag = soup.find(id="vi-itm-cond")
    if tag:
        text = tag.get_text(strip=True)
        text = " ".join(dict.fromkeys(text.split()))
        return text
    
    return "UnknownCondition"

def extract_price(soup):
    selectors = [
        ".x-price-primary",
        "#prcIsum",
        "#mm-saleDscPrc",
        "#prcIsum_bidPrice",
        ".notranslate"
    ]
    for sel in selectors:
        tag = soup.select_one(sel)
        if tag:
            return tag.get_text(strip=True)
    return "UnknownPrice"

def extract_category(soup):
    crumbs = soup.select("li.seo-breadcrumb-text")
    if crumbs:
        return " > ".join([c.get_text(strip=True) for c in crumbs])
    
    crumbs = soup.select("nav[aria-label='Breadcrumb'] li a")
    if crumbs:
        return " > ".join([c.get_text(strip=True) for c in crumbs])
    
    scripts = soup.find_all("script")
    category_candidates = []
    
    for s in scripts:
        if not s.string:
            continue
        text = s.string
        matches = re.findall(r'"categoryName":"([^"]+)"', text)
        for m in matches:
            category_candidates.append(m)
    
    category_candidates = list(dict.fromkeys(category_candidates))
    if category_candidates:
        return category_candidates[0]
    
    return "UnknownCategory"

def extract_description(soup, html):
    iframe = soup.find("iframe", {"id": "desc_ifr"})
    if iframe and iframe.get("src"):
        iframe_url = iframe["src"]
        if iframe_url.startswith("//"):
            iframe_url = "https:" + iframe_url
        try:
            r = requests.get(iframe_url, headers=HEADERS, timeout=10)
            iframe_soup = BeautifulSoup(r.text, "html.parser")
            text = iframe_soup.get_text("\n", strip=True)
            if text:
                return text
        except:
            pass
    
    for pid in ["desc_div", "viTabs_0_is"]:
        tag = soup.find(id=pid)
        if tag:
            return tag.get_text("\n", strip=True)
    
    return "No seller description found."

def extract_gallery_images(soup):
    urls = set()
    thumbs = soup.select("div.ux-image-carousel-item img")
    
    for img in thumbs:
        for attr in ["src", "data-src", "data-img"]:
            src = img.get(attr)
            if src and "i.ebayimg.com" in src:
                urls.add(src)
        
        srcset = img.get("srcset")
        if srcset:
            for part in srcset.split(","):
                url = part.strip().split(" ")[0]
                if "i.ebayimg.com" in url:
                    urls.add(url)
    
    return urls

def extract_gallery_json(html):
    urls = set()
    matches = re.findall(r'\"iUrl\":\"(https:\\/\\/i\\.ebayimg\\.com[^\"]+)', html)
    for m in matches:
        urls.add(m.replace("\\/", "/"))
    return urls

def normalise_image(url):
    return re.sub(r's-l\d+\.jpg', 's-l1600.jpg', url)

# --- Main scrape function ---
def scrape_listing(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        return None, str(e)
    
    html = r.text
    soup = BeautifulSoup(html, "html.parser")
    
    title = extract_title(soup)
    condition = extract_condition(soup)
    price = extract_price(soup)
    category = extract_category(soup)
    description = extract_description(soup, html)
    
    # Images
    img_urls = extract_gallery_images(soup)
    if not img_urls:
        img_urls = extract_gallery_json(html)
    
    img_urls = [normalise_image(u) for u in img_urls]
    img_urls = [u for u in img_urls if u.lower().endswith("s-l1600.jpg")]
    img_urls = list(dict.fromkeys(img_urls))
    
    return {
        "title": title,
        "condition": condition,
        "price": price,
        "category": category,
        "description": description,
        "images": img_urls,
        "image_count": len(img_urls)
    }, None

# --- UI ---
input_text = st.text_area("Paste eBay URLs (one per line):", height=150)

if st.button("🔍 Scrape Listings", type="primary"):
    urls = [u.strip() for u in input_text.split("\n") if u.strip().startswith("http")]
    
    if not urls:
        st.error("No valid URLs provided")
    else:
        progress_bar = st.progress(0)
        status = st.empty()
        
        results = []
        for idx, url in enumerate(urls):
            progress_bar.progress((idx + 1) / len(urls))
            status.text(f"Scraping {idx + 1}/{len(urls)}...")
            
            data, error = scrape_listing(url)
            if error:
                results.append({
                    "URL": url,
                    "Status": f"❌ {error}",
                    "Title": "",
                    "Condition": "",
                    "Price": "",
                    "Images": 0
                })
            else:
                results.append({
                    "URL": url,
                    "Status": "✅ Success",
                    "Title": data["title"],
                    "Condition": data["condition"],
                    "Price": data["price"],
                    "Images": data["image_count"]
                })
        
        df = pd.DataFrame(results)
        st.success(f"✅ Scraped {len(urls)} listings!")
        st.dataframe(df, use_container_width=True)
        
        # Download CSV
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Download CSV Results",
            csv,
            "ebay_listings.csv",
            "text/csv"
        )

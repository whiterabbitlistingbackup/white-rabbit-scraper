import streamlit as st
import pandas as pd
import requests
import re
import io
from bs4 import BeautifulSoup
from urllib.parse import urlparse

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
    "Referer": "https://www.ebay.co.uk/",
    "Cookie": "ebay=%5Esbf%3D%23000000%5E"
}

st.set_page_config(page_title="White Rabbit eBay Scraper", layout="wide")
st.title("🐇 White Rabbit eBay Scraper")
st.write("Extract full eBay listings: images, condition, price, postage, category & more")

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

def extract_postage(soup):
    tag = soup.select_one(".x-shipping-cost")
    if tag:
        return tag.get_text(strip=True)
    
    tag = soup.select_one(".ux-labels-values__values-content")
    if tag and ("£" in tag.get_text() or "Free" in tag.get_text()):
        return tag.get_text(strip=True)
    
    tag = soup.find("span", {"id": "fshippingCost"})
    if tag:
        return tag.get_text(strip=True)
    
    return "UnknownPostage"

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
        
        matches = re.findall(r'"name":"([^"]+)"', text)
        for m in matches:
            if len(m) < 3 or m.isupper() or "_" in m or m.lower() in ["name", "jsonld", "search", "information"]:
                continue
            category_candidates.append(m)
    
    category_candidates = list(dict.fromkeys(category_candidates))
    real = [c for c in category_candidates if c[0].isupper() and " " in c]
    
    if real:
        return " > ".join(real[:5])
    
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
    
    iframe = soup.find("iframe")
    if iframe and iframe.get("src") and "ebaydesc" in iframe["src"]:
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

def extract_item_specifics(soup):
    specifics = {}
    
    labels = soup.select(".ux-labels-values__labels")
    values = soup.select(".ux-labels-values__values")
    if labels and values:
        for label, value in zip(labels, values):
            specifics[label.get_text(strip=True)] = value.get_text(strip=True)
    
    table = soup.find("table", {"id": "vi-ia-attrTable"})
    if table:
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 2:
                specifics[cells[0].get_text(strip=True).replace(":", "")] = cells[1].get_text(strip=True)
    
    fallback = soup.find("div", {"class": "itemAttr"})
    if fallback:
        for row in fallback.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 2:
                specifics[cells[0].get_text(strip=True).replace(":", "")] = cells[1].get_text(strip=True)
    
    return specifics

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
    postage = extract_postage(soup)
    category = extract_category(soup)
    description = extract_description(soup, html)
    specifics = extract_item_specifics(soup)
    
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
        "postage": postage,
        "category": category,
        "description": description,
        "specifics": specifics,
        "images": img_urls,
        "image_count": len(img_urls)
    }, None

# --- UI ---
input_text = st.text_area("Paste eBay URLs (one per line):", height=150, placeholder="https://www.ebay.co.uk/itm/...")

col1, col2 = st.columns([3, 1])
with col2:
    scrape_button = st.button("🔍 Scrape", type="primary", use_container_width=True)

if scrape_button:
    urls = [u.strip() for u in input_text.split("\n") if u.strip().startswith("http")]
    
    if not urls:
        st.error("❌ No valid URLs provided")
    else:
        progress_bar = st.progress(0)
        status = st.empty()
        
        results = []
        details = {}
        
        for idx, url in enumerate(urls):
            progress_bar.progress((idx + 1) / len(urls))
            status.text(f"📍 Scraping {idx + 1}/{len(urls)}: {url[:60]}...")
            
            data, error = scrape_listing(url)
            if error:
                results.append({
                    "URL": url,
                    "Status": "❌",
                    "Title": "",
                    "Condition": "",
                    "Price": "",
                    "Postage": "",
                    "Images": 0,
                    "Error": error[:50]
                })
            else:
                results.append({
                    "URL": url,
                    "Status": "✅",
                    "Title": data["title"],
                    "Condition": data["condition"],
                    "Price": data["price"],
                    "Postage": data["postage"],
                    "Images": data["image_count"]
                })
                details[url] = data
        
        progress_bar.empty()
        status.empty()
        
        df = pd.DataFrame(results)
        st.success(f"✅ Scraped {len(urls)} listings!")
        
        # Summary stats
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total URLs", len(df))
        with col2:
            successful = len(df[df["Status"] == "✅"])
            st.metric("✅ Successful", successful)
        with col3:
            failed = len(df[df["Status"] == "❌"])
            st.metric("❌ Failed", failed)
        with col4:
            total_images = df[df["Status"] == "✅"]["Images"].sum()
            st.metric("🖼️ Total Images", int(total_images))
        
        st.divider()
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Download CSV
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Download CSV",
            csv,
            "ebay_listings.csv",
            "text/csv"
        )
        
        # Show details for successful scrapes
        if details:
            st.divider()
            st.subheader("📋 Full Details")
            
            for url, data in details.items():
                with st.expander(f"📄 {data['title']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Condition:** {data['condition']}")
                        st.write(f"**Price:** {data['price']}")
                        st.write(f"**Postage:** {data['postage']}")
                    with col2:
                        st.write(f"**Category:** {data['category']}")
                        st.write(f"**Images:** {data['image_count']}")
                        st.write(f"**URL:** {url}")
                    
                    st.write("**Description:**")
                    st.write(data['description'][:500] + "..." if len(data['description']) > 500 else data['description'])
                    
                    if data['specifics']:
                        st.write("**Item Specifics:**")
                        spec_df = pd.DataFrame(list(data['specifics'].items()), columns=["Key", "Value"])
                        st.dataframe(spec_df, use_container_width=True, hide_index=True)
                    
                    if data['images']:
                        st.write("**Image URLs:**")
                        for i, img_url in enumerate(data['images'], 1):
                            st.code(img_url, language="text")

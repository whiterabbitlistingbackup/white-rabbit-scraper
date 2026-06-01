# ┌────────────────────────────────────────────────────────────────────────────┐
# │                             White Rabbit eBay Scraper                      │
# │                     • Full‑res gallery extraction (HTML + JSON)            │
# │                     • Description + item specifics                          │
# │                     • Condition, price, postage, category                   │
# │                     • Clean folder naming                                   │
# │                     • Press Q to quit gracefully                            │
# └────────────────────────────────────────────────────────────────────────────┘

import os
import re
import requests
import threading
import sys
from bs4 import BeautifulSoup
from tqdm import tqdm

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
    "Referer": "https://www.ebay.co.uk/",
    "Cookie": "ebay=%5Esbf%3D%23000000%5E"
}

quit_flag = False
FAILED = open("failed_listings.txt", "a", encoding="utf-8")

# ---------------------------------------------------------
# Quit listener
# ---------------------------------------------------------
def quit_listener():
    global quit_flag
    while True:
        key = sys.stdin.read(1)
        if key.lower() == "q":
            quit_flag = True
            print("\nStopping after current item…")
            break

threading.Thread(target=quit_listener, daemon=True).start()

# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------
def clean_title(title):
    title = title.strip()
    title = re.sub(r"[^A-Za-z0-9]+", "_", title)
    return title[:60] or "item"

def extract_title(soup):
    tag = soup.find("h1")
    if not tag:
        return "item"
    return clean_title(tag.get_text())

# ---------------------------------------------------------
# Extra info extraction
# ---------------------------------------------------------
def extract_condition(soup):
    tag = soup.select_one(".x-item-condition-text")
    if tag:
        text = tag.get_text(" ", strip=True)
        text = text.replace("More information - About this item condition", "")
        text = " ".join(dict.fromkeys(text.split()))  # remove duplicate words
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
    # 1. Try visible breadcrumbs
    crumbs = soup.select("li.seo-breadcrumb-text")
    if crumbs:
        return " > ".join([c.get_text(strip=True) for c in crumbs])

    crumbs = soup.select("nav[aria-label='Breadcrumb'] li a")
    if crumbs:
        return " > ".join([c.get_text(strip=True) for c in crumbs])

    # 2. JSON fallback
    scripts = soup.find_all("script")
    category_candidates = []

    for s in scripts:
        if not s.string:
            continue
        text = s.string

        # Look for categoryName fields
        matches = re.findall(r'"categoryName":"([^"]+)"', text)
        for m in matches:
            category_candidates.append(m)

        # Look for name fields but filter out UI junk
        matches = re.findall(r'"name":"([^"]+)"', text)
        for m in matches:
            # Filter out garbage UI names
            if len(m) < 3:
                continue
            if m.isupper():
                continue
            if "_" in m:
                continue
            if m.lower() in ["name", "jsonld", "search", "information"]:
                continue
            category_candidates.append(m)

    # Keep only unique values
    category_candidates = list(dict.fromkeys(category_candidates))

    # Heuristic: real categories are short, human-readable, capitalised
    real = [c for c in category_candidates if c[0].isupper() and " " in c]

    if real:
        return " > ".join(real[:5])  # limit to avoid runaway

    return "UnknownCategory"

# ---------------------------------------------------------
# Description extraction
# ---------------------------------------------------------
def extract_description(soup, html, url):
    iframe = soup.find("iframe", {"id": "desc_ifr"})
    if iframe and iframe.get("src"):
        iframe_url = iframe["src"]
        if iframe_url.startswith("//"):
            iframe_url = "https:" + iframe_url
        try:
            r = requests.get(iframe_url, headers=HEADERS)
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
            r = requests.get(iframe_url, headers=HEADERS)
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

# ---------------------------------------------------------
# Item specifics extraction
# ---------------------------------------------------------
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

# ---------------------------------------------------------
# Gallery extraction (HTML + JSON fallback)
# ---------------------------------------------------------
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

# ---------------------------------------------------------
# Main download function
# ---------------------------------------------------------
def download_images(url):
    global quit_flag
    if quit_flag:
        return

    print(f"\nProcessing: {url}")

    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
    except:
        print("Failed to load page.")
        FAILED.write(url + "\n")
        FAILED.flush()
        return

    html = r.text
    soup = BeautifulSoup(html, "html.parser")

    # Extract core info
    title = extract_title(soup)
    condition = extract_condition(soup)

    # Folder naming
    folder = f"{title}_{condition}"
    folder = folder.replace("__", "_")[:120]
    os.makedirs(folder, exist_ok=True)

    # Save extra info
    price = extract_price(soup)
    postage = extract_postage(soup)
    category = extract_category(soup)

    with open(os.path.join(folder, "info.txt"), "w", encoding="utf-8") as f:
        f.write(f"Title: {title}\n")
        f.write(f"Condition: {condition}\n")
        f.write(f"Price: {price}\n")
        f.write(f"Postage: {postage}\n")
        f.write(f"Category: {category}\n")
        f.write(f"URL: {url}\n")

    # Description
    description = extract_description(soup, html, url)
    with open(os.path.join(folder, "description.txt"), "w", encoding="utf-8") as f:
        f.write(description)

    # Item specifics
    specifics = extract_item_specifics(soup)
    with open(os.path.join(folder, "item_specifics.txt"), "w", encoding="utf-8") as f:
        for key, val in specifics.items():
            f.write(f"{key}: {val}\n")

    # Gallery (HTML + JSON fallback)
    img_urls = extract_gallery_images(soup)

    if not img_urls:
        img_urls = extract_gallery_json(html)

    img_urls = [normalise_image(u) for u in img_urls]
    img_urls = [u for u in img_urls if u.lower().endswith("s-l1600.jpg")]
    img_urls = list(dict.fromkeys(img_urls))

    if not img_urls:
        print("No usable images found.")
        FAILED.write(url + "\n")
        FAILED.flush()
        return

    saved = 0

    for img_url in tqdm(img_urls, desc=f"Images for {title}", unit="img"):
        if quit_flag:
            return

        try:
            data = requests.get(img_url, headers=HEADERS, timeout=15).content
            saved += 1
            filename = f"{title}_{saved}.jpg"
            filepath = os.path.join(folder, filename)

            with open(filepath, "wb") as f:
                f.write(data)

        except Exception as e:
            print(f"Error downloading {img_url}: {e}")
            continue

    print(f"\nSaved {saved} images for {title}")

def clean_text_block(text):
    # Replace double colons
    text = text.replace("::", ": ")

    # Add spacing before capital letters that start new sections
    text = text.replace("See details", "\nSee details")
    text = text.replace("Located in:", "\nLocated in:")
    text = text.replace("Delivery:", "\nDelivery:")
    text = text.replace("Returns:", "\nReturns:")
    text = text.replace("Payments:", "\nPayments:")
    text = text.replace("Condition:", "\nCondition:")
    text = text.replace("Seller notes:", "\nSeller notes:")
    text = text.replace("Brand:", "\nBrand:")
    text = text.replace("Type:", "\nType:")
    text = text.replace("Fastening:", "\nFastening:")
    text = text.replace("Country of Origin:", "\nCountry of Origin:")
    text = text.replace("To Fit:", "\nTo Fit:")
    text = text.replace("Lens Fitting:", "\nLens Fitting:")
    text = text.replace("EAN:", "\nEAN:")

    # Remove double spaces
    text = " ".join(text.split())

    return text.strip()

# ---------------------------------------------------------
# URL loader
# ---------------------------------------------------------
def load_urls():
    urls = []
    if os.path.exists("urls.txt"):
        with open("urls.txt", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("www."):
                    line = "https://" + line
                if line.startswith("http"):
                    urls.append(line)
    return urls

# ---------------------------------------------------------
# Run
# ---------------------------------------------------------
URL_LIST = load_urls()

for url in tqdm(URL_LIST, desc="Listings", unit="listing"):
    if quit_flag:
        break
    download_images(url)

print("\nAll done.")
FAILED.close()

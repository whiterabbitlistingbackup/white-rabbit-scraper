import os
import re
import io
import zipfile
import tempfile
import requests
from bs4 import BeautifulSoup
import streamlit as st
import subprocess
subprocess.run(["playwright", "install", "chromium"], check=False)

# ────────────────────────────────────────────────────────────────
#        ***       
#      **   **     
#     **     **    
#     **     **         ****
#     **     **       **    ****
#     **    **       *   **    **
#      **   *       *   ** ***  **
#       **   *     *   **    **  *
#        **  **   **  **       ** 
#        **    **    **        
#       *              *
#      *    0     0     *
#     *    /   @   \     *
#     *    \__/ \__/     *
#       *       W       *
#         **         **   
#           ***********
#
#                 WHITE RABBIT SCRAPER (Streamlit)
# ────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
    "Referer": "https://www.ebay.co.uk/",
    "Cookie": "ebay=%5Esbf%3D%23000000%5E"
}

# ───────────────── helpers ─────────────────

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

        matches = re.findall(r'"name":"([^"]+)"', text)
        for m in matches:
            if len(m) < 3:
                continue
            if m.isupper():
                continue
            if "_" in m:
                continue
            if m.lower() in ["name", "jsonld", "search", "information"]:
                continue
            category_candidates.append(m)

    category_candidates = list(dict.fromkeys(category_candidates))
    real = [c for c in category_candidates if c[0].isupper() and " " in c]

    if real:
        return " > ".join(real[:5])

    return "UnknownCategory"

def extract_description(soup, html, url):
    iframe = soup.find("iframe", {"id": "desc_ifr"})
    if iframe and iframe.get("src"):
        iframe_url = iframe["src"]
        if iframe_url.startswith("//"):
            iframe_url = "https:" + iframe_url
        try:
            r = requests.get(iframe_url, headers=HEADERS, timeout=15)
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
            r = requests.get(iframe_url, headers=HEADERS, timeout=15)
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

def process_single_url(url, base_output_dir):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
    except:
        return None, "Failed to load page."

    html = r.text
    soup = BeautifulSoup(html, "html.parser")

    title = extract_title(soup)
    condition = extract_condition(soup)
    price = extract_price(soup)
    category = extract_category(soup)
    description = extract_description(soup, html, url)
    specifics = extract_item_specifics(soup)

    folder = f"{title}_{condition}"
    folder = folder.replace("__", "_")[:120]
    folder_path = os.path.join(base_output_dir, folder)
    os.makedirs(folder_path, exist_ok=True)

    full_path = os.path.join(folder_path, "full_item.txt")
    with open(full_path, "w", encoding="utf-8") as f:
        f.write("=== BASIC INFO ===\n")
        f.write(f"Title: {title}\n")
        f.write(f"Condition: {condition}\n")
        f.write(f"Price: {price}\n")
        f.write(f"Category: {category}\n")
        f.write(f"URL: {url}\n\n")

        f.write("=== DESCRIPTION ===\n")
        f.write(description.strip() + "\n\n")

        f.write("=== ITEM SPECIFICS ===\n")
        if specifics:
            for key, val in specifics.items():
                f.write(f"{key}: {val}\n")
        else:
            f.write("No item specifics found.\n")

    img_urls = extract_gallery_images(soup)
    if not img_urls:
        img_urls = extract_gallery_json(html)

    img_urls = [normalise_image(u) for u in img_urls]
    img_urls = [u for u in img_urls if u.lower().endswith("s-l1600.jpg")]
    img_urls = list(dict.fromkeys(img_urls))

    saved = 0
    for img_url in img_urls:
        try:
            data = requests.get(img_url, headers=HEADERS, timeout=15).content
            saved += 1
            filename = f"{title}_{saved}.jpg"
            filepath = os.path.join(folder_path, filename)
            with open(filepath, "wb") as f:
                f.write(data)
        except:
            continue

    return folder_path, None

def zip_directory(base_dir):
    mem_file = io.BytesIO()
    with zipfile.ZipFile(mem_file, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(base_dir):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, base_dir)
                zf.write(full_path, rel_path)
    mem_file.seek(0)
    return mem_file

# ───────────────── Streamlit UI ─────────────────

st.title("White Rabbit eBay Scraper 🐇")
st.write("Paste one eBay URL per line. The app will create folders, full_item.txt, and download full‑res images.")

urls_text = st.text_area("eBay item URLs", height=200, placeholder="https://www.ebay.co.uk/itm/...\nhttps://www.ebay.co.uk/itm/...")

run_button = st.button("Run scraper")

if run_button:
    urls = [u.strip() for u in urls_text.splitlines() if u.strip()]
    if not urls:
        st.error("No URLs provided.")
    else:
        st.info(f"Processing {len(urls)} listing(s)…")
        progress = st.progress(0)
        status = st.empty()

        with tempfile.TemporaryDirectory() as tmpdir:
            for i, url in enumerate(urls, start=1):
                status.write(f"Processing {i}/{len(urls)}: {url}")
                _, err = process_single_url(url, tmpdir)
                progress.progress(i / len(urls))

            st.success("Done. Building ZIP…")
            zip_bytes = zip_directory(tmpdir)

        st.download_button(
            label="Download results as ZIP",
            data=zip_bytes,
            file_name="white_rabbit_results.zip",
            mime="application/zip"
        )

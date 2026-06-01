import streamlit as st
import pandas as pd
import subprocess
from playwright.sync_api import sync_playwright

# --- Install Playwright browser on Streamlit Cloud ---
subprocess.run(["playwright", "install", "chromium"], check=False)

st.title("🐇 White Rabbit Scraper — Playwright Edition")
st.write("Paste your eBay listing URLs below. One per line.")

# --- Scraper function using Playwright ---
def scrape_images(urls):
    results = []

    with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-software-rasterizer"
        ]
    )
    page = browser.new_page()

        for url in urls:
            st.write(f"Scraping: {url}")
            try:
                page.goto(url, timeout=60000)
                page.wait_for_load_state("networkidle")

                # Grab ALL images on the page
                imgs = page.query_selector_all("img")
                img_urls = []

                for img in imgs:
                    src = img.get_attribute("src")
                    if src and "s-l" in src:
                        img_urls.append(src)

                results.append({
                    "Listing URL": url,
                    "Image Count": len(img_urls),
                    "Images": img_urls
                })

            except Exception as e:
                results.append({
                    "Listing URL": url,
                    "Image Count": 0,
                    "Images": [],
                    "Error": str(e)
                })

        browser.close()

    return results

# --- UI Input ---
input_text = st.text_area("Enter URLs here:")

if st.button("Start Scraping"):
    urls = [u.strip() for u in input_text.split("\n") if u.strip()]

    if not urls:
        st.error("No URLs provided.")
    else:
        st.info("Scraping in progress… please wait.")
        data = scrape_images(urls)

        df = pd.DataFrame(data)
        st.success("Scraping complete!")
        st.dataframe(df)

        # Optional: allow CSV download
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", csv, "results.csv", "text/csv")

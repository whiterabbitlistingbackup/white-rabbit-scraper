import streamlit as st
import pandas as pd
import subprocess
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse

# --- Install Playwright browser on Streamlit Cloud (cached) ---
@st.cache_resource
def install_playwright_browsers():
    subprocess.run(["playwright", "install", "chromium"], check=False)

install_playwright_browsers()

st.title("🐇 White Rabbit Scraper — Playwright Edition")
st.write("Paste your eBay listing URLs below. One per line.")

# --- URL Validation ---
def is_valid_url(url):
    """Validate URL format"""
    try:
        result = urlparse(url)
        return all([result.scheme in ['http', 'https'], result.netloc])
    except Exception:
        return False

# --- Scraper function using Playwright ---
def scrape_images(urls):
    results = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Create progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, url in enumerate(urls):
            # Update progress
            progress = (idx + 1) / len(urls)
            progress_bar.progress(progress)
            status_text.text(f"Scraping {idx + 1}/{len(urls)}: {url}")
            
            try:
                page.goto(url, timeout=60000, wait_until="domcontentloaded")
                
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
                    "Images": img_urls,
                    "Status": "✅ Success"
                })
                
            except TimeoutError:
                results.append({
                    "Listing URL": url,
                    "Image Count": 0,
                    "Images": [],
                    "Status": "⏱️ Timeout",
                    "Error": "Page load timeout"
                })
                
            except Exception as e:
                error_msg = str(e)
                if "crashed" in error_msg.lower():
                    status = "❌ Browser crashed (page too heavy)"
                elif "net::ERR_NAME_NOT_RESOLVED" in error_msg:
                    status = "❌ Invalid domain"
                elif "net::ERR_CONNECTION" in error_msg:
                    status = "❌ Connection failed"
                else:
                    status = "❌ Error"
                
                results.append({
                    "Listing URL": url,
                    "Image Count": 0,
                    "Images": [],
                    "Status": status,
                    "Error": error_msg[:100]
                })
        
        browser.close()
    
    return results

# --- UI Input ---
input_text = st.text_area("Enter URLs here (one per line):")

if st.button("Start Scraping", type="primary"):
    urls = [u.strip() for u in input_text.split("\n") if u.strip()]
    
    if not urls:
        st.error("❌ No URLs provided.")
    else:
        # Validate URLs
        invalid_urls = [u for u in urls if not is_valid_url(u)]
        valid_urls = [u for u in urls if is_valid_url(u)]
        
        if invalid_urls:
            st.warning(f"⚠️ {len(invalid_urls)} invalid URL(s) found and skipped:")
            for url in invalid_urls:
                st.text(f"  • {url}")
        
        if valid_urls:
            st.info(f"🔄 Scraping {len(valid_urls)} URL(s)… please wait.")
            data = scrape_images(valid_urls)
            
            df = pd.DataFrame(data)
            st.success("✅ Scraping complete!")
            
            # Display results
            st.dataframe(df, use_container_width=True)
            
            # Summary stats
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total URLs", len(df))
            with col2:
                successful = len(df[df["Status"].str.contains("Success", na=False)])
                st.metric("Successful", successful)
            with col3:
                total_images = df["Image Count"].sum()
                st.metric("Total Images", int(total_images))
            
            # Download options
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name="results.csv",
                mime="text/csv"
            )

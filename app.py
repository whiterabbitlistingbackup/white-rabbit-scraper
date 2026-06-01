import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import io
import zipfile
from urllib.parse import urlparse

st.title("🐇 White Rabbit Scraper")
st.write("Paste your eBay listing URLs below. One per line.")

# --- URL Validation ---
def is_valid_url(url):
    """Validate URL format"""
    try:
        result = urlparse(url)
        return all([result.scheme in ['http', 'https'], result.netloc])
    except Exception:
        return False

# --- Scraper function using requests + BeautifulSoup ---
def scrape_images(urls):
    results = []
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, url in enumerate(urls):
        progress = (idx + 1) / len(urls)
        progress_bar.progress(progress)
        status_text.text(f"Scraping {idx + 1}/{len(urls)}: {url}")
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find all images
            img_tags = soup.find_all('img')
            img_urls = []
            
            for img in img_tags:
                src = img.get('src') or img.get('data-src')
                if src:
                    # Convert relative URLs to absolute
                    if src.startswith('/'):
                        src = 'https://ebay.com' + src
                    if src.startswith('http'):
                        img_urls.append(src)
            
            results.append({
                "Listing URL": url,
                "Image Count": len(img_urls),
                "Images": "\n".join(img_urls) if img_urls else "No images found",
                "Status": "✅ Success" if img_urls else "⚠️ No images found"
            })
            
        except requests.Timeout:
            results.append({
                "Listing URL": url,
                "Image Count": 0,
                "Images": "",
                "Status": "⏱️ Timeout"
            })
            
        except Exception as e:
            results.append({
                "Listing URL": url,
                "Image Count": 0,
                "Images": "",
                "Status": f"❌ Error: {str(e)[:50]}"
            })
    
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
                total_images = df[df["Status"].str.contains("Success", na=False)]["Image Count"].sum()
                st.metric("Total Images", int(total_images))
            
            # Download as CSV
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name="ebay_images.csv",
                mime="text/csv"
            )

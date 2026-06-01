import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import time

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

# --- Scraper function using cloudscraper ---
def scrape_images(urls):
    results = []
    
    # Create cloudscraper instance (bypasses Cloudflare)
    scraper = cloudscraper.create_scraper()
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, url in enumerate(urls):
        progress = (idx + 1) / len(urls)
        progress_bar.progress(progress)
        status_text.text(f"Scraping {idx + 1}/{len(urls)}: {url}")
        
        try:
            # Reduce delay - only every 20 requests
            if idx > 0 and idx % 20 == 0:
                time.sleep(0.5)
            
            response = scraper.get(
                url, 
                timeout=10,
                allow_redirects=True
            )
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # eBay stores images in multiple ways
            img_urls = set()
            
            # Method 1: Direct img tags
            for img in soup.find_all('img'):
                src = img.get('src') or img.get('data-src')
                if src and ('ebayimg' in src or 's-l' in src or 'picsum' in src):
                    img_urls.add(src)
            
            # Method 2: Picture tags with sources
            for picture in soup.find_all('picture'):
                for source in picture.find_all('source'):
                    src = source.get('srcset')
                    if src:
                        img_urls.add(src.split()[0])
            
            # Method 3: Look for image URLs in script/JSON
            for script in soup.find_all('script'):
                if script.string and 'ebayimg' in script.string:
                    import re
                    urls_found = re.findall(r'https://[^\s"<>]+\.(?:jpg|jpeg|png|gif)', script.string)
                    img_urls.update(urls_found)
            
            img_list = list(img_urls)
            
            results.append({
                "Listing URL": url,
                "Image Count": len(img_list),
                "Images": "\n".join(img_list) if img_list else "No images found",
                "Status": "✅ Success" if img_list else "⚠️ No images"
            })
            
        except Exception as e:
            error_msg = str(e)
            if '403' in error_msg or 'Forbidden' in error_msg:
                status = "❌ 403 Blocked"
            elif 'Timeout' in error_msg or 'timeout' in error_msg:
                status = "⏱️ Timeout"
            else:
                status = f"❌ {error_msg[:40]}"
            
            results.append({
                "Listing URL": url,
                "Image Count": 0,
                "Images": "",
                "Status": status
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

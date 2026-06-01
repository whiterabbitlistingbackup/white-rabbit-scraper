import streamlit as st
import re

st.title("🐇 White Rabbit — URL Pre‑Processor (Option C)")
st.write("Paste your eBay listing URLs below. This app cleans and validates them, then outputs a `urls.txt` file for your local scraper.")

# ---------------------------------------------------------
# URL cleaning
# ---------------------------------------------------------
def clean_url(url):
    url = url.strip()

    # Fix missing https
    if url.startswith("www."):
        url = "https://" + url

    # Only accept valid eBay item URLs
    pattern = r"(https:\/\/www\.ebay\.co\.uk\/itm\/\d+)"
    match = re.search(pattern, url)
    if match:
        return match.group(1)

    return None

# ---------------------------------------------------------
# UI
# ---------------------------------------------------------
input_text = st.text_area("Paste URLs here (one per line):")

if st.button("Process URLs"):
    raw_lines = input_text.split("\n")
    cleaned = []

    for line in raw_lines:
        url = clean_url(line)
        if url:
            cleaned.append(url)

    cleaned = list(dict.fromkeys(cleaned))  # remove duplicates

    if not cleaned:
        st.error("No valid eBay item URLs found.")
    else:
        st.success(f"Processed {len(cleaned)} valid URLs.")

        # Show preview
        st.write("### Cleaned URLs:")
        st.write("\n".join(cleaned))

        # Prepare downloadable file
        urls_text = "\n".join(cleaned).encode("utf-8")
        st.download_button(
            label="Download urls.txt",
            data=urls_text,
            file_name="urls.txt",
            mime="text/plain"
        )

        st.info("Download `urls.txt` and place it next to your local scraper. Then run your desktop script normally.")

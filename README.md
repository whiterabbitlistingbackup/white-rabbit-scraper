# White Rabbit eBay Scraper - Desktop Edition

## 🚀 Quick Start

### 1. Install
```bash
pip install -r requirements.txt
```

### 2. Run Locally
```bash
streamlit run app.py
```

Opens in browser at http://localhost:8501

### 3. Build Windows .exe (Optional)
```bash
build.bat
```

Then share the `.exe` from `dist/` folder

---

## 📋 Features

✅ **Paste URLs directly** or upload CSV/TXT  
✅ **Extracts:** Title, Condition, Price, Images, Description  
✅ **Batch processing** with adjustable delays  
✅ **Export CSV** with full details  
✅ **Download image URLs** for future use  

---

## 💰 Monetization

### Option 1: Desktop App (Recommended)
1. Build `.exe` with `build.bat`
2. Sell on Gumroad/Lemonsqueezy
3. One-time purchase: $19-49
4. Users run locally (no IP blocking)

### Option 2: SaaS (With Proxies)
- Add residential proxies ($50-200/mo)
- Host on your server
- Charge per API call or subscription

---

## 🔧 How It Works

1. User provides eBay listing URLs
2. Scrapes HTML + JSON for images
3. Extracts: title, condition, price, description
4. Exports as CSV with image URLs
5. User can download images separately

---

## ⚠️ Notes

- Works best when run locally (eBay trusts home IPs)
- Streamlit Cloud gets IP-blocked (use residential proxies for that)
- Add delays between requests (default 0.3s) to avoid rate limiting
- Respects eBay's robots.txt and terms

---

## 📦 File Structure

```
white-rabbit-scraper/
├── app.py              # Main Streamlit app
├── requirements.txt    # Dependencies
├── build.spec          # PyInstaller config
├── build.bat           # Build script (Windows)
└── README.md           # This file
```

---

## 🎯 Next Steps

1. Test locally: `streamlit run app.py`
2. Build .exe: `build.bat`
3. Upload to Gumroad
4. Start selling! 🚀


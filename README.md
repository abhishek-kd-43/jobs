# 💼 OnlyJobs – India's Smartest Job Portal

OnlyJobs is a highly automated job board and aggregator that tracks government notifications, private sector openings, remote roles, results, and admit cards from 13+ reliable sources.

### 🚀 [Live Demo](https://abhishek-kd-43.github.io/jobs/)

---

## 🔥 Key Features

- **Automated Daily Scraping**: Scrapers run 3x daily (8:15 AM, 1:30 PM, and 8:15 PM IST) to ensure fresh data.
- **Categorized Listings**: 
  - **Government Jobs**: Latest notifications from Sarkari Result, FreeJobAlert, etc.
  - **Private Sector**: Openings from top companies.
  - **Remote Roles**: Global opportunities from platforms like WeWorkRemotely.
- **Smart Tracking**: Integrated tracking for Admit Cards and Answer Keys.
- **Modern UI**: Clean, responsive dashboard designed for speed and usability.

## 🛠️ Tech Stack

- **Frontend**: Clean HTML5, CSS3, and modern JavaScript.
- **Backend/Scraper**: Python 3 with `BeautifulSoup4` and `lxml`.
- **Automation**: GitHub Actions for scheduled scraping and deployment.
- **Hosting**: GitHub Pages.

## 🤖 How it Works

The system uses a Python-based scraper (`scraper.py`) that fetches data from multiple RSS feeds and HTML sources. The scraped data is stored in `data.json` and `scrape_status.json`, which are then used by the frontend to render the job listings dynamically.

1. **Scrape**: GitHub Actions triggers the Python script.
2. **Process**: The script parses 13+ sources, deduplicates, and limits entries for performance.
3. **Deploy**: Changes are committed to the repository, triggering a GitHub Pages redeploy.

## 📈 Current Stats
- **Sources Scraped**: 13+
- **Update Frequency**: 3x Daily
- **Total active jobs**: 361+ (as of last scrape)

---

Developed with ❤️ as a smart job dashboard.

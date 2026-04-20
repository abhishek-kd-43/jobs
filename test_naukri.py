import sys
import os
from scraper import scrape_naukri_private_jobs, empty_scrape_result

os.environ['SCRAPER_API_KEY'] = "232a1e1f363e2229f7c979c6778ed58d"
res = empty_scrape_result()
counts = {key: 0 for key in res}
seen_urls = set()
scrape_naukri_private_jobs(res, counts, seen_urls)
print(f"Total Naukri jobs: {len(res['private_jobs'])}")

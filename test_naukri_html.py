import os
from scraper import request_api_soup

os.environ['SCRAPER_API_KEY'] = "232a1e1f363e2229f7c979c6778ed58d"
try:
    soup = request_api_soup('https://www.naukri.com/jobs-in-india', render_js=True)
    with open('naukri_test.html', 'w') as f:
        f.write(str(soup))
    print("Saved HTML")
except Exception as e:
    print(f"Error: {e}")

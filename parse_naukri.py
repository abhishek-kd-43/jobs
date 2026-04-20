from bs4 import BeautifulSoup
with open('naukri_test.html') as f:
    soup = BeautifulSoup(f, 'html.parser')

added = 0
for card in soup.select('div.srp-jobtuple-wrapper'):
    title_el = card.select_one('a.title')
    company_el = card.select_one('a.comp-name')
    if not title_el or not company_el:
        print("Missing title or company")
        continue

    title = title_el.get_text(' ', strip=True)
    job_url = title_el.get('href', '')
    if not title or not job_url:
        print("Empty title or job_url")
        continue
    
    added += 1

print(f"Total: {added}")

import requests
from bs4 import BeautifulSoup, NavigableString, Tag
import json
import os
import re
import hashlib
import time
import random
import traceback
from datetime import date
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import escape
from urllib.parse import urljoin, urlparse, urldefrag

env_file = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_file):
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            os.environ[k.strip()] = v.strip().strip("'").strip('"')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xhtml+xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-IN,en;q=0.9,hi;q=0.8',
}

# ─────────────────────────────────────────────
# COMPETITOR DOMAINS — every link/image pointing
# to these will be stripped or replaced
# ─────────────────────────────────────────────
COMPETITOR_DOMAINS = [
    'sarkariresult.com', 'sarkariresult', 'sarkari result',
    'freejobalert.com', 'freejobalert', 'free job alert',
    'sarkariexam.com',  'sarkariexam',  'sarkari exam',
    'naukri.com', 'shine.com', 'freshersworld.com', 'rojgarresult.com',
    'sarkari naukri', 'sarkarinaukri', 'careersage.in', 'employmentnews',
    'indGovtJobs', 'sarkariwallahs', 'sarkarimaster',
]

APP_STORE_PATTERNS = [
    'play.google.com', 'apps.apple.com', 'app.adjust.com',
    'onelink.me', 'apkpure.com', 'apkmirror.com',
    'download app', 'get app', 'install app', 'download now the app',
    'google play', 'app store', 'available on play store',
    'download on the', 'android app', 'ios app',
]

SOCIAL_DOMAINS = [
    'facebook.com', 'twitter.com', 'instagram.com', 'youtube.com', 'youtu.be',
    'whatsapp.com', 'wa.me', 't.me', 'telegram.me', 'linkedin.com',
    'pinterest.com', 'snapchat.com',
]

# Unsplash image categories for different post types
IMAGE_KEYWORDS = {
    'latest_jobs': ['government,jobs,india', 'exam,study,india', 'recruitment,india', 'sarkari,naukri'],
    'results':     ['exam,result,india', 'board,result', 'merit,list', 'government,exam'],
    'admit_cards': ['admit,card,exam', 'hall,ticket,exam', 'exam,india', 'recruitment,exam'],
    'answer_keys': ['answer,key,exam', 'exam,paper,india', 'question,paper', 'exam,solution'],
    'private_jobs': ['office,teamwork,career', 'startup,technology,office', 'business,meeting,team', 'career,interview,workspace'],
    'remote_jobs': ['remote,work,laptop', 'work from home,office', 'digital nomad,workspace', 'online,team,computer'],
}

STATE_PORTALS_FILE = os.path.join(os.path.dirname(__file__), 'state_portals.json')
DATA_FILE = os.path.join(os.path.dirname(__file__), 'data.json')
SCRAPE_STATUS_FILE = os.path.join(os.path.dirname(__file__), 'scrape_status.json')

try:
    with open(STATE_PORTALS_FILE, 'r', encoding='utf-8') as f:
        STATE_DIRECTORY = json.load(f).get('states', [])
except Exception:
    STATE_DIRECTORY = []

STATE_PORTAL_MAP = {
    entry['name']: entry.get('portal_url', '')
    for entry in STATE_DIRECTORY
    if entry.get('type') in ('state', 'ut')
}

GENERIC_SCOPE_MAP = {
    entry['name']: entry.get('portal_url', '')
    for entry in STATE_DIRECTORY
    if entry.get('type') == 'central'
}

STATE_SIGNAL_PATTERNS = {
    entry['name']: [
        re.compile(r'(?<![a-z])' + re.escape(alias.lower()) + r'(?![a-z])', re.IGNORECASE)
        for alias in entry.get('aliases', [])
    ]
    for entry in STATE_DIRECTORY
    if entry.get('type') in ('state', 'ut')
}

CENTRAL_SCOPE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r'\bcentral govt\b', r'\bcentral government\b', r'\bupsc\b', r'\bssc\b',
        r'\brailway\b', r'\brrb\b', r'\bibps\b', r'\bsbi\b', r'\bindian army\b',
        r'\bindian navy\b', r'\bindian air ?force\b', r'\bagniveer\b',
        r'\bdrdo\b', r'\bnielit\b', r'\bctet\b', r'\bneet\b', r'\bnta\b'
    ]
]

ALL_INDIA_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r'\ball india\b', r'\ball states\b', r'\bnationwide\b',
        r'\bpan india\b', r'\bacross india\b'
    ]
]

CATEGORIES = ('results', 'admit_cards', 'latest_jobs', 'answer_keys', 'private_jobs', 'remote_jobs')
CATEGORY_LIMITS = {
    'latest_jobs': int(os.getenv('ONLYJOBS_LIMIT_LATEST_JOBS', '36')),
    'results': int(os.getenv('ONLYJOBS_LIMIT_RESULTS', '20')),
    'admit_cards': int(os.getenv('ONLYJOBS_LIMIT_ADMIT_CARDS', '20')),
    'answer_keys': int(os.getenv('ONLYJOBS_LIMIT_ANSWER_KEYS', '18')),
    'private_jobs': int(os.getenv('ONLYJOBS_LIMIT_PRIVATE_JOBS', '24')),
    'remote_jobs': int(os.getenv('ONLYJOBS_LIMIT_REMOTE_JOBS', '24')),
}
OFFICIAL_SOURCE_LIMITS = {
    'upsc_active': int(os.getenv('ONLYJOBS_LIMIT_UPSC_ACTIVE', '12')),
    'upsc_recruitment': int(os.getenv('ONLYJOBS_LIMIT_UPSC_RECRUITMENT', '6')),
    'ibps_recruitment': int(os.getenv('ONLYJOBS_LIMIT_IBPS_RECRUITMENT', '12')),
    'rac_recruitment': int(os.getenv('ONLYJOBS_LIMIT_RAC_RECRUITMENT', '4')),
}
LISTING_PAGE_LIMIT = int(os.getenv('ONLYJOBS_LISTING_PAGE_LIMIT', '10'))
FJA_STATE_PAGE_LIMIT = int(os.getenv('ONLYJOBS_FJA_STATE_PAGE_LIMIT', '1'))
REQUEST_DELAY_SECONDS = float(os.getenv('ONLYJOBS_REQUEST_DELAY_SECONDS', '0.15'))
CURRENT_YEAR_PATTERN = re.compile(r'\b20(2[4-9]|3\d)\b')
CONTENT_SIGNAL_TERMS = {
    'latest_jobs': [
        'online form', 'apply online', 'recruitment', 'vacancy', 'vacancies',
        'notification', 'jobs', 'job', 'bharti', 'post', 'posts', 'walk in'
    ],
    'results': ['result', 'results', 'score', 'score card', 'merit', 'selection', 'cut off'],
    'admit_cards': ['admit', 'exam city', 'hall ticket', 'call letter', 'schedule', 'city intimation'],
    'answer_keys': ['answer key', 'response sheet', 'objection', 'provisional key', 'final key'],
}
COMMON_SKIP_TITLES = {
    'home', 'view more', 'search', 'contact us', 'important', 'syllabus', 'notifications',
    'latest notifications', 'latest jobs', 'admit card', 'answer key', 'exam results'
}
SITE_SKIP_PATHS = {
    'SR': ['/latestjob/', '/result/', '/admitcard/', '/answerkey/', '/syllabus/', '/search/', '/contactus/', '/important/'],
    'FJA': ['/government-jobs/', '/state-government-jobs/', '/latest-notifications/', '/admit-card/', '/exam-results/', '/answer-key/', '/bank-jobs/', '/teaching-faculty-jobs/', '/engineering-jobs/', '/railway-jobs/', '/police-defence-jobs/', '/employment-news/', '/search-jobs/'],
    'SE': ['/category/'],
    'SU': ['/category/', '/page/'],
}
SITE_PAGE_CONFIGS = {
    'SR': [
        {'url': 'https://www.sarkariresult.com/latestjob/', 'category': 'latest_jobs'},
        {'url': 'https://www.sarkariresult.com/result/', 'category': 'results'},
        {'url': 'https://www.sarkariresult.com/admitcard/', 'category': 'admit_cards'},
        {'url': 'https://www.sarkariresult.com/answerkey/', 'category': 'answer_keys'},
    ],
    'FJA': [
        {'url': 'https://www.freejobalert.com/latest-notifications/', 'category': 'latest_jobs'},
        {'url': 'https://www.freejobalert.com/government-jobs/', 'category': 'latest_jobs'},
        {'url': 'https://www.freejobalert.com/bank-jobs/', 'category': 'latest_jobs'},
        {'url': 'https://www.freejobalert.com/railway-jobs/', 'category': 'latest_jobs'},
        {'url': 'https://www.freejobalert.com/police-defence-jobs/', 'category': 'latest_jobs'},
        {'url': 'https://www.freejobalert.com/teaching-faculty-jobs/', 'category': 'latest_jobs'},
        {'url': 'https://www.freejobalert.com/admit-card/', 'category': 'admit_cards'},
        {'url': 'https://www.freejobalert.com/exam-results/', 'category': 'results'},
        {'url': 'https://www.freejobalert.com/answer-key/', 'category': 'answer_keys'},
    ],
    'SE': [
        {'url': 'https://www.sarkariexam.com/category/top-online-form/', 'category': 'latest_jobs'},
        {'url': 'https://www.sarkariexam.com/category/hot-job/', 'category': 'latest_jobs'},
        {'url': 'https://www.sarkariexam.com/category/exam-result/', 'category': 'results'},
        {'url': 'https://www.sarkariexam.com/category/admit-card/', 'category': 'admit_cards'},
        {'url': 'https://www.sarkariexam.com/category/answer-keys/', 'category': 'answer_keys'},
    ],
    'SU': [
        {'url': 'https://sarkariujala.com/category/new-update', 'category': 'latest_jobs'},
        {'url': 'https://sarkariujala.com/category/form', 'category': 'latest_jobs'},
        {'url': 'https://sarkariujala.com/category/sarkari-result', 'category': 'results'},
        {'url': 'https://sarkariujala.com/category/admit-card', 'category': 'admit_cards'},
    ],
}
FJA_STATE_PAGE_MAP = {
    'Andhra Pradesh': 'https://www.freejobalert.com/ap-government-jobs/',
    'Assam': 'https://www.freejobalert.com/assam-government-jobs/',
    'Bihar': 'https://www.freejobalert.com/bihar-government-jobs/',
    'Chhattisgarh': 'https://www.freejobalert.com/chhattisgarh-government-jobs/',
    'Delhi': 'https://www.freejobalert.com/delhi-government-jobs/',
    'Gujarat': 'https://www.freejobalert.com/gujarat-government-jobs/',
    'Haryana': 'https://www.freejobalert.com/haryana-government-jobs/',
    'Himachal Pradesh': 'https://www.freejobalert.com/hp-government-jobs/',
    'Jharkhand': 'https://www.freejobalert.com/jharkhand-government-jobs/',
    'Karnataka': 'https://www.freejobalert.com/karnataka-government-jobs/',
    'Kerala': 'https://www.freejobalert.com/kerala-government-jobs/',
    'Madhya Pradesh': 'https://www.freejobalert.com/mp-government-jobs/',
    'Maharashtra': 'https://www.freejobalert.com/maharashtra-government-jobs/',
    'Odisha': 'https://www.freejobalert.com/odisha-government-jobs/',
    'Punjab': 'https://www.freejobalert.com/punjab-government-jobs/',
    'Rajasthan': 'https://www.freejobalert.com/rajasthan-government-jobs/',
    'Tamil Nadu': 'https://www.freejobalert.com/tn-government-jobs/',
    'Telangana': 'https://www.freejobalert.com/telangana-government-jobs/',
    'Uttar Pradesh': 'https://www.freejobalert.com/up-government-jobs/',
    'Uttarakhand': 'https://www.freejobalert.com/uttarakhand-government-jobs/',
    'West Bengal': 'https://www.freejobalert.com/wb-government-jobs/',
}
IBPS_ALLOWED_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r'\bPSB\b', r'\bIDBI\b', r'\bIIFCL\b', r'\bNABFID\b', r'\bNABARD\b',
        r'\bSIDBI\b', r'\bSBI\b', r'\bPNB\b', r'\bBOB\b', r'\bBank of India\b',
        r'\bIndian Bank\b', r'\bCentral Bank\b', r'\bCanara\b', r'\bUnion Bank\b'
    ]
]
IBPS_SKIP_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [r'\bprogramme\b', r'\bpgip\b', r'\bco-operative\b', r'\bspecial recruitment drive\b']
]


def category_limit(category: str) -> int:
    return CATEGORY_LIMITS.get(category, LISTING_PAGE_LIMIT)


def official_source_limit(source_name: str) -> int:
    return OFFICIAL_SOURCE_LIMITS.get(source_name, LISTING_PAGE_LIMIT)


def empty_scrape_result() -> dict:
    return {category: [] for category in CATEGORIES}


def normalize_target_url(url: str) -> str:
    if not url:
        return ''
    normalized, _ = urldefrag(url.strip())
    return normalized


def same_source_domain(full_url: str, site_type: str) -> bool:
    host = urlparse(full_url).netloc.lower()
    if site_type == 'SR':
        return 'sarkariresult.com' in host
    if site_type == 'FJA':
        return 'freejobalert.com' in host
    if site_type == 'SE':
        return 'sarkariexam.com' in host
    if site_type == 'SU':
        return 'sarkariujala.com' in host
    return False


def title_has_signal(title: str, href: str, category: str) -> bool:
    text = f'{title} {href}'.lower()
    if CURRENT_YEAR_PATTERN.search(text):
        return True
    return any(term in text for term in CONTENT_SIGNAL_TERMS.get(category, []))


def is_listing_candidate(title: str, full_url: str, site_type: str, category: str) -> bool:
    if not title or not full_url:
        return False

    clean_title = ' '.join(title.split()).strip()
    title_lower = clean_title.lower()
    if title_lower in COMMON_SKIP_TITLES or len(clean_title) < 10:
        return False

    if is_social_href(full_url):
        return False

    parsed = urlparse(full_url)
    if parsed.scheme not in ('http', 'https'):
        return False

    path_lower = parsed.path.lower()
    if any(path_lower == skip.rstrip('/') or path_lower.startswith(skip) for skip in SITE_SKIP_PATHS.get(site_type, [])):
        return False

    if not same_source_domain(full_url, site_type):
        return False

    return title_has_signal(clean_title, full_url, category)


def append_entry(res: dict, counts: dict, seen_urls: set, entry: dict) -> bool:
    if not entry:
        return False

    category = entry.get('_cat')
    if category not in counts:
        return False

    url_key = normalize_target_url(entry.get('original_url', ''))
    if not url_key or url_key in seen_urls or counts[category] >= category_limit(category):
        return False

    seen_urls.add(url_key)
    res[category].append(entry)
    counts[category] += 1
    return True


def scrape_listing_page(page_url: str, site_type: str, category: str, res: dict, counts: dict, seen_urls: set, per_page_limit: int = None):
    if counts[category] >= category_limit(category):
        return

    limit = min(per_page_limit or LISTING_PAGE_LIMIT, category_limit(category) - counts[category])
    if limit <= 0:
        return

    print(f"  📄 [{site_type}] Listing {page_url}")
    try:
        session = requests.Session()
        session.mount('https://', requests.adapters.HTTPAdapter(max_retries=3))
        html = session.get(page_url, headers=HEADERS, timeout=30).text
        soup = BeautifulSoup(html, 'html.parser')
        page_seen = set()
        added = 0

        for link in soup.find_all('a', href=True):
            title = ' '.join(link.get_text(' ', strip=True).split())
            full_url = normalize_target_url(urljoin(page_url, link.get('href', '')))

            if not is_listing_candidate(title, full_url, site_type, category):
                continue
            if full_url in page_seen or full_url in seen_urls:
                continue

            page_seen.add(full_url)
            entry = generate_entry(title, full_url, site_type, category)
            if append_entry(res, counts, seen_urls, entry):
                added += 1

            if added >= limit or counts[category] >= category_limit(category):
                break
    except Exception as exc:
        print(f"  ❌ Listing page error [{site_type}] {page_url}: {exc}")


def dedupe_category_entries(entries):
    deduped = []
    seen = set()
    for entry in entries:
        key = normalize_target_url(entry.get('original_url', '')) or entry.get('id')
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped


def normalize_spaces(value: str) -> str:
    return ' '.join(str(value or '').split()).strip()


def format_indian_number(value: int) -> str:
    digits = str(int(value))
    if len(digits) <= 3:
        return digits
    last_three = digits[-3:]
    rest = digits[:-3]
    parts = []
    while len(rest) > 2:
        parts.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        parts.insert(0, rest)
    return ','.join(parts + [last_three])


def years_in_text(value: str):
    return [int(match.group(0)) for match in re.finditer(r'\b20\d{2}\b', value or '')]


def is_current_or_future_notice(value: str) -> bool:
    years = years_in_text(value)
    return not years or max(years) >= date.today().year


def should_keep_ibps_recruitment(org: str, role: str) -> bool:
    combined = normalize_spaces(f'{org} {role}')
    if any(pattern.search(combined) for pattern in IBPS_SKIP_PATTERNS):
        return False
    return any(pattern.search(combined) for pattern in IBPS_ALLOWED_PATTERNS)


def request_soup(url: str, timeout: int = 30) -> BeautifulSoup:
    session = requests.Session()
    session.mount('https://', requests.adapters.HTTPAdapter(max_retries=3))
    res = session.get(url, headers=HEADERS, timeout=timeout)
    res.raise_for_status()
    return BeautifulSoup(res.text, 'html.parser')

def request_api_soup(url: str, render_js: bool = False, timeout: int = 45) -> BeautifulSoup:
    api_key = os.getenv('SCRAPER_API_KEY')
    if not api_key:
        raise ValueError("SCRAPER_API_KEY not configured")
    payload = {'api_key': api_key, 'url': url}
    if render_js:
        payload['render'] = 'true'
    
    session = requests.Session()
    session.mount('http://', requests.adapters.HTTPAdapter(max_retries=3))
    res = session.get('http://api.scraperapi.com', params=payload, timeout=timeout)
    res.raise_for_status()
    return BeautifulSoup(res.text, 'html.parser')


def absolute_clean_html(node, base_url: str) -> str:
    if not node:
        return ''

    fragment = BeautifulSoup(str(node), 'html.parser')
    for tag in list(fragment.find_all(['script', 'style', 'iframe', 'noscript', 'svg', 'img', 'meta', 'link'])):
        tag.decompose()

    for anchor in fragment.find_all('a', href=True):
        anchor['href'] = normalize_target_url(urljoin(base_url, anchor.get('href', '')))
        anchor['target'] = '_blank'
        anchor['rel'] = 'nofollow noopener'

    return str(fragment)


def build_official_content_html(source_name: str, summary_lines=None, links=None, extra_html: str = '') -> str:
    summary_lines = [normalize_spaces(line) for line in (summary_lines or []) if normalize_spaces(line)]
    link_pairs = []
    seen_urls = set()
    for label, href in links or []:
        clean_href = normalize_target_url(href)
        clean_label = normalize_spaces(label)
        if not clean_href or not clean_label or clean_href in seen_urls:
            continue
        seen_urls.add(clean_href)
        link_pairs.append((clean_label, clean_href))

    summary_html = ''
    if summary_lines:
        summary_html = ''.join(
            f'<li style="margin:0 0 8px 0;">{escape(line)}</li>'
            for line in summary_lines
        )
        summary_html = f'<ul style="margin:0;padding-left:20px;color:#334155;line-height:1.8;">{summary_html}</ul>'

    links_html = ''
    if link_pairs:
        links_html = ''.join(
            f'<li style="margin:0 0 8px 0;"><a href="{escape(href, quote=True)}" target="_blank" rel="nofollow noopener" style="color:#1D4ED8;text-decoration:none;">{escape(label)}</a></li>'
            for label, href in link_pairs
        )
        links_html = (
            '<div style="background:#FFF7ED;border:1px solid #FED7AA;border-radius:12px;padding:16px 18px;margin-top:18px;">'
            '<div style="font-size:14px;font-weight:800;color:#9A3412;margin-bottom:10px;">Official Links</div>'
            f'<ul style="margin:0;padding-left:20px;color:#7C2D12;line-height:1.8;">{links_html}</ul>'
            '</div>'
        )

    intro = (
        '<div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:12px;padding:18px 20px;margin-bottom:18px;">'
        f'<p style="margin:0 0 12px 0;color:#0F172A;font-weight:700;">Direct update from the official {escape(source_name)} recruitment portal.</p>'
        f'{summary_html}'
        '</div>'
    )
    return f'{intro}{extra_html}{links_html}'


def create_official_entry(title: str, url: str, source_label: str, content_html: str, info: dict = None, category: str = 'latest_jobs') -> dict:
    safe_title = normalize_spaces(title)
    post_id = hashlib.md5(f'{category}:{url}'.encode('utf-8')).hexdigest()
    parsed = BeautifulSoup(content_html or '', 'html.parser')
    derived_info = extract_key_info(safe_title, parsed if content_html else None)
    final_info = {
        'last_date': 'See Notification',
        'vacancies': 'Various',
        'exam_date': 'As per Schedule',
        'category': 'Central Govt',
        'applicant_count': None,
        'applicant_count_display': '',
        'applicant_metric_label': 'Not officially disclosed',
        'applicant_metric_note': 'Applicant or participant totals have not been officially disclosed yet.',
        'applicant_metric_basis': 'not_disclosed',
    }
    final_info.update(derived_info)
    if info:
        final_info.update({key: value for key, value in info.items() if value})

    seo_html = generate_seo_post(safe_title, category, final_info, content_html or '', url)
    state_data = infer_state_data(safe_title, content_html or '')
    return {
        "id": post_id,
        "title": clean_text(safe_title),
        "original_url": url,
        "content_html": seo_html,
        "source": source_label,
        "_cat": category,
        "applicant_count": final_info.get('applicant_count'),
        "applicant_count_display": final_info.get('applicant_count_display'),
        "applicant_metric_label": final_info.get('applicant_metric_label'),
        "applicant_metric_note": final_info.get('applicant_metric_note'),
        "applicant_metric_basis": final_info.get('applicant_metric_basis'),
        "states": state_data['states'],
        "state_label": state_data['state_label'],
        "official_state_portal": state_data['official_state_portal']
    }


def create_market_job_entry(title: str, url: str, source_label: str, category: str, company: str = '',
                            location: str = '', compensation: str = '', experience: str = '',
                            posted_at: str = '', skills=None, summary_html: str = '',
                            job_meta: dict = None) -> dict:
    content_html = build_market_job_content_html(
        company=company,
        location=location,
        compensation=compensation,
        experience=experience,
        posted_at=posted_at,
        skills=skills,
        summary_html=summary_html,
        source_url=url,
    )
    info = {
        'last_date': 'Apply ASAP',
        'vacancies': 'See listing',
        'exam_date': posted_at or 'Recently posted',
        'category': 'Remote Job' if category == 'remote_jobs' else 'Private Job',
    }
    if job_meta:
        info.update({key: value for key, value in job_meta.items() if value})

    entry = create_official_entry(
        title=title,
        url=url,
        source_label=source_label,
        content_html=content_html,
        info=info,
        category=category,
    )
    entry['company'] = clean_text(company)
    entry['job_location'] = clean_text(location) if location else ('Remote' if category == 'remote_jobs' else '')
    entry['salary'] = clean_text(compensation)
    entry['experience'] = clean_text(experience)
    entry['posted_at'] = posted_at
    entry['skills'] = [clean_text(skill) for skill in (skills or []) if clean_text(skill)]
    if entry['job_location']:
        entry['state_label'] = entry['job_location']
        entry['states'] = []
        entry['official_state_portal'] = ''
    return entry


def get_hero_image_url(category: str, title: str) -> str:
    """Return an Unsplash image URL. Uses a deterministic seed so the same post
    always gets the same image."""
    keywords_list = IMAGE_KEYWORDS.get(category, IMAGE_KEYWORDS['latest_jobs'])
    # Use picsum for reliable fallback (no API key needed)
    seed = abs(hash(title)) % 1000
    return f"https://picsum.photos/seed/{seed}/800/400"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json_atomic(path: str, payload: dict):
    tmp_path = path + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, path)


def strip_tags_text(value: str) -> str:
    if not value:
        return ''
    return normalize_spaces(BeautifulSoup(value, 'html.parser').get_text(' ', strip=True))


def format_currency_range(min_value, max_value, symbol: str = '$') -> str:
    try:
        min_number = int(min_value or 0)
    except (TypeError, ValueError):
        min_number = 0
    try:
        max_number = int(max_value or 0)
    except (TypeError, ValueError):
        max_number = 0

    if min_number and max_number:
        return f'{symbol}{min_number:,} - {symbol}{max_number:,}'
    if min_number:
        return f'From {symbol}{min_number:,}'
    if max_number:
        return f'Up to {symbol}{max_number:,}'
    return ''


def format_market_date(value: str) -> str:
    raw = normalize_spaces(value)
    if not raw:
        return ''

    try:
        if 'T' in raw:
            dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
            return dt.strftime('%d %b %Y')
    except ValueError:
        pass

    try:
        dt = parsedate_to_datetime(raw)
        return dt.strftime('%d %b %Y')
    except (TypeError, ValueError):
        return raw


def clean_market_fragment(html: str, base_url: str) -> str:
    if not html:
        return ''
    fragment = BeautifulSoup(html, 'html.parser')
    for tag in list(fragment.find_all(['script', 'style', 'iframe', 'img', 'noscript', 'svg', 'form'])):
        tag.decompose()
    for anchor in fragment.find_all('a', href=True):
        anchor['href'] = normalize_target_url(urljoin(base_url, anchor.get('href', '')))
        anchor['target'] = '_blank'
        anchor['rel'] = 'nofollow noopener'
    return str(fragment)


def build_market_job_content_html(company: str, location: str, compensation: str, experience: str,
                                  posted_at: str, skills, summary_html: str, source_url: str) -> str:
    skills = [normalize_spaces(skill) for skill in (skills or []) if normalize_spaces(skill)]
    summary_lines = [
        f'Company: {company}' if company else '',
        f'Location: {location}' if location else '',
        f'Compensation: {compensation}' if compensation else '',
        f'Experience: {experience}' if experience else '',
        f'Posted / updated: {posted_at}' if posted_at else '',
    ]

    extra_parts = []
    if skills:
        skills_html = ''.join(
            f'<span style="display:inline-block;background:#EFF6FF;color:#1D4ED8;padding:6px 10px;border-radius:999px;font-size:12px;font-weight:700;margin:0 6px 6px 0;">{escape(skill)}</span>'
            for skill in skills[:10]
        )
        extra_parts.append(
            '<div style="margin:16px 0 0;">'
            '<div style="font-size:14px;font-weight:800;color:#0F172A;margin-bottom:10px;">Key Skills</div>'
            f'<div>{skills_html}</div>'
            '</div>'
        )

    clean_summary_html = clean_market_fragment(summary_html, source_url)
    if clean_summary_html:
        extra_parts.append(
            '<div style="margin-top:18px;">'
            '<div style="font-size:14px;font-weight:800;color:#0F172A;margin-bottom:10px;">Role Snapshot</div>'
            f'<div style="color:#334155;line-height:1.8;">{clean_summary_html}</div>'
            '</div>'
        )

    return build_official_content_html(
        source_name='career portal',
        summary_lines=summary_lines,
        links=[('Open original listing', source_url)],
        extra_html=''.join(extra_parts),
    )


def is_competitor_href(href: str, current_site_type: str = None) -> bool:
    if not href:
        return False
    href_lower = href.lower()
    
    # Don't skip our own site's links
    site_domain_map = {'SR': 'sarkariresult.com', 'FJA': 'freejobalert.com', 'SE': 'sarkariexam.com'}
    current_domain = site_domain_map.get(current_site_type, 'impossible_domain')
    
    for domain in COMPETITOR_DOMAINS:
        if domain.lower() in href_lower:
            # If it's our own domain, keep it
            if domain.lower() in current_domain:
                continue
            return True
    for pattern in APP_STORE_PATTERNS:
        if pattern.lower() in href_lower:
            return True
    return False


def is_social_href(href: str) -> bool:
    if not href:
        return False
    href_lower = href.lower()
    for domain in SOCIAL_DOMAINS:
        if domain in href_lower:
            return True
    return False


def clean_text(text: str) -> str:
    """Replace all competitor text references with OnlyJobs."""
    if not text: return ""
    # Competitor brand names
    text = re.sub(r'Sarkari\s*Result\.?\s*Com|Sarkari\s*Result|sarkariresult\.com|SARKARI\s*RESULT|sarkariresult', 'OnlyJobs', text, flags=re.IGNORECASE)
    text = re.sub(r'freejobalert\.com|Free\s*Job\s*Alert|FreeJobAlert|freejobalert', 'OnlyJobs', text, flags=re.IGNORECASE)
    text = re.sub(r'sarkariexam\.com|Sarkari\s*Exam|SarkariExam|sarkariexam', 'OnlyJobs', text, flags=re.IGNORECASE)
    text = re.sub(r'rojgarresult\.com|RojgarResult|rojgarresult', 'OnlyJobs', text, flags=re.IGNORECASE)
    text = re.sub(r'sarkarinaukri\.com|Sarkari\s*Naukri|sarkarinaukri', 'OnlyJobs', text, flags=re.IGNORECASE)
    # App download mentions
    for pat in APP_STORE_PATTERNS:
        text = re.sub(re.escape(pat), '', text, flags=re.IGNORECASE)
    return text


def deep_clean_soup(soup_elem, current_site_type=''):
    """
    Aggressively clean a BeautifulSoup element:
    - Remove all scripts, styles, iframes, ads, share widgets, app banners
    - Strip href/src attributes pointing to competitors, app stores, social media
    - Remove entire <a> and <img> tags that point to competitors or apps
    - Replace competitor text with OnlyJobs
    """
    if not soup_elem:
        return soup_elem

    # 1. Remove unwanted tags entirely
    for tag in list(soup_elem.find_all(['script', 'style', 'iframe', 'noscript', 'meta', 'link'])):
        tag.decompose()

    # 2. Remove ads / share / social / app-download divs by class/id keywords
    junk_classes = re.compile(
        r'share|social|addtoany|fb-|whatsapp|telegram|app-download|download-app|'
        r'mobile-app|get-app|playstore|appstore|ad-|ads-|advertisement|'
        r'comments?|comment-form|related-posts?|newsletter|subscribe|signup|'
        r'sidebar|widget|breadcrumb|navigation|footer|header|menu|navbar|'
        r'popup|modal|overlay|cookie|gdpr|notification|alert-bar',
        re.IGNORECASE
    )
    for tag in list(soup_elem.find_all(True)):
        if not tag.parent: continue
        cls = ' '.join(tag.get('class', [])) if tag.get('class') else ''
        tag_id = str(tag.get('id', ''))
        if junk_classes.search(cls) or junk_classes.search(tag_id):
            tag.decompose()

    # 3. Strip competitor / app-store / social links
    for a_tag in list(soup_elem.find_all('a')):
        if not a_tag.parent: continue
        href = a_tag.get('href', '')
        text_lower = a_tag.get_text(strip=True).lower()

        if is_competitor_href(href, current_site_type):
            a_tag.decompose()
            continue
        if is_social_href(href):
            a_tag.decompose()
            continue
        for pat in APP_STORE_PATTERNS:
            if pat.lower() in text_lower:
                a_tag.decompose()
                break
        else:
            if href and href.startswith('http') and 'gov.in' not in href and 'nic.in' not in href:
                a_tag['href'] = href
                if a_tag.has_attr('target'): del a_tag['target']
                a_tag.attrs = {k: v for k, v in a_tag.attrs.items() if k not in ['onclick', 'onmouseover']}

    # 4. Strip competitor images / logos
    for img in list(soup_elem.find_all('img')):
        if not img.parent: continue
        src = img.get('src', '')
        alt = img.get('alt', '')
        if is_competitor_href(src, current_site_type):
            img.decompose()
            continue
        if any(d in alt.lower() for d in ['sarkari', 'freejobalert', 'sarkariexam']):
            img.decompose()
            continue

    # 5. Replace competitor text in all text nodes and common attributes
    for tag in list(soup_elem.find_all(True)):
        if not tag.parent: continue
        for attr in ['title', 'alt', 'aria-label']:
            if tag.has_attr(attr):
                tag[attr] = clean_text(tag[attr])

    for text_node in list(soup_elem.find_all(string=True)):
        if isinstance(text_node, NavigableString):
            new_text = clean_text(str(text_node))
            if new_text != str(text_node):
                text_node.replace_with(new_text)

    return soup_elem


def extract_key_info(title: str, content_soup) -> dict:
    """Try to extract key dates, vacancies, last date from the parsed content."""
    info = {
        'last_date': 'See Notification',
        'vacancies': 'Various',
        'exam_date': 'As per Schedule',
        'category': 'Central Govt',
        'applicant_count': None,
        'applicant_count_display': '',
        'applicant_metric_label': 'Not officially disclosed',
        'applicant_metric_note': 'Applicant or participant totals have not been officially disclosed yet.',
        'applicant_metric_basis': 'not_disclosed',
    }
    if not title: title = "Government Job Update 2026"
    text = content_soup.get_text(' ', strip=True) if content_soup else ''

    # Last date
    m = re.search(r'last\s*date[:\s]+([A-Z][a-z]{2,8}[\s\d,]+\d{4}|[\d/\-]+\s*\d{4})', text, re.IGNORECASE)
    if not m:
         m = re.search(r'last\s*date\s*[:\-]\s*([\d\-\/]+)', text, re.IGNORECASE)
    if m:
        info['last_date'] = m.group(1).strip()

    # Vacancies
    m = re.search(r'(\d[\d,]+)\s*(?:post|vacancy|vacancies|seat)', text, re.IGNORECASE)
    if m:
        info['vacancies'] = m.group(1).strip()

    # Exam date
    m = re.search(r'exam\s*date[:\s]+([A-Z][a-z]{2,8}[\s\d,]+\d{4}|[\d/\-]+\s*\d{4})', text, re.IGNORECASE)
    if m:
        info['exam_date'] = m.group(1).strip()

    # Category from title
    for cat in ['UPSC', 'SSC', 'Railway', 'RRB', 'Banking', 'IBPS', 'SBI', 'Defence', 'Army', 'Navy', 'Air Force', 'Police', 'Teaching', 'CTET', 'TET']:
        if cat.lower() in title.lower():
            info['category'] = cat
            break

    info.update(extract_applicant_info(title, text))
    return info


def applicant_info_default() -> dict:
    return {
        'applicant_count': None,
        'applicant_count_display': '',
        'applicant_metric_label': 'Not officially disclosed',
        'applicant_metric_note': 'Applicant or participant totals have not been officially disclosed yet.',
        'applicant_metric_basis': 'not_disclosed',
    }


def parse_count_token(number_text: str, unit_text: str = '') -> int:
    normalized = (number_text or '').replace(',', '').strip()
    unit = (unit_text or '').strip().lower()
    if not normalized:
        return 0
    value = float(normalized)
    multiplier = 1
    if unit == 'lakh':
        multiplier = 100000
    elif unit == 'crore':
        multiplier = 10000000
    elif unit == 'million':
        multiplier = 1000000
    return int(round(value * multiplier))


def extract_applicant_info(title: str, text: str) -> dict:
    info = applicant_info_default()
    content = normalize_spaces(text)
    if not content:
        return info

    patterns = [
        ('applied', re.compile(r'(?:(?:over|more than|around|nearly|approximately)\s+)?(\d[\d,]*(?:\.\d+)?)\s*(lakh|crore|million)?\s+(?:candidates?|applicants?)\s+(?:have\s+)?applied\b', re.IGNORECASE)),
        ('registered', re.compile(r'(?:(?:over|more than|around|nearly|approximately)\s+)?(\d[\d,]*(?:\.\d+)?)\s*(lakh|crore|million)?\s+(?:candidates?|applicants?)\s+(?:have\s+been\s+)?registered\b', re.IGNORECASE)),
        ('applications received', re.compile(r'(?:(?:over|more than|around|nearly|approximately)\s+)?(\d[\d,]*(?:\.\d+)?)\s*(lakh|crore|million)?\s+applications?\s+(?:were\s+|have\s+been\s+)?received\b', re.IGNORECASE)),
        ('appeared', re.compile(r'(?:(?:over|more than|around|nearly|approximately)\s+)?(\d[\d,]*(?:\.\d+)?)\s*(lakh|crore|million)?\s+(?:candidates?|students?)\s+(?:have\s+)?appeared\b', re.IGNORECASE)),
        ('qualified', re.compile(r'(?:(?:over|more than|around|nearly|approximately)\s+)?(\d[\d,]*(?:\.\d+)?)\s*(lakh|crore|million)?\s+(?:candidates?|students?)\s+(?:have\s+)?qualified\b', re.IGNORECASE)),
        ('registered', re.compile(r'total\s+registered\s+(?:candidates?|applicants?)\s*[:\-]?\s*(\d[\d,]*(?:\.\d+)?)\s*(lakh|crore|million)?', re.IGNORECASE)),
        ('applied', re.compile(r'total\s+(?:candidates?|applicants?)\s+applied\s*[:\-]?\s*(\d[\d,]*(?:\.\d+)?)\s*(lakh|crore|million)?', re.IGNORECASE)),
        ('appeared', re.compile(r'total\s+(?:candidates?|students?)\s+appeared\s*[:\-]?\s*(\d[\d,]*(?:\.\d+)?)\s*(lakh|crore|million)?', re.IGNORECASE)),
    ]

    label_map = {
        'applied': 'Applied',
        'registered': 'Registered',
        'applications received': 'Applications Received',
        'appeared': 'Appeared',
        'qualified': 'Qualified',
    }

    for basis, pattern in patterns:
        match = pattern.search(content)
        if not match:
            continue
        count = parse_count_token(match.group(1), match.group(2) if match.lastindex and match.lastindex >= 2 else '')
        if count <= 0:
            continue
        count_display = format_indian_number(count)
        human_basis = label_map.get(basis, 'Reported')
        info.update({
            'applicant_count': count,
            'applicant_count_display': count_display,
            'applicant_metric_label': human_basis,
            'applicant_metric_note': f'Source page mentions {count_display} candidates {basis.lower()}.',
            'applicant_metric_basis': basis,
        })
        return info

    return info


def html_to_text(value: str) -> str:
    if not value:
        return ''
    if '<' in value and '>' in value:
        return BeautifulSoup(value, 'html.parser').get_text(' ', strip=True)
    return value


def infer_state_data(title: str, content_html: str) -> dict:
    combined_text = ' '.join(
        part for part in [clean_text(title or ''), html_to_text(content_html or '')[:2500]]
        if part
    )
    normalized = re.sub(r'\s+', ' ', combined_text).strip().lower()

    if re.search(r'\bremote\b', normalized):
        return {'states': [], 'state_label': 'Remote', 'official_state_portal': ''}

    if any(pattern.search(normalized) for pattern in ALL_INDIA_PATTERNS):
        return {'states': [], 'state_label': 'All India', 'official_state_portal': GENERIC_SCOPE_MAP.get('All India', '')}

    matched_states = []
    for state_name, patterns in STATE_SIGNAL_PATTERNS.items():
        if any(pattern.search(normalized) for pattern in patterns):
            matched_states.append(state_name)

    if matched_states:
        unique_states = []
        for state_name in matched_states:
            if state_name not in unique_states:
                unique_states.append(state_name)
        if len(unique_states) > 3:
            return {'states': unique_states, 'state_label': 'All States', 'official_state_portal': ''}
        portal = STATE_PORTAL_MAP.get(unique_states[0], '') if len(unique_states) == 1 else ''
        return {'states': unique_states, 'state_label': ' / '.join(unique_states), 'official_state_portal': portal}

    if any(pattern.search(normalized) for pattern in CENTRAL_SCOPE_PATTERNS):
        return {'states': [], 'state_label': 'Central Govt', 'official_state_portal': GENERIC_SCOPE_MAP.get('Central Govt', '')}

    return {'states': [], 'state_label': 'All India', 'official_state_portal': GENERIC_SCOPE_MAP.get('All India', '')}


def generate_seo_post(title: str, category: str, info: dict, clean_content_html: str, original_url: str) -> str:
    """
    Generate a full SEO-optimised professional blog-style HTML post.
    """
    hero_img = get_hero_image_url(category, title)
    safe_title = clean_text(title).replace('"', '&quot;')
    safe_heading = clean_text(title)
    meta_desc = clean_text(f"Check complete details for {title}. Includes important dates, application link, eligibility, syllabus and result info — updated live on OnlyJobs.")

    cat_label_map = {
        'latest_jobs': 'Latest Jobs 2026',
        'results':     'OnlyJobs Result 2026',
        'admit_cards': 'Admit Card 2026',
        'answer_keys': 'Answer Key 2026',
        'private_jobs': 'Private Jobs 2026',
        'remote_jobs': 'Remote Jobs 2026',
    }
    cat_label = cat_label_map.get(category, 'OnlyJobs Update 2026')

    toc_items_map = {
        'latest_jobs': ['Important Dates', 'Vacancies &amp; Category', 'Age Limit', 'Qualification', 'Application Fee', 'How to Apply', 'Official Links'],
        'results':     ['Result Status', 'Cut Off Marks', 'Score Card Download', 'Merit List', 'Next Steps', 'Official Links'],
        'admit_cards': ['Exam Date', 'Download Admit Card', 'Important Instructions', 'Exam Pattern', 'Official Links'],
        'answer_keys': ['Download Answer Key', 'Raise Objections', 'Expected Cut Off', 'Result Date', 'Official Links'],
        'private_jobs': ['Role Snapshot', 'Company Details', 'Location &amp; Salary', 'Experience', 'Skills', 'Original Listing'],
        'remote_jobs': ['Role Snapshot', 'Remote Location', 'Compensation', 'Experience', 'Skills', 'Original Listing'],
    }
    toc_items = toc_items_map.get(category, toc_items_map['latest_jobs'])
    toc_html = ''.join([f'<li><a href="#sec-{i+1}" style="color:#1D4ED8;text-decoration:none;">→ {item}</a></li>' for i, item in enumerate(toc_items)])
    applicant_display = info.get('applicant_count_display') or 'Not Disclosed'
    applicant_label = info.get('applicant_metric_label') or 'Not officially disclosed'
    applicant_note = info.get('applicant_metric_note') or 'Applicant or participant totals have not been officially disclosed yet.'

    highlights_html = f"""
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:20px 0;">
      <div style="background:#EFF6FF;border:1px solid #BFDBFE;border-radius:10px;padding:14px;text-align:center;">
        <div style="font-size:22px;">📅</div>
        <div style="font-size:11px;color:#64748B;font-weight:700;text-transform:uppercase;margin:4px 0;">Last Date</div>
        <div style="font-size:14px;font-weight:700;color:#1D4ED8;">{info['last_date']}</div>
      </div>
      <div style="background:#ECFDF5;border:1px solid #A7F3D0;border-radius:10px;padding:14px;text-align:center;">
        <div style="font-size:22px;">💼</div>
        <div style="font-size:11px;color:#64748B;font-weight:700;text-transform:uppercase;margin:4px 0;">Vacancies</div>
        <div style="font-size:14px;font-weight:700;color:#059669;">{info['vacancies']}</div>
      </div>
      <div style="background:#FFF3EB;border:1px solid #FED7AA;border-radius:10px;padding:14px;text-align:center;">
        <div style="font-size:22px;">📝</div>
        <div style="font-size:11px;color:#64748B;font-weight:700;text-transform:uppercase;margin:4px 0;">Exam Date</div>
        <div style="font-size:14px;font-weight:700;color:#E85D04;">{info['exam_date']}</div>
      </div>
      <div style="background:#F5F3FF;border:1px solid #DDD6FE;border-radius:10px;padding:14px;text-align:center;">
        <div style="font-size:22px;">🏛️</div>
        <div style="font-size:11px;color:#64748B;font-weight:700;text-transform:uppercase;margin:4px 0;">Category</div>
        <div style="font-size:14px;font-weight:700;color:#7C3AED;">{info['category']}</div>
      </div>
      <div style="background:#FFF7ED;border:1px solid #FED7AA;border-radius:10px;padding:14px;text-align:center;">
        <div style="font-size:22px;">👥</div>
        <div style="font-size:11px;color:#64748B;font-weight:700;text-transform:uppercase;margin:4px 0;">Applicants</div>
        <div style="font-size:14px;font-weight:700;color:#C2410C;">{applicant_display}</div>
        <div style="font-size:11px;color:#7C2D12;margin-top:4px;">{applicant_label}</div>
      </div>
    </div>
    """

    applicant_note_html = f"""
    <div style="background:#FFF7ED;border:1px solid #FED7AA;border-radius:10px;padding:14px 16px;margin:18px 0 24px;">
      <div style="font-size:13px;font-weight:800;color:#9A3412;margin-bottom:6px;">All-India Applications / Participation</div>
      <div style="font-size:13.5px;color:#7C2D12;line-height:1.7;">{applicant_note}</div>
    </div>
    """

    full_html = f"""
<article style="font-family:'Figtree',sans-serif;max-width:900px;margin:0 auto;color:#2D2D3A;line-height:1.7;">
  <div style="border-radius:14px;overflow:hidden;margin-bottom:22px;position:relative;height:260px;background:#1A1A2E;">
    <img src="{hero_img}" alt="{safe_title}" style="width:100%;height:100%;object-fit:cover;opacity:0.55;" onerror="this.style.display='none'"/>
    <div style="position:absolute;inset:0;display:flex;flex-direction:column;justify-content:flex-end;padding:22px 24px;background:linear-gradient(to top,rgba(0,0,0,0.7) 0%,transparent 60%);">
      <span style="display:inline-block;background:#E85D04;color:#fff;font-size:11px;font-weight:700;padding:3px 10px;border-radius:20px;margin-bottom:8px;width:fit-content;">{cat_label}</span>
      <h1 style="font-size:clamp(17px,2.5vw,24px);font-weight:800;color:#fff;line-height:1.3;margin:0;">{safe_heading}</h1>
    </div>
  </div>
  <div style="display:flex;gap:16px;flex-wrap:wrap;font-size:12.5px;color:#64748B;padding:12px 16px;background:#F7F8FC;border-radius:8px;margin-bottom:20px;align-items:center;">
    <span>📅 Updated: {date.today().strftime('%d %b %Y')}</span>
    <span>✍️ By: <strong style="color:#E85D04;">OnlyJobs Editorial Team</strong></span>
    <span>🌐 Source: <a href="{original_url}" target="_blank" rel="nofollow noopener" style="color:#1D4ED8;">Official Notification</a></span>
  </div>
  <p style="font-size:15px;color:#374151;margin-bottom:18px;">{meta_desc}</p>
  <h2 style="font-size:18px;font-weight:800;color:#1A1A2E;border-left:4px solid #E85D04;padding-left:12px;margin:24px 0 12px;">⚡ Key Highlights</h2>
  {highlights_html}
  {applicant_note_html}
  <div style="background:#F0F2F8;border-radius:10px;padding:16px 20px;margin:24px 0;">
    <div style="font-weight:800;font-size:14px;color:#1A1A2E;margin-bottom:10px;">📋 Quick Navigation</div>
    <ol style="margin:0;padding-left:20px;color:#374151;font-size:13.5px;line-height:2;">{toc_html}</ol>
  </div>
  <h2 style="font-size:18px;font-weight:800;color:#1A1A2E;border-left:4px solid #E85D04;padding-left:12px;margin:28px 0 16px;">📄 Complete Details &amp; Notification</h2>
  <div id="scraped-body" style="overflow-x:auto;">
    {clean_content_html if clean_content_html.strip() else '<p>Detailed content available on the official website.</p>'}
  </div>
  <div style="background:linear-gradient(135deg,#1A1A2E 0%,#3730A3 100%);border-radius:12px;padding:24px;margin:30px 0;text-align:center;color:#fff;">
    <h3 style="margin-bottom:8px;">Get Instant Job Alerts on OnlyJobs</h3>
    <p style="font-size:13px;margin-bottom:16px;">Join 4.8 Cr+ aspirants. Free mock tests, live results, and daily job updates.</p>
    <a href="index.html" style="background:#E85D04;color:#fff;padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:700;">🏠 Browse All Jobs</a>
  </div>
</article>
"""
    return full_html


def fetch_inner_content_clean(url: str, site_type: str, category: str = 'latest_jobs') -> str:
    """Fetch the post page, deep-clean it, return SEO-wrapped professional HTML."""
    try:
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(max_retries=3)
        session.mount('https://', adapter)
        
        res = session.get(url, headers=HEADERS, timeout=30)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')

        title_tag = soup.find('h1')
        page_title = title_tag.get_text(strip=True) if title_tag else ""

        content = None
        if site_type == 'SR':
            content = soup.find('div', id='post') or soup.find('div', class_=re.compile(r'postab|post-content|post_detail'))
        elif site_type in ['FJA', 'SE', 'SU']:
            content = soup.find('div', class_=re.compile(r'entry-content|post-content|single-post')) or soup.find('article')

        if not content:
            tables = soup.find_all('table')
            if tables: content = max(tables, key=lambda t: len(str(t)))

        if not content: return "", {}

        content = deep_clean_soup(content, site_type)
        info = extract_key_info(page_title or "", content)
        return str(content), info
    except Exception:
        print(f"  ❌ Failed inner [{site_type}] {url}: {traceback.format_exc()}")
        return "", {}


def generate_entry(title: str, url: str, site_type: str, category: str = 'latest_jobs') -> dict:
    post_id = hashlib.md5(f'{category}:{url}'.encode('utf-8')).hexdigest()
    print(f"  🔍 [{site_type}] {title[:70]}...")
    try:
        raw_content_html, info = fetch_inner_content_clean(url, site_type, category)
        if not info: info = extract_key_info(title, None)
        seo_html = generate_seo_post(title, category, info, raw_content_html, url)
        state_data = infer_state_data(title, raw_content_html)
        time.sleep(REQUEST_DELAY_SECONDS)
        return {
            "id": post_id, "title": clean_text(title),
            "original_url": url, "content_html": seo_html,
            "source": site_type, "_cat": category,
            "applicant_count": info.get('applicant_count'),
            "applicant_count_display": info.get('applicant_count_display'),
            "applicant_metric_label": info.get('applicant_metric_label'),
            "applicant_metric_note": info.get('applicant_metric_note'),
            "applicant_metric_basis": info.get('applicant_metric_basis'),
            "states": state_data['states'],
            "state_label": state_data['state_label'],
            "official_state_portal": state_data['official_state_portal']
        }
    except Exception:
        print(f"  ❌ Failed [GEN] {title}: {traceback.format_exc()}")
        return None


def scrape_sarkariresult(limit=None):
    res = empty_scrape_result()
    counts = {key: 0 for key in res}
    seen_urls = set()
    home_limit = min(LISTING_PAGE_LIMIT, 15)
    url = "https://www.sarkariresult.com/"
    print(f"\n📡 Scraping SarkariResult ({url})...")
    try:
        html = requests.get(url, headers=HEADERS, timeout=25).text
        soup = BeautifulSoup(html, 'html.parser')
        columns = soup.find_all('div', id='post')
        mapping = {'Result': 'results', 'Admit Card': 'admit_cards', 'Latest Job': 'latest_jobs', 'Online Form': 'latest_jobs', 'Answer Key': 'answer_keys'}
        for col in columns:
            head_txt = col.get_text().strip().split('\n')[0].strip()
            cat = next((v for k, v in mapping.items() if k.lower() in head_txt.lower()), None)
            if not cat: continue
            for link in col.find_all('a')[:home_limit]:
                title, href = link.text.strip(), link.get('href', '')
                if not title or not href: continue
                full_url = href if href.startswith('http') else url.rstrip('/') + '/' + href.lstrip('/')
                if is_competitor_href(full_url, 'SR'): continue
                e = generate_entry(title, full_url, "SR", cat)
                append_entry(res, counts, seen_urls, e)
                if counts[cat] >= home_limit or counts[cat] >= category_limit(cat):
                    break
    except Exception as e: print(f"  ❌ SR Error: {e}")

    for page in SITE_PAGE_CONFIGS['SR']:
        scrape_listing_page(page['url'], 'SR', page['category'], res, counts, seen_urls)
    return res

def scrape_freejobalert(limit=None):
    res = empty_scrape_result()
    counts = {key: 0 for key in res}
    seen_urls = set()
    home_limit = min(LISTING_PAGE_LIMIT, 15)
    url = "https://www.freejobalert.com/"
    print(f"\n📡 Scraping FreeJobAlert ({url})...")
    try:
        session = requests.Session()
        session.mount('https://', requests.adapters.HTTPAdapter(max_retries=3))
        html = session.get(url, headers=HEADERS, timeout=30).text
        soup = BeautifulSoup(html, 'html.parser')
        mapping = {'Result': 'results', 'Admit Card': 'admit_cards', 'Notification': 'latest_jobs', 'Updates': 'latest_jobs', 'Answer Key': 'answer_keys'}
        headings = soup.find_all(['h2', 'h3', 'div', 'span'], class_=re.compile(r'nutitle|gb-headline|widget-title|section-head', re.I)) or soup.find_all(['h2', 'h3'])
        for h in headings:
            txt = h.get_text().strip()
            cat = next((v for k, v in mapping.items() if k.lower() in txt.lower()), None)
            if not cat: continue
            nxt = h.find_next_sibling('ul') or h.find_next('ul')
            if not nxt: continue
            if counts[cat] >= home_limit:
                continue
            for link in nxt.find_all('a')[:home_limit]:
                title, href = link.text.strip(), link.get('href', '')
                if not title or not href: continue
                full_url = href if href.startswith('http') else 'https://www.freejobalert.com' + href
                if is_competitor_href(full_url, 'FJA'): continue
                e = generate_entry(title, full_url, "FJA", cat)
                append_entry(res, counts, seen_urls, e)
                if counts[cat] >= home_limit or counts[cat] >= category_limit(cat):
                    break
    except Exception as e: print(f"  ❌ FJA Error: {e}")

    for page in SITE_PAGE_CONFIGS['FJA']:
        scrape_listing_page(page['url'], 'FJA', page['category'], res, counts, seen_urls)

    for state_name, page_url in FJA_STATE_PAGE_MAP.items():
        if counts['latest_jobs'] >= category_limit('latest_jobs'):
            break
        scrape_listing_page(page_url, 'FJA', 'latest_jobs', res, counts, seen_urls, per_page_limit=FJA_STATE_PAGE_LIMIT)
    return res

def scrape_sarkariexam(limit=None):
    res = empty_scrape_result()
    counts = {key: 0 for key in res}
    seen_urls = set()
    home_limit = min(LISTING_PAGE_LIMIT, 15)
    url = "https://www.sarkariexam.com/"
    print(f"\n📡 Scraping SarkariExam ({url})...")
    try:
        html = requests.get(url, headers=HEADERS, timeout=30).text
        soup = BeautifulSoup(html, 'html.parser')
        mapping = {'Result': 'results', 'Admit Card': 'admit_cards', 'Exam': 'results', 'Online Form': 'latest_jobs', 'New Updates': 'latest_jobs', 'Answer Key': 'answer_keys'}
        for h in soup.find_all(['h2', 'h3', 'h4']):
            cat = next((v for k, v in mapping.items() if k.lower() in h.get_text().lower()), None)
            if not cat: continue
            if counts[cat] >= home_limit:
                continue
            nxt = h.find_next_sibling('ul') or h.find_next('ul')
            if not nxt: continue
            for link in nxt.find_all('a')[:home_limit]:
                title, href = link.text.strip(), link.get('href', '')
                if not title or not href: continue
                full_url = href if href.startswith('http') else 'https://www.sarkariexam.com' + href
                if is_competitor_href(full_url, 'SE'): continue
                e = generate_entry(title, full_url, "SE", cat)
                append_entry(res, counts, seen_urls, e)
                if counts[cat] >= home_limit or counts[cat] >= category_limit(cat):
                    break
    except Exception as e: print(f"  ❌ SE Error: {e}")

    for page in SITE_PAGE_CONFIGS['SE']:
        scrape_listing_page(page['url'], 'SE', page['category'], res, counts, seen_urls)
    return res

def scrape_sarkariujala(limit=None):
    res = empty_scrape_result()
    counts = {key: 0 for key in res}
    seen_urls = set()
    print(f"\n📡 Scraping SarkariUjala (https://sarkariujala.com/)...")
    for page in SITE_PAGE_CONFIGS['SU']:
        scrape_listing_page(page['url'], 'SU', page['category'], res, counts, seen_urls)
    return res


def scrape_upsc_active_exams(res: dict, counts: dict, seen_urls: set):
    url = 'https://upsc.gov.in/examinations/active-exams'
    print(f"\n🏛️ Scraping UPSC active examinations ({url})...")
    try:
        soup = request_soup(url, timeout=35)
        view = soup.select_one('div.view-content')
        if not view:
            return

        added = 0
        for link in view.select('div.views-row a[href]'):
            if added >= official_source_limit('upsc_active'):
                break

            title = normalize_spaces(link.get_text(' ', strip=True))
            detail_url = normalize_target_url(urljoin(url, link.get('href', '')))
            if not title or not detail_url or detail_url in seen_urls:
                continue

            detail_soup = request_soup(detail_url, timeout=35)
            content = detail_soup.select_one('div.view-content') or detail_soup.select_one('div.region-content')
            content_html = absolute_clean_html(content, detail_url)
            upload_dates = [
                normalize_spaces(node.get_text(' ', strip=True))
                for node in (content.select('.date-display-single') if content else [])
            ]
            intro_html = build_official_content_html(
                'UPSC',
                summary_lines=[
                    'Active examination listed directly on the official UPSC portal.',
                    f'Latest document upload: {upload_dates[0]}' if upload_dates else 'Latest document uploads are available on the official UPSC page.',
                ],
                links=[
                    ('UPSC examination page', detail_url),
                    ('UPSC active examinations list', url),
                ],
                extra_html=content_html,
            )
            entry = create_official_entry(
                title=title,
                url=detail_url,
                source_label='UPSC',
                content_html=intro_html,
                info={
                    'category': 'UPSC',
                    'exam_date': upload_dates[0] if upload_dates else 'As per UPSC schedule',
                    'last_date': 'See UPSC notification',
                    'vacancies': 'See UPSC notification',
                },
            )
            if append_entry(res, counts, seen_urls, entry):
                added += 1
                time.sleep(REQUEST_DELAY_SECONDS)
    except Exception as exc:
        print(f"  ❌ UPSC active exams error: {exc}")


def scrape_upsc_recruitment_ads(res: dict, counts: dict, seen_urls: set):
    url = 'https://upsc.gov.in/recruitment/recruitment-advertisement'
    print(f"\n🏛️ Scraping UPSC recruitment advertisements ({url})...")
    try:
        soup = request_soup(url, timeout=35)
        view = soup.select_one('div.view-content')
        if not view:
            return

        added = 0
        for item in view.select('li'):
            if added >= official_source_limit('upsc_recruitment'):
                break

            title_text = normalize_spaces(item.get_text(' ', strip=True))
            title_text = re.sub(r'\(\s*\d[\d.,]*\s*(?:KB|MB)\s*\)', '', title_text, flags=re.IGNORECASE).strip()
            pdf_link = item.find('a', href=True)
            pdf_url = normalize_target_url(urljoin(url, pdf_link.get('href', ''))) if pdf_link else url
            if not title_text or not pdf_url or pdf_url in seen_urls:
                continue

            title = title_text if title_text.lower().startswith('upsc') else f'UPSC {title_text}'
            content_html = build_official_content_html(
                'UPSC',
                summary_lines=[
                    'Direct recruitment advertisement published on the official UPSC portal.',
                    title_text,
                ],
                links=[
                    ('Advertisement PDF', pdf_url),
                    ('UPSC recruitment advertisements', url),
                ],
            )
            entry = create_official_entry(
                title=title,
                url=pdf_url,
                source_label='UPSC',
                content_html=content_html,
                info={
                    'category': 'UPSC',
                    'last_date': 'See advertisement PDF',
                    'vacancies': 'See advertisement PDF',
                },
            )
            if append_entry(res, counts, seen_urls, entry):
                added += 1
    except Exception as exc:
        print(f"  ❌ UPSC recruitment ads error: {exc}")


def scrape_ibps_recruitments(res: dict, counts: dict, seen_urls: set):
    url = 'https://www.ibps.in/index.php/recruitment'
    print(f"\n🏦 Scraping IBPS recruitments ({url})...")
    try:
        soup = request_soup(url, timeout=35)
        added = 0
        for anchor in soup.select('a[href*="ibpsreg.ibps.in"]'):
            if added >= official_source_limit('ibps_recruitment'):
                break

            href = normalize_target_url(urljoin(url, anchor.get('href', '')))
            container = anchor.find('div', class_='detail-list') or anchor
            org = normalize_spaces(container.select_one('.detail-first-heading').get_text(' ', strip=True) if container.select_one('.detail-first-heading') else 'IBPS')
            role = normalize_spaces(container.select_one('.detail-second-heading').get_text(' ', strip=True) if container.select_one('.detail-second-heading') else anchor.get_text(' ', strip=True))
            date_values = [
                normalize_spaces(node.get_text(' ', strip=True))
                for node in container.select('.detail-third-heading .detail-heading > div')
            ]
            start_date = date_values[0] if len(date_values) > 0 else ''
            end_date = date_values[1] if len(date_values) > 1 else ''
            title = normalize_spaces(f'{org} {role}')
            if not title or not href or href in seen_urls or not should_keep_ibps_recruitment(org, role):
                continue

            content_html = build_official_content_html(
                'IBPS',
                summary_lines=[
                    f'Organisation: {org}',
                    f'Notification: {role}',
                    f'Registration starts: {start_date}' if start_date else '',
                    f'Registration ends: {end_date}' if end_date else '',
                ],
                links=[
                    ('Apply / official recruitment page', href),
                    ('IBPS ongoing recruitments', url),
                ],
            )
            entry = create_official_entry(
                title=title,
                url=href,
                source_label='IBPS',
                content_html=content_html,
                info={
                    'category': 'IBPS',
                    'last_date': end_date or 'See IBPS notification',
                    'exam_date': start_date or 'As per IBPS schedule',
                    'vacancies': 'See notification',
                },
            )
            if append_entry(res, counts, seen_urls, entry):
                added += 1
    except Exception as exc:
        print(f"  ❌ IBPS recruitments error: {exc}")


def scrape_rac_recruitments(res: dict, counts: dict, seen_urls: set):
    url = 'https://rac.gov.in/'
    print(f"\n🧪 Scraping DRDO RAC recruitments ({url})...")
    try:
        soup = request_soup(url, timeout=40)
        added = 0
        for block in soup.select('div[data-bs-target^="#offcanvas"]'):
            if added >= official_source_limit('rac_recruitment'):
                break

            target = (block.get('data-bs-target') or '').strip().lstrip('#')
            offcanvas = soup.find(id=target) if target else None
            if not offcanvas:
                continue

            adv_number = normalize_spaces(block.select_one('.advtHeading').get_text(' ', strip=True) if block.select_one('.advtHeading') else '')
            block_text = normalize_spaces(block.get_text(' ', strip=True))
            last_updated_match = re.search(r'Last updated:\s*(.*?)(?:Closing date:|$)', block_text, re.IGNORECASE)
            closing_match = re.search(r'Closing date:\s*(.+)$', block_text, re.IGNORECASE)
            summary_title = next(
                (
                    normalize_spaces(text)
                    for text in block.stripped_strings
                    if 'selection of' in text.lower() or 'scientist' in text.lower()
                ),
                ''
            )
            title = f"DRDO RAC Advertisement No. {adv_number}".strip()
            if summary_title:
                title = f"{title} - {summary_title}"
            notice_cycle_text = ' '.join(
                part for part in [
                    title,
                    summary_title,
                    closing_match.group(1).strip() if closing_match else '',
                ]
                if part
            )
            if not is_current_or_future_notice(notice_cycle_text):
                continue

            official_links = []
            primary_url = ''
            for anchor in offcanvas.find_all('a', href=True):
                label = normalize_spaces(anchor.get_text(' ', strip=True)) or 'Official link'
                href = normalize_target_url(urljoin(url, anchor.get('href', '')))
                if not href:
                    continue
                if not primary_url and 'advertisement' in label.lower():
                    primary_url = href
                official_links.append((label, href))
            if not primary_url:
                primary_url = url
            if primary_url in seen_urls:
                continue

            detail_html = absolute_clean_html(offcanvas.select_one('.offcanvas-body') or offcanvas, url)
            content_html = build_official_content_html(
                'DRDO RAC',
                summary_lines=[
                    f'Advertisement number: {adv_number}' if adv_number else 'Advertisement available on the official RAC portal.',
                    f'Last updated: {last_updated_match.group(1).strip()}' if last_updated_match else '',
                    f'Closing date: {closing_match.group(1).strip()}' if closing_match else '',
                    summary_title,
                ],
                links=official_links + [('RAC homepage', url)],
                extra_html=detail_html,
            )
            entry = create_official_entry(
                title=title,
                url=primary_url,
                source_label='RAC',
                content_html=content_html,
                info={
                    'category': 'DRDO',
                    'last_date': closing_match.group(1).strip() if closing_match else 'See advertisement',
                    'exam_date': last_updated_match.group(1).strip() if last_updated_match else 'As per RAC schedule',
                    'vacancies': 'See advertisement',
                },
            )
            if append_entry(res, counts, seen_urls, entry):
                added += 1
                time.sleep(REQUEST_DELAY_SECONDS)
    except Exception as exc:
        print(f"  ❌ DRDO RAC recruitments error: {exc}")


def scrape_official_portals(limit=None):
    res = empty_scrape_result()
    counts = {key: 0 for key in res}
    seen_urls = set()

    for scraper_func in [
        scrape_upsc_active_exams,
        scrape_upsc_recruitment_ads,
        scrape_ibps_recruitments,
        scrape_rac_recruitments,
    ]:
        scraper_func(res, counts, seen_urls)

    return res


def scrape_internshala_private_jobs(res: dict, counts: dict, seen_urls: set):
    url = 'https://internshala.com/jobs/'
    print(f"\n💼 Scraping Internshala private jobs ({url})...")
    try:
        soup = request_soup(url, timeout=35)
        for card in soup.select('.individual_internship'):
            if counts['private_jobs'] >= category_limit('private_jobs'):
                break

            title_el = card.select_one('.job-title-href')
            company_el = card.select_one('.company-name')
            if not title_el or not company_el:
                continue

            title = normalize_spaces(title_el.get_text(' ', strip=True))
            job_url = normalize_target_url(urljoin(url, title_el.get('href', '')))
            if not title or not job_url or job_url in seen_urls:
                continue

            row_items = card.select('.detail-row-1 .row-1-item')
            location = normalize_spaces(card.select_one('.locations').get_text(' ', strip=True) if card.select_one('.locations') else '')
            compensation = normalize_spaces(row_items[1].get_text(' ', strip=True) if len(row_items) > 1 else '')
            experience = normalize_spaces(row_items[2].get_text(' ', strip=True) if len(row_items) > 2 else '')
            posted_at = normalize_spaces(card.select_one('.status-success').get_text(' ', strip=True) if card.select_one('.status-success') else '')
            summary_html = str(card.select_one('.about_job .text') or '')
            skills = [normalize_spaces(skill.get_text(' ', strip=True)) for skill in card.select('.job_skill')]

            entry = create_market_job_entry(
                title=title,
                url=job_url,
                source_label='Internshala',
                category='private_jobs',
                company=normalize_spaces(company_el.get_text(' ', strip=True)),
                location=location,
                compensation=compensation,
                experience=experience,
                posted_at=posted_at,
                skills=skills,
                summary_html=summary_html,
            )
            append_entry(res, counts, seen_urls, entry)
    except Exception as exc:
        print(f"  ❌ Internshala error: {exc}")


def scrape_freshersworld_private_jobs(res: dict, counts: dict, seen_urls: set):
    url = 'https://www.freshersworld.com/jobs'
    print(f"\n💼 Scraping Freshersworld private jobs ({url})...")
    try:
        soup = request_soup(url, timeout=35)
        for card in soup.select('.job-container'):
            if counts['private_jobs'] >= category_limit('private_jobs'):
                break

            title_el = card.select_one('.job-new-title .wrap-title.seo_title')
            company_el = card.select_one('.company-name')
            job_url = normalize_target_url(card.get('job_display_url', ''))
            if not title_el or not company_el or not job_url or job_url in seen_urls:
                continue

            raw_title = normalize_spaces(title_el.get_text(' ', strip=True))
            title = normalize_spaces(re.sub(r'\b(?:Less|More)\b', ' ', raw_title))
            location = normalize_spaces(card.select_one('.job-location').get_text(' ', strip=True) if card.select_one('.job-location') else '')
            experience = normalize_spaces(card.select_one('.experience').get_text(' ', strip=True) if card.select_one('.experience') else '')
            detail_spans = [normalize_spaces(el.get_text(' ', strip=True)) for el in card.select('.qualification-block .job-details-span')]
            compensation = detail_spans[0] if detail_spans else ''
            qualification = detail_spans[1] if len(detail_spans) > 1 else ''
            card_text = normalize_spaces(card.get_text(' ', strip=True))
            posted_match = re.search(r'Posted:\s*(.+?)\s+(?:Save|View\s*&\s*Apply|$)', card_text, re.IGNORECASE)
            posted_at = normalize_spaces(posted_match.group(1) if posted_match else '')
            skills = [part.strip() for part in qualification.split(',') if part.strip()]
            summary_html = (
                f'<p>{escape(qualification)}</p>' if qualification else ''
            )

            entry = create_market_job_entry(
                title=title,
                url=job_url,
                source_label='Freshersworld',
                category='private_jobs',
                company=normalize_spaces(company_el.get_text(' ', strip=True)),
                location=location,
                compensation=compensation,
                experience=experience,
                posted_at=posted_at,
                skills=skills,
                summary_html=summary_html,
                job_meta={'last_date': 'Check listing before applying', 'exam_date': posted_at or 'Recently listed'},
            )
            append_entry(res, counts, seen_urls, entry)
    except Exception as exc:
        print(f"  ❌ Freshersworld error: {exc}")


def scrape_naukri_private_jobs(res: dict, counts: dict, seen_urls: set):
    if not os.getenv('SCRAPER_API_KEY'):
        return
    url = 'https://www.naukri.com/jobs-in-india'
    print(f"\n💼 Scraping Naukri private jobs via ScraperAPI ({url})...")
    try:
        soup = request_api_soup(url, render_js=True)
        for card in soup.select('div.srp-jobtuple-wrapper, article.jobTuple'):
            if counts['private_jobs'] >= category_limit('private_jobs'):
                break

            title_el = card.select_one('a.title')
            company_el = card.select_one('a.comp-name')
            if not title_el or not company_el:
                continue

            title = normalize_spaces(title_el.get_text(' ', strip=True))
            job_url = normalize_target_url(title_el.get('href', ''))
            if not title or not job_url or job_url in seen_urls:
                continue

            location = normalize_spaces(card.select_one('.locWdth').get_text(' ', strip=True) if card.select_one('.locWdth') else '')
            experience = normalize_spaces(card.select_one('.expwdth').get_text(' ', strip=True) if card.select_one('.expwdth') else '')
            
            entry = create_market_job_entry(
                title=title,
                url=job_url,
                source_label='Naukri',
                category='private_jobs',
                company=normalize_spaces(company_el.get_text(' ', strip=True)),
                location=location,
                experience=experience,
                summary_html='Apply on Naukri.com to view full details.',
                job_meta={'last_date': 'Check listing before applying'},
            )
            append_entry(res, counts, seen_urls, entry)
    except Exception as exc:
        print(f"  ❌ Naukri error: {exc}")

def scrape_indeed_private_jobs(res: dict, counts: dict, seen_urls: set):
    if not os.getenv('SCRAPER_API_KEY'):
        return
    url = 'https://in.indeed.com/jobs?q=full+time'
    print(f"\n💼 Scraping Indeed private jobs via ScraperAPI ({url})...")
    try:
        soup = request_api_soup(url, render_js=False)
        for card in soup.select('td.resultContent'):
            if counts['private_jobs'] >= category_limit('private_jobs'):
                break

            title_el = card.select_one('h2.jobTitle a')
            company_el = card.select_one('span.companyName')
            if not title_el:
                continue

            title = normalize_spaces(title_el.get_text(' ', strip=True))
            if title.startswith('new'):
                title = title[3:].strip()
            job_url = normalize_target_url(urljoin('https://in.indeed.com', title_el.get('href', '')))
            if not title or not job_url or job_url in seen_urls:
                continue

            location = normalize_spaces(card.select_one('div.companyLocation').get_text(' ', strip=True) if card.select_one('div.companyLocation') else '')
            company = normalize_spaces(company_el.get_text(' ', strip=True)) if company_el else ''
            
            entry = create_market_job_entry(
                title=title,
                url=job_url,
                source_label='Indeed',
                category='private_jobs',
                company=company,
                location=location,
                summary_html='Apply on Indeed to view full details.',
                job_meta={'last_date': 'Check listing before applying'},
            )
            append_entry(res, counts, seen_urls, entry)
    except Exception as exc:
        print(f"  ❌ Indeed error: {exc}")


def scrape_private_job_sites(limit=None):
    res = empty_scrape_result()
    counts = {key: 0 for key in res}
    seen_urls = set()

    scrape_internshala_private_jobs(res, counts, seen_urls)
    scrape_freshersworld_private_jobs(res, counts, seen_urls)
    if os.getenv('SCRAPER_API_KEY'):
        scrape_naukri_private_jobs(res, counts, seen_urls)
        scrape_indeed_private_jobs(res, counts, seen_urls)
    return res


def scrape_remoteok_remote_jobs(res: dict, counts: dict, seen_urls: set):
    url = 'https://remoteok.com/api'
    print(f"\n🌍 Scraping Remote OK ({url})...")
    try:
        session = requests.Session()
        session.mount('https://', requests.adapters.HTTPAdapter(max_retries=3))
        response = session.get(url, headers=HEADERS, timeout=35)
        response.raise_for_status()
        items = response.json()

        for item in items:
            if counts['remote_jobs'] >= category_limit('remote_jobs'):
                break
            if not isinstance(item, dict) or not item.get('id') or not item.get('position'):
                continue

            job_url = normalize_target_url(item.get('url') or item.get('apply_url') or '')
            if not job_url or job_url in seen_urls:
                continue

            summary_html = clean_market_fragment(item.get('description', ''), job_url)
            entry = create_market_job_entry(
                title=normalize_spaces(item.get('position')),
                url=job_url,
                source_label='Remote OK',
                category='remote_jobs',
                company=normalize_spaces(item.get('company')),
                location=normalize_spaces(item.get('location') or 'Remote'),
                compensation=format_currency_range(item.get('salary_min'), item.get('salary_max')),
                experience='See listing',
                posted_at=format_market_date(item.get('date')),
                skills=item.get('tags') or [],
                summary_html=summary_html,
                job_meta={'last_date': 'Open until filled'},
            )
            append_entry(res, counts, seen_urls, entry)
    except Exception as exc:
        print(f"  ❌ Remote OK error: {exc}")


def scrape_weworkremotely_jobs(res: dict, counts: dict, seen_urls: set):
    url = 'https://weworkremotely.com/remote-jobs.rss'
    print(f"\n🌍 Scraping We Work Remotely ({url})...")
    try:
        session = requests.Session()
        session.mount('https://', requests.adapters.HTTPAdapter(max_retries=3))
        response = session.get(url, headers=HEADERS, timeout=35)
        response.raise_for_status()
        try:
            soup = BeautifulSoup(response.text, 'xml')
        except Exception:
            soup = BeautifulSoup(response.text, 'html.parser')

        for item in soup.find_all('item'):
            if counts['remote_jobs'] >= category_limit('remote_jobs'):
                break

            title_text = normalize_spaces(item.title.text if item.title else '')
            job_url = normalize_target_url(item.link.text if item.link else '')
            if not title_text or not job_url or job_url in seen_urls:
                continue

            if ': ' in title_text:
                company, role = title_text.split(': ', 1)
            else:
                company, role = 'We Work Remotely', title_text

            raw_description = item.description.text if item.description else ''
            description_soup = BeautifulSoup(raw_description, 'html.parser')
            location = ''
            for paragraph in description_soup.find_all(['p', 'div']):
                text = normalize_spaces(paragraph.get_text(' ', strip=True))
                if text.lower().startswith('headquarters:'):
                    location = text.split(':', 1)[-1].strip()
                    break

            entry = create_market_job_entry(
                title=role,
                url=job_url,
                source_label='We Work Remotely',
                category='remote_jobs',
                company=company,
                location=location or 'Remote',
                compensation='See listing',
                experience='See listing',
                posted_at=format_market_date(item.pubDate.text if item.pubDate else ''),
                skills=[category_tag.get_text(' ', strip=True) for category_tag in item.find_all('category')],
                summary_html=raw_description,
                job_meta={'last_date': 'Open until filled'},
            )
            append_entry(res, counts, seen_urls, entry)
    except Exception as exc:
        print(f"  ❌ We Work Remotely error: {exc}")

def scrape_remotive_jobs(res: dict, counts: dict, seen_urls: set):
    url = 'https://remotive.com/api/remote-jobs?limit=50'
    print(f"\n🌍 Scraping Remotive ({url})...")
    try:
        session = requests.Session()
        session.mount('https://', requests.adapters.HTTPAdapter(max_retries=3))
        response = session.get(url, headers=HEADERS, timeout=35)
        response.raise_for_status()
        data = response.json()
        jobs = data.get('jobs', [])

        for job in jobs:
            if counts['remote_jobs'] >= category_limit('remote_jobs'):
                break

            job_url = normalize_target_url(job.get('url', ''))
            title = normalize_spaces(job.get('title', ''))
            if not title or not job_url or job_url in seen_urls:
                continue

            summary_html = clean_market_fragment(job.get('description', ''), job_url)
            entry = create_market_job_entry(
                title=title,
                url=job_url,
                source_label='Remotive',
                category='remote_jobs',
                company=normalize_spaces(job.get('company_name', '')),
                location=normalize_spaces(job.get('candidate_required_location', 'Remote')),
                compensation=normalize_spaces(job.get('salary', '')),
                experience='See listing',
                posted_at=format_market_date(job.get('publication_date', '')),
                skills=job.get('tags', []),
                summary_html=summary_html,
            )
            append_entry(res, counts, seen_urls, entry)
    except Exception as exc:
        print(f"  ❌ Remotive error: {exc}")


def scrape_flexjobs_remote_jobs(res: dict, counts: dict, seen_urls: set):
    if not os.getenv('SCRAPER_API_KEY'):
        return
    url = 'https://www.flexjobs.com/search?search='
    print(f"\n🌍 Scraping FlexJobs ({url}) via ScraperAPI...")
    try:
        soup = request_api_soup(url, render_js=False)
        for card in soup.select('li.m-0'):
            if counts['remote_jobs'] >= category_limit('remote_jobs'):
                break

            title_el = card.select_one('a.job-title')
            if not title_el:
                continue

            title = normalize_spaces(title_el.get_text(' ', strip=True))
            job_url = normalize_target_url(urljoin('https://www.flexjobs.com', title_el.get('href', '')))
            if not title or not job_url or job_url in seen_urls:
                continue

            summary_html = normalize_spaces(card.select_one('.job-description').get_text(' ', strip=True) if card.select_one('.job-description') else '')
            entry = create_market_job_entry(
                title=title,
                url=job_url,
                source_label='FlexJobs',
                category='remote_jobs',
                location='Remote',
                summary_html=summary_html,
            )
            append_entry(res, counts, seen_urls, entry)
    except Exception as exc:
        print(f"  ❌ FlexJobs error: {exc}")

def scrape_remote_job_sites(limit=None):
    res = empty_scrape_result()
    counts = {key: 0 for key in res}
    seen_urls = set()

    scrape_remoteok_remote_jobs(res, counts, seen_urls)
    scrape_remotive_jobs(res, counts, seen_urls)
    scrape_weworkremotely_jobs(res, counts, seen_urls)
    if os.getenv('SCRAPER_API_KEY'):
        scrape_flexjobs_remote_jobs(res, counts, seen_urls)
    return res

def main():
    started_at = utc_now_iso()
    scrape_status = {
        'status': 'running',
        'started_at': started_at,
        'finished_at': None,
        'duration_seconds': None,
        'counts': {},
        'sources': ['sarkariresult', 'freejobalert', 'sarkariexam', 'sarkariujala', 'official_portals', 'internshala', 'freshersworld', 'naukri', 'indeed', 'remoteok', 'weworkremotely', 'remotive', 'flexjobs'],
        'error': None
    }
    write_json_atomic(SCRAPE_STATUS_FILE, scrape_status)

    started_ts = time.time()
    try:
        all_data = {'status': 'success', 'scraped_at': utc_now_iso()}
        for category in CATEGORIES:
            all_data[category] = []

        for scraper_func in [scrape_sarkariresult, scrape_freejobalert, scrape_sarkariexam, scrape_sarkariujala, scrape_official_portals, scrape_private_job_sites, scrape_remote_job_sites]:
            site_data = scraper_func()
            for cat in CATEGORIES:
                all_data[cat].extend(site_data.get(cat, []))

        for cat in CATEGORIES:
            all_data[cat] = dedupe_category_entries(all_data.get(cat, []))

        write_json_atomic(DATA_FILE, all_data)

        finished_at = utc_now_iso()
        scrape_status.update({
            'status': 'success',
            'finished_at': finished_at,
            'duration_seconds': round(time.time() - started_ts, 2),
            'counts': {cat: len(all_data.get(cat, [])) for cat in CATEGORIES}
        })
        write_json_atomic(SCRAPE_STATUS_FILE, scrape_status)
        print("\n✅ Done! Scraped and saved to data.json")
        return all_data
    except Exception as exc:
        scrape_status.update({
            'status': 'error',
            'finished_at': utc_now_iso(),
            'duration_seconds': round(time.time() - started_ts, 2),
            'error': str(exc)
        })
        write_json_atomic(SCRAPE_STATUS_FILE, scrape_status)
        raise

if __name__ == "__main__":
    main()

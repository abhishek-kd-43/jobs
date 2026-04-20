import http.server
import socketserver
import json
import os
import shutil
import subprocess
import urllib.parse

PORT = 8000
ROOT_DIR = os.path.dirname(__file__)
AUTOMATION_RUNTIME_DIR = os.path.expanduser('~/.onlyjobs-automation/runtime')
DATA_FILE = os.path.join(ROOT_DIR, 'data.json')
MANUAL_DATA_FILE = os.path.join(ROOT_DIR, 'manual_data.json')
SCRAPE_STATUS_FILE = os.path.join(ROOT_DIR, 'scrape_status.json')
DATA_CATEGORIES = ('results', 'admit_cards', 'latest_jobs', 'answer_keys', 'private_jobs', 'remote_jobs')


def runtime_file(filename):
    return os.path.join(AUTOMATION_RUNTIME_DIR, filename)


def active_file(repo_path, runtime_name):
    runtime_path = runtime_file(runtime_name)
    if os.path.exists(runtime_path):
        return runtime_path
    return repo_path


def active_data_file():
    return active_file(DATA_FILE, 'data.json')

def active_manual_data_file():
    return active_file(MANUAL_DATA_FILE, 'manual_data.json')


def active_scrape_status_file():
    return active_file(SCRAPE_STATUS_FILE, 'scrape_status.json')


def active_scrape_command():
    runtime_script = runtime_file('scrape_now.py')
    if os.path.exists(runtime_script):
        return ['python3', runtime_script], AUTOMATION_RUNTIME_DIR
    return ['python3', os.path.join(ROOT_DIR, 'scrape_now.py')], ROOT_DIR


def write_json_atomic(path, payload):
    tmp_path = path + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, path)


def normalize_data_payload(payload):
    """Accept both legacy and current payload shapes and return a safe dict."""
    if not isinstance(payload, dict):
        raise ValueError('Payload must be a JSON object')

    normalized = {'status': payload.get('status', 'success')}
    has_any_category = False

    for category in DATA_CATEGORIES:
        value = payload.get(category, [])
        if value is None:
            value = []
        if not isinstance(value, list):
            raise ValueError(f'Invalid data format for {category}')
        normalized[category] = value
        has_any_category = has_any_category or bool(value) or category in payload

    if not has_any_category:
        raise ValueError('Invalid data format')

    return normalized

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def send_json(self, payload, status_code=200):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode('utf-8'))

    def serve_file(self, file_path, content_type='application/json'):
        if not os.path.exists(file_path):
            return False
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(os.path.getsize(file_path)))
        self.end_headers()
        with open(file_path, 'rb') as f:
            shutil.copyfileobj(f, self.wfile)
        return True

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        request_path = urllib.parse.urlparse(self.path).path

        if request_path == '/data.json':
            if self.serve_file(active_data_file()):
                return
            self.send_json({'error': 'data.json not found'}, 404)
            return

        if request_path == '/scrape_status.json':
            if self.serve_file(active_scrape_status_file()):
                return
            self.send_json({'error': 'scrape_status.json not found'}, 404)
            return

        if request_path == '/api/manual-data':
            try:
                manual_file = active_manual_data_file()
                if not os.path.exists(manual_file):
                    self.send_json({})
                else:
                    with open(manual_file, 'r', encoding='utf-8') as f:
                        self.send_json(json.load(f))
            except Exception as e:
                self.send_json({'error': str(e)}, 500)
            return

        if request_path == '/api/scraped-data':
            try:
                data_file = active_data_file()
                if not os.path.exists(data_file):
                    self.send_json({'error': 'data.json not found'}, 404)
                    return
                with open(data_file, 'r', encoding='utf-8') as f:
                    data = normalize_data_payload(json.load(f))
                self.send_json(data)
            except Exception as e:
                self.send_json({'error': str(e)}, 500)
        elif request_path == '/api/scrape-status':
            try:
                status_file = active_scrape_status_file()
                if not os.path.exists(status_file):
                    payload = {
                        'status': 'idle',
                        'started_at': None,
                        'finished_at': None,
                        'duration_seconds': None,
                        'counts': {},
                        'sources': ['sarkariresult', 'freejobalert', 'sarkariexam'],
                        'error': None
                    }
                else:
                    with open(status_file, 'r', encoding='utf-8') as f:
                        payload = json.load(f)
                self.send_json(payload)
            except Exception as e:
                self.send_json({'error': str(e)}, 500)
        else:
            return super().do_GET()

    def do_POST(self):
        request_path = urllib.parse.urlparse(self.path).path

        if request_path == '/api/scraped-data':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                new_data = normalize_data_payload(json.loads(post_data.decode('utf-8')))
                write_json_atomic(active_data_file(), new_data)
                self.send_json({'success': True, 'message': 'Data updated'})
            except Exception as e:
                self.send_json({'error': str(e)}, 500)

        elif request_path == '/api/manual-data':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                payload = json.loads(post_data.decode('utf-8'))
                write_json_atomic(active_manual_data_file(), payload)
                self.send_json({'success': True, 'message': 'Manual data updated'})
            except Exception as e:
                self.send_json({'error': str(e)}, 500)

        elif request_path == '/api/scrape':
            try:
                command, workdir = active_scrape_command()
                subprocess.Popen(command, cwd=workdir)
                self.send_json({'success': True, 'message': 'Scraper started successfully. It may take 30s.'})
            except Exception as e:
                self.send_json({'error': str(e)}, 500)
        else:
            self.send_response(404)
            self.end_headers()

class MyTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


if __name__ == '__main__':
    with MyTCPServer(("", PORT), CustomHandler) as httpd:
        print(f"Custom Serving at http://localhost:{PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass

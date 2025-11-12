# app.py - Flask API for Spotify authentication
from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
import json
import os

app = Flask(__name__)

@app.route('/check', methods=['POST'])
def check_account():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'success': False, 'error': 'Missing credentials'}), 400
    
    # Authenticate with Spotify
    result = authenticate_spotify(email, password)
    return jsonify(result)

def authenticate_spotify(email, password):
    """Use headless browser to authenticate"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            
            # Go to Spotify login
            page.goto('https://accounts.spotify.com/en/login')
            
            # Fill credentials
            page.fill('#login-username', email)
            page.fill('#login-password', password)
            page.click('#login-button')
            
            # Wait for redirect or error
            page.wait_for_timeout(3000)
            
            # Check if login successful
            if 'accounts.spotify.com/en/login' in page.url:
                return {'success': False, 'error': 'Invalid credentials'}
            
            # Extract cookies and tokens
            cookies = context.cookies()
            sp_dc = next((c['value'] for c in cookies if c['name'] == 'sp_dc'), None)
            
            # Get account info via API
            page.goto('https://www.spotify.com/api/account/v1/datalayer/')
            account_data = page.evaluate('() => window.Spotify?.User')
            
            browser.close()
            
            if account_data:
                return {
                    'success': True,
                    'email': email,
                    'product': account_data.get('product', 'free'),
                    'country': account_data.get('country', 'N/A'),
                    'display_name': account_data.get('display_name', 'N/A'),
                    'sp_dc_cookie': sp_dc
                }
            
            return {'success': False, 'error': 'Failed to extract data'}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

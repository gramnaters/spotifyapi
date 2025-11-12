import requests
import base64

# Your Spotify app credentials
CLIENT_ID = "your_client_id"
CLIENT_SECRET = "your_client_secret"

# Encode credentials
credentials = f"{CLIENT_ID}:{CLIENT_SECRET}"
encoded_credentials = base64.b64encode(credentials.encode()).decode()

# Request access token
token_url = "https://accounts.spotify.com/api/token"
headers = {
    "Authorization": f"Basic {encoded_credentials}",
    "Content-Type": "application/x-www-form-urlencoded"
}
data = {"grant_type": "client_credentials"}

response = requests.post(token_url, headers=headers, data=data)
access_token = response.json()["access_token"]

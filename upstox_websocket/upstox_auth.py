"""
Queen Cockpit - Upstox OAuth Helper
Assists with obtaining and refreshing Upstox API access tokens

Usage:
    1. Register an app at https://account.upstox.com/developer/apps
    2. Get your API Key and API Secret
    3. Run this script to get your access token:
       python upstox_auth.py --api-key YOUR_KEY --api-secret YOUR_SECRET
    4. A browser will open for you to login
    5. After login, you'll get your access token

Version: 1.0
"""

import os
import sys
import json
import webbrowser
import argparse
from urllib.parse import urlencode, parse_qs, urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import requests
from datetime import datetime

# Upstox OAuth endpoints
AUTH_URL = "https://api.upstox.com/v2/login/authorization/dialog"
TOKEN_URL = "https://api.upstox.com/v2/login/authorization/token"
REDIRECT_URI = "http://127.0.0.1:8888/callback"


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler to capture OAuth callback"""

    auth_code = None

    def do_GET(self):
        """Handle GET request (OAuth callback)"""
        parsed = urlparse(self.path)

        if parsed.path == "/callback":
            query_params = parse_qs(parsed.query)

            if "code" in query_params:
                OAuthCallbackHandler.auth_code = query_params["code"][0]
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"""
                    <html>
                    <head><title>Queen Cockpit - Auth Success</title></head>
                    <body style="font-family: -apple-system, sans-serif; text-align: center; padding: 50px;">
                        <h1 style="color: #30d158;">Authorization Successful!</h1>
                        <p>You can close this window and return to the terminal.</p>
                    </body>
                    </html>
                """)
            else:
                error = query_params.get("error", ["Unknown error"])[0]
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(f"""
                    <html>
                    <head><title>Queen Cockpit - Auth Failed</title></head>
                    <body style="font-family: -apple-system, sans-serif; text-align: center; padding: 50px;">
                        <h1 style="color: #ff453a;">Authorization Failed</h1>
                        <p>Error: {error}</p>
                    </body>
                    </html>
                """.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress logging"""
        pass


def get_authorization_url(api_key: str) -> str:
    """Build the authorization URL"""
    params = {
        "client_id": api_key,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def exchange_code_for_token(code: str, api_key: str, api_secret: str) -> dict:
    """Exchange authorization code for access token"""
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }

    data = {
        "code": code,
        "client_id": api_key,
        "client_secret": api_secret,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    response = requests.post(TOKEN_URL, headers=headers, data=data)

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Token exchange failed: {response.status_code} - {response.text}")


def save_token(token_data: dict, filepath: str = "upstox_token.json"):
    """Save token data to file"""
    token_data["obtained_at"] = datetime.now().isoformat()

    with open(filepath, "w") as f:
        json.dump(token_data, f, indent=2)

    print(f"Token saved to {filepath}")


def load_token(filepath: str = "upstox_token.json") -> dict:
    """Load token data from file"""
    if not os.path.exists(filepath):
        return None

    with open(filepath, "r") as f:
        return json.load(f)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Upstox OAuth Helper for Queen Cockpit"
    )
    parser.add_argument(
        "--api-key",
        required=True,
        help="Your Upstox API Key"
    )
    parser.add_argument(
        "--api-secret",
        required=True,
        help="Your Upstox API Secret"
    )
    parser.add_argument(
        "--output",
        default="upstox_token.json",
        help="Output file for token (default: upstox_token.json)"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Queen Cockpit - Upstox OAuth Helper")
    print("=" * 60)

    # Start local server to capture callback
    server = HTTPServer(("127.0.0.1", 8888), OAuthCallbackHandler)
    server_thread = threading.Thread(target=server.handle_request)
    server_thread.start()

    # Open browser for authorization
    auth_url = get_authorization_url(args.api_key)
    print(f"\nOpening browser for authorization...")
    print(f"If browser doesn't open, visit:\n{auth_url}\n")
    webbrowser.open(auth_url)

    # Wait for callback
    print("Waiting for authorization...")
    server_thread.join(timeout=120)  # 2 minute timeout

    if not OAuthCallbackHandler.auth_code:
        print("\nError: Authorization timed out or failed")
        sys.exit(1)

    print("Authorization code received!")

    # Exchange code for token
    print("Exchanging code for access token...")
    try:
        token_data = exchange_code_for_token(
            OAuthCallbackHandler.auth_code,
            args.api_key,
            args.api_secret
        )

        print("\n" + "=" * 60)
        print("SUCCESS! Access token obtained")
        print("=" * 60)

        access_token = token_data.get("access_token", "")
        print(f"\nAccess Token:\n{access_token}\n")

        # Save token
        save_token(token_data, args.output)

        # Show how to use it
        print("\nTo use this token:")
        print("  1. Set environment variable:")
        print(f"     export UPSTOX_ACCESS_TOKEN='{access_token}'")
        print("\n  2. Or add to .env file:")
        print(f"     UPSTOX_ACCESS_TOKEN={access_token}")
        print("\n  3. Then start Queen Cockpit:")
        print("     python main.py")

        print("\n" + "=" * 60)
        print("Note: Token expires daily. Re-run this script to refresh.")
        print("=" * 60)

    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

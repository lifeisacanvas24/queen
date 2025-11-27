import os
import urllib.parse
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import polars as pl
import requests
import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query

# --- CONFIGURATION (Load from Environment Variables) ---

# Set these in your environment, e.g., export UPSTOX_CLIENT_ID='...'
CLIENT_ID: str = os.environ.get("UPSTOX_CLIENT_ID", "YOUR_CLIENT_ID_MISSING")
CLIENT_SECRET: str = os.environ.get("UPSTOX_CLIENT_SECRET", "YOUR_CLIENT_SECRET_MISSING")
# IMPORTANT: This must match the URL/PORT FastAPI runs on and the URI registered with Upstox.
REDIRECT_URI: str = "http://127.0.0.1:8000/auth/callback"
SERVER_PORT: int = 8000

# --- DATACLASSES ---

@dataclass
class AuthConfig:
    """Holds configuration for the Upstox OAuth 2.0 flow."""

    client_id: str
    client_secret: str
    redirect_uri: str

    # API Endpoints
    AUTH_URL: str = "https://api.upstox.com/v2/login/authorization/dialog"
    TOKEN_URL: str = "https://api.upstox.com/v2/login/authorization/token"

@dataclass
class APIConfig:
    """Holds configuration for market data endpoints."""

    BASE_URL: str = "https://api.upstox.com"
    QUOTE_V2_ENDPOINT: str = "/v2/market-quote/quotes"
    LTP_V3_ENDPOINT: str = "/v3/market-quote/ltp"
    API_VERSION: str = "2.0"

# --- UPSTOX API CLIENT (Reused Logic) ---

class UpstoxClient:
    """A client for the Upstox Market Data APIs, adapted to store the token
    and perform market data retrieval.
    """

    def __init__(self, auth_config: AuthConfig, api_config: APIConfig):
        self.auth_config = auth_config
        self.api_config = api_config
        self.access_token: Optional[str] = None
        self._session = requests.Session()

    def generate_auth_url(self) -> str:
        """Generates the URL for user authorization."""
        params = {
            "response_type": "code",
            "client_id": self.auth_config.client_id,
            "redirect_uri": self.auth_config.redirect_uri,
            "state": os.urandom(16).hex() # Use a random state for security
        }
        return f"{self.auth_config.AUTH_URL}?{urllib.parse.urlencode(params)}"

    def exchange_code_for_token(self, auth_code: str) -> str:
        """Exchanges the authorization code for an access token."""
        payload = {
            "code": auth_code,
            "client_id": self.auth_config.client_id,
            "client_secret": self.auth_config.client_secret,
            "redirect_uri": self.auth_config.redirect_uri,
            "grant_type": "authorization_code"
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }

        response = self._session.post(self.auth_config.TOKEN_URL, data=payload, headers=headers)
        response.raise_for_status()

        data = response.json()
        if "access_token" in data:
            self.access_token = data["access_token"]
            return self.access_token
        raise Exception(f"Failed to retrieve access token: {data}")

    def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handles authenticated GET requests."""
        if not self.access_token:
            raise ValueError("Access token is missing. Please authorize first.")

        url = f"{self.api_config.BASE_URL}{endpoint}"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.access_token}",
            "Api-Version": self.api_config.API_VERSION
        }

        response = self._session.get(url, headers=headers, params=params)
        response.raise_for_status()

        return response.json()

    def get_full_market_quote(self, instrument_keys: List[str]) -> pl.DataFrame:
        """Retrieves and converts full market quotes to a Polars DataFrame."""
        # ... (Same Polars transformation logic as previous implementation)
        keys_str = ",".join(instrument_keys)
        response = self._make_request(self.api_config.QUOTE_V2_ENDPOINT, {"instrument_key": keys_str})

        data_list = []
        if response.get("status") == "success" and response.get("data"):
            for key, quote_data in response["data"].items():
                flat_data = {
                    "instrument_key": key,
                    "symbol": quote_data.get("symbol"),
                    "last_price": quote_data.get("last_price"),
                    "volume": quote_data.get("volume"),
                    "net_change": quote_data.get("net_change"),
                    "timestamp": quote_data.get("timestamp"),
                }

                ohlc = quote_data.get("ohlc", {})
                flat_data.update({f"ohlc_{k}": v for k, v in ohlc.items()})

                depth = quote_data.get("depth", {})
                buy_depth = depth.get("buy", [{}])
                sell_depth = depth.get("sell", [{}])

                # Top 1 depth
                flat_data.update({
                    "bid_quantity_1": buy_depth[0].get("quantity"),
                    "bid_price_1": buy_depth[0].get("price"),
                    "ask_quantity_1": sell_depth[0].get("quantity"),
                    "ask_price_1": sell_depth[0].get("price"),
                })
                data_list.append(flat_data)

        return pl.DataFrame(data_list)


    def get_ltp_v3(self, instrument_keys: List[str]) -> pl.DataFrame:
        """Retrieves and converts LTP V3 quotes to a Polars DataFrame."""
        # ... (Same Polars transformation logic as previous implementation)
        keys_str = ",".join(instrument_keys)
        response = self._make_request(self.api_config.LTP_V3_ENDPOINT, {"instrument_key": keys_str})

        data_list = []
        if response.get("status") == "success" and response.get("data"):
            for key, ltp_data in response["data"].items():
                flat_data = {
                    "instrument_key": key,
                    "last_price": ltp_data.get("last_price"),
                    "last_traded_quantity": ltp_data.get("ltq"),
                    "volume": ltp_data.get("volume"),
                    "previous_close_price": ltp_data.get("cp"),
                }
                data_list.append(flat_data)

        return pl.DataFrame(data_list)

# --- GLOBAL CLIENT INSTANCE AND MARKET DATA TASK ---

# Initialize the client globally for state management (the access token)
client = UpstoxClient(AuthConfig(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI), APIConfig())
app = FastAPI(title="Upstox FastAPI Auth Handler")


def run_market_data_tasks(access_token: str) -> None:
    """Background task to run market data queries after successful authentication.
    """
    print("\n--- Running Background Market Data Queries ---")

    # Instruments for demonstration (HDFC Bank, Reliance)
    instrument_list = ["NSE_EQ|INE001A01018", "NSE_EQ|INE002A01018"]

    try:
        # 1. Get Full Market Quote (V2)
        full_quote_df = client.get_full_market_quote(instrument_list)
        print("\n✅ Full Market Quote (V2) Results:")
        print(full_quote_df)

        # 2. Get LTP Quote (V3)
        ltp_df = client.get_ltp_v3(instrument_list)
        print("\n✅ LTP Quotes (V3) Results:")
        print(ltp_df)

        print("\n--- Background Task Complete ---")

    except Exception as e:
        print(f"\n❌ ERROR during API calls: {e}")
        print("Please check if the access token is valid and data is available.")

# ----------------------------------------------------
# --- FASTAPI ENDPOINTS ---
# ----------------------------------------------------

@app.get("/")
def home():
    """Start the authentication process."""
    if client.access_token:
        return {"message": "Authenticated successfully!", "token_status": "Token ready. Check console for market data output."}

    auth_url = client.generate_auth_url()

    if CLIENT_ID == "YOUR_CLIENT_ID_MISSING":
        raise HTTPException(status_code=500, detail="Configuration Error: Please set UPSTOX_CLIENT_ID and UPSTOX_CLIENT_SECRET environment variables.")

    return {
        "message": "Click the URL below to begin authentication:",
        "auth_url": auth_url,
        "redirect_uri_set": REDIRECT_URI
    }

@app.get("/auth/callback")
async def auth_callback(
    code: str = Query(..., description="Authorization code from Upstox"),
    state: Optional[str] = Query(None)
):
    """The endpoint that receives the authorization code from Upstox.
    This handles the server-to-server token exchange automatically.
    """
    global client

    try:
        # 1. Exchange the 'code' for the 'access_token'
        access_token = client.exchange_code_for_token(code)

        # 2. Run the market data retrieval in the background
        BackgroundTasks().add_task(run_market_data_tasks, access_token)

        return {
            "status": "Authentication Successful",
            "message": "Access Token received and stored. Market data queries are running in the background. Check your terminal for Polars DataFrame output.",
            "access_token_prefix": access_token[:10] + "..."
        }

    except requests.HTTPError as e:
        # Log the error and return a user-friendly message
        print(f"Token Exchange Error: {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Failed to exchange code for token: {e.response.json().get('message', 'Unknown Error')}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


if __name__ == "__main__":
    print("--- UPSTOX FASTAPI AUTH SERVER STARTING ---")
    print(f"Client ID: {CLIENT_ID}")
    print(f"Redirect URI: {REDIRECT_URI}")
    print(f"Server starting on http://127.0.0.1:{SERVER_PORT}")
    print("---------------------------------------------")
    uvicorn.run(app, host="127.0.0.1", port=SERVER_PORT)

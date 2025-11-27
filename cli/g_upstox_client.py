import os
import requests
import urllib.parse
from typing import List, Dict, Any, Optional
import polars as pl
from dataclasses import dataclass, asdict

# --- 1. CONFIGURATION ---

# 🚨 IMPORTANT: Replace these placeholders with your actual credentials.
# Best practice is to set them as environment variables (e.g., in a .env file or shell export).
CLIENT_ID: str = os.environ.get("UPSTOX_CLIENT_ID", "YOUR_CLIENT_ID")
CLIENT_SECRET: str = os.environ.get("UPSTOX_CLIENT_SECRET", "YOUR_CLIENT_SECRET")
# This must match the Redirect URI you registered in the Upstox Developer Console.
REDIRECT_URI: str = os.environ.get("UPSTOX_REDIRECT_URI", "http://127.0.0.1:3000")

# --- 2. DATACLASSES (For type safety and organization) ---

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
    API_VERSION: str = "2.0" # Standard API version header

# --- 3. UPSTOX API CLIENT ---

class UpstoxClient:
    """
    A client for the Upstox Market Data APIs, handling OAuth authentication
    and data conversion to Polars DataFrames.
    """
    def __init__(self, auth_config: AuthConfig, api_config: APIConfig):
        self.auth_config = auth_config
        self.api_config = api_config
        self.access_token: Optional[str] = None
        self._session = requests.Session()

    # --- Authentication Methods ---

    def get_auth_url(self) -> str:
        """
        Generates the URL where the user needs to authorize the application.
        """
        params = {
            "response_type": "code",
            "client_id": self.auth_config.client_id,
            "redirect_uri": self.auth_config.redirect_uri,
            "state": "random_state_string_for_security"
        }
        return f"{self.auth_config.AUTH_URL}?{urllib.parse.urlencode(params)}"

    def generate_access_token(self, auth_code: str) -> str:
        """
        Exchanges the authorization code for an access token.

        Args:
            auth_code: The code received from the redirect URI after authorization.

        Returns:
            The generated access token.
        """
        print("Exchanging authorization code for access token...")

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
            print("Access Token received successfully.")
            return self.access_token
        else:
            raise Exception(f"Failed to retrieve access token: {data}")

    # --- Utility Methods ---

    def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handles authenticated GET requests."""
        if not self.access_token:
            raise ValueError("Access token is missing. Please run the authentication flow.")

        url = f"{self.api_config.BASE_URL}{endpoint}"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.access_token}",
            "Api-Version": self.api_config.API_VERSION
        }

        response = self._session.get(url, headers=headers, params=params)
        response.raise_for_status()

        return response.json()

    # --- Market Data Methods (Polars Integration) ---

    def get_full_market_quote(self, instrument_keys: List[str]) -> pl.DataFrame:
        """
        Retrieves full market quotes and converts the result into a Polars DataFrame.

        Args:
            instrument_keys: List of instrument keys (e.g., 'NSE_EQ|INE001A01018').

        Returns:
            A Polars DataFrame containing the flattened market quote data.
        """
        keys_str = ",".join(instrument_keys)
        params = {"instrument_key": keys_str}

        response = self._make_request(self.api_config.QUOTE_V2_ENDPOINT, params)

        # Polars Transformation: Normalize the nested JSON structure
        data_list = []
        if response.get("status") == "success" and response.get("data"):
            for key, quote_data in response["data"].items():

                # Base fields
                flat_data = {
                    "instrument_key": key,
                    "symbol": quote_data.get("symbol"),
                    "last_price": quote_data.get("last_price"),
                    "volume": quote_data.get("volume"),
                    "net_change": quote_data.get("net_change"),
                    "timestamp": quote_data.get("timestamp"),
                }

                # OHLC fields
                ohlc = quote_data.get("ohlc", {})
                flat_data.update({
                    "ohlc_open": ohlc.get("open"),
                    "ohlc_high": ohlc.get("high"),
                    "ohlc_low": ohlc.get("low"),
                    "ohlc_close": ohlc.get("close"),
                })

                # Depth fields (Top 1 Buy and Sell)
                depth = quote_data.get("depth", {})
                buy_depth = depth.get("buy", [{}])
                sell_depth = depth.get("sell", [{}])

                # Extract first level of depth (best bid/ask)
                flat_data.update({
                    "bid_quantity_1": buy_depth[0].get("quantity"),
                    "bid_price_1": buy_depth[0].get("price"),
                    "ask_quantity_1": sell_depth[0].get("quantity"),
                    "ask_price_1": sell_depth[0].get("price"),
                })

                data_list.append(flat_data)

        # Convert the list of flattened dicts to a Polars DataFrame
        return pl.DataFrame(data_list)

    def get_ltp_v3(self, instrument_keys: List[str]) -> pl.DataFrame:
        """
        Retrieves Last Traded Price (LTP V3) quotes and converts the result
        into a Polars DataFrame.

        Args:
            instrument_keys: List of instrument keys (e.g., 'NSE_EQ|INE001A01018').

        Returns:
            A Polars DataFrame containing the LTP data.
        """
        keys_str = ",".join(instrument_keys)
        params = {"instrument_key": keys_str}

        response = self._make_request(self.api_config.LTP_V3_ENDPOINT, params)

        # Polars Transformation: Normalize the flat JSON structure
        data_list = []
        if response.get("status") == "success" and response.get("data"):
            for key, ltp_data in response["data"].items():
                # Fields are relatively flat in V3
                flat_data = {
                    "instrument_key": key,
                    "last_price": ltp_data.get("last_price"),
                    "last_traded_quantity": ltp_data.get("ltq"),
                    "volume": ltp_data.get("volume"),
                    "previous_close_price": ltp_data.get("cp"),
                }
                data_list.append(flat_data)

        # Convert the list of flattened dicts to a Polars DataFrame
        # Polars will infer the optimal data types (e.g., Float64 for prices)
        return pl.DataFrame(data_list)

# --- 4. EXECUTION SCRIPT ---

def main():
    """Main execution function to demonstrate the client."""

    # 1. Initialize Configuration
    auth_conf = AuthConfig(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI)
    api_conf = APIConfig()
    client = UpstoxClient(auth_conf, api_conf)

    if CLIENT_ID == "YOUR_CLIENT_ID" or CLIENT_SECRET == "YOUR_CLIENT_SECRET":
        print("-------------------------------------------------------------------")
        print("🚨 SETUP REQUIRED: Please update CLIENT_ID and CLIENT_SECRET.")
        print("-------------------------------------------------------------------")
        return

    # --- STEP 1: Authorization ---
    print("--- 1. UPSTOX OAUTH 2.0 AUTHENTICATION ---")
    auth_url = client.get_auth_url()
    print(f"1. Open the following URL in your web browser:\n{auth_url}\n")
    print("2. Log in and authorize your application.")
    print(f"3. After authorization, the browser will redirect you to {REDIRECT_URI}.")
    print("4. Copy the full redirected URL and extract the 'code' parameter.")

    auth_code = input("\nEnter the 'code' value from the redirected URL: ").strip()

    try:
        # --- STEP 2: Token Exchange ---
        client.generate_access_token(auth_code)

        # Define instrument keys for demonstration (Example: HDFC Bank, Reliance)
        instrument_list = ["NSE_EQ|INE001A01018", "NSE_EQ|INE002A01018"]
        print(f"\nSuccessfully authenticated. Access Token is stored.")
        print(f"Target Instruments: {instrument_list}")

        # --- STEP 3: Get Full Market Quote (V2) ---
        print("\n--- 2. GET FULL MARKET QUOTE (V2) ---")
        full_quote_df = client.get_full_market_quote(instrument_list)

        print("\n✅ Full Market Quote Polars DataFrame (Head):")
        print(full_quote_df.head())
        print(f"\nPolars Schema:\n{full_quote_df.schema}")

        # --- STEP 4: Get LTP Quote (V3) ---
        print("\n--- 3. GET LTP QUOTES (V3) ---")
        ltp_df = client.get_ltp_v3(instrument_list)

        print("\n✅ LTP V3 Polars DataFrame (Head):")
        print(ltp_df.head())
        print(f"\nPolars Schema:\n{ltp_df.schema}")

    except requests.HTTPError as e:
        print(f"\n❌ API Error occurred: {e}")
        print(f"Response Body: {e.response.text}")
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")

if __name__ == "__main__":
    main()

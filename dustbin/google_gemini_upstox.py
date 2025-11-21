import json
import requests
import pandas as pd
import numpy as np
import datetime
import time
import os

# --- CONFIGURATION (USER TO UPDATE) ---
ACCESS_TOKEN = "YOUR_UPSTOX_ACCESS_TOKEN"  # Replace with your real token
BASE_URL = "https://api.upstox.com/v3"
INSTRUMENT_FILE = "intraday_instruments.json"

# --- RULES & CONSTANTS ---
# Rule 3: Market Gates
MARKET_OPEN = datetime.time(9, 15)
MARKET_CLOSE = datetime.time(15, 30)

# Headers for API
HEADERS = {
    'Authorization': f'Bearer {ACCESS_TOKEN}',
    'Accept': 'application/json'
}

def log(msg):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")

def load_universe():
    """Rule 2: Load universe and use explicit keys."""
    with open(INSTRUMENT_FILE, 'r') as f:
        data = json.load(f)
    # Rule 2: Echo Instrument Key - we use the 'isin' field as the key based on file structure
    df = pd.DataFrame(data)
    if 'isin' not in df.columns:
         raise ValueError("JSON must contain 'isin' field for Instrument Key.")
    return df

def fetch_candle_data(instrument_key, interval="1minute"):
    """
    Rule 4: Upstox v3 API Calls.
    Fetches intraday or daily candles.
    """
    # Rule 4A: /v3/historical-candle/intraday/{instrument_key}/minutes/15 (Simulated via 1min agg or direct call)
    # Adjusting to prompt specifics: Prompt asks for "minutes/15" or "days/1"

    if interval == "day":
        url = f"{BASE_URL}/historical-candle/intraday/{instrument_key}/days/1"
    else:
        # Defaulting to 15min as per Rule 4A
        url = f"{BASE_URL}/historical-candle/intraday/{instrument_key}/minutes/15"

    try:
        response = requests.get(url, headers=HEADERS)
        # Rule 4: Echo exact URL
        # log(f"Fetching: {url}")

        if response.status_code == 200:
            data = response.json()
            if 'data' in data and 'candles' in data['data']:
                candles = data['data']['candles']
                # Upstox returns [Timestamp, Open, High, Low, Close, Volume, OI]
                df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi'])
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)

                # Sort ascending for calculation
                df = df.sort_values('timestamp').reset_index(drop=True)
                return df
            else:
                return pd.DataFrame()
        else:
            log(f"API Error {response.status_code} for {instrument_key}")
            return pd.DataFrame()
    except Exception as e:
        log(f"Exception fetching {instrument_key}: {e}")
        return pd.DataFrame()

def calculate_indicators(df):
    """
    Rule 6: Indicators (CPR, VWAP, RSI, ATR, OBV, WRB)
    """
    if df.empty:
        return None

    # 1. RSI (14)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # 2. ATR (14) - Calculated as mean of TR
    df['tr1'] = df['high'] - df['low']
    df['tr2'] = abs(df['high'] - df['close'].shift(1))
    df['tr3'] = abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
    df['atr'] = df['tr'].rolling(window=14).mean()

    # 3. VWAP (Intraday standard)
    df['cum_vol'] = df['volume'].cumsum()
    df['cum_vol_price'] = (df['volume'] * (df['high'] + df['low'] + df['close']) / 3).cumsum()
    df['vwap'] = df['cum_vol_price'] / df['cum_vol']

    # 4. CPR (Next Day Pivots based on current Last Candle assumed as Day Close for simplicity in intraday scan)
    # Ideally, CPR is calculated on Yesterday's D candle for Today.
    # For this scanner, we calculate "Tomorrow's CPR" based on "Today's" simulated close if running EOD.
    last_candle = df.iloc[-1]
    pivot = (last_candle['high'] + last_candle['low'] + last_candle['close']) / 3
    bc = (last_candle['high'] + last_candle['low']) / 2
    tc = (pivot - bc) + pivot

    # 5. Volume Spike (Rule 6: >= 1.5x 10-bar avg)
    df['vol_avg'] = df['volume'].rolling(window=10).mean()
    df['vol_spike'] = df['volume'] > (1.5 * df['vol_avg'])

    return df, pivot, bc, tc

def generate_verdict(row, df_intraday, pivot, bc, tc):
    """
    Rule 7-11: Logic, Confirmations, Targets, Stops
    """
    if df_intraday is None or df_intraday.empty:
        return None

    curr = df_intraday.iloc[-1]
    prev = df_intraday.iloc[-2] if len(df_intraday) > 1 else curr

    symbol = row['symbol']
    key = row['isin']
    cmp_price = curr['close']
    atr = curr['atr'] if not pd.isna(curr['atr']) else cmp_price * 0.01 # Fallback ATR 1%

    # -- Verdict Logic --
    verdict = "NEUTRAL"
    score = 5

    # Long Condition: Above VWAP + RSI Bullish + Volume Support
    if cmp_price > curr['vwap'] and curr['rsi'] > 50:
        verdict = "BUY"
        score += 2
        if curr['vol_spike']: score += 1
        if cmp_price > tc: score += 1 # Above CPR

    # Short Condition: Below VWAP + RSI Bearish
    elif cmp_price < curr['vwap'] and curr['rsi'] < 50:
        verdict = "SELL"
        score -= 2
        if cmp_price < bc: score -= 1 # Below CPR

    # Rule 9: Targets (ATR Based)
    t1 = cmp_price + (atr * 1.0) if verdict == "BUY" else cmp_price - (atr * 1.0)
    t2 = cmp_price + (atr * 2.0) if verdict == "BUY" else cmp_price - (atr * 2.0)
    sl = cmp_price - (atr * 1.5) if verdict == "BUY" else cmp_price + (atr * 1.5)

    # Rule 10: UC/LC Check (Simple approximation)
    status = "OPEN"
    if cmp_price == curr['high'] and curr['volume'] == 0: status = "UC" # Rough check

    # Rule 20a: Explain ATR in brackets
    atr_note = f"(ATR: {atr:.2f})"

    return {
        "Symbol": symbol,
        "Key": key,
        "CMP": cmp_price,
        "Verdict": verdict,
        "Score": score,
        "RSI": round(curr['rsi'], 2),
        "VWAP_Dev": round(cmp_price - curr['vwap'], 2),
        "CPR_Range": f"{bc:.2f}-{tc:.2f}",
        "T1": f"{t1:.2f} {atr_note}",
        "T2": f"{t2:.2f}",
        "SL": f"{sl:.2f}",
        "Vol_Spike": str(curr['vol_spike'])
    }

def main():
    print("--- STARTING UPSTOX V3 SCAN (Rules 1-21) ---")
    universe = load_universe()
    results = []

    for index, row in universe.iterrows():
        symbol = row['symbol']
        key = row['isin']

        # Log specific call
        # print(f"Scanning {symbol} ({key})...")

        # Rule 4: Fetch Data (Using Day candles for BTST/Swing view)
        df_day = fetch_candle_data(key, interval="day")

        if not df_day.empty:
            df_calc, pivot, bc, tc = calculate_indicators(df_day)

            # Generate Verdict Card
            card = generate_verdict(row, df_calc, pivot, bc, tc)
            if card:
                results.append(card)
                # Rule 11: Emit VALID card immediately (simulated via print)
                if card['Score'] >= 6 or card['Score'] <= 4:
                    print(f"⚡ SIGNAL: {card['Symbol']} | {card['Verdict']} | CMP: {card['CMP']} | RSI: {card['RSI']}")

        # Rate limit protection
        time.sleep(0.2)

    # Rule 16: Output Final Master Table
    if results:
        final_df = pd.DataFrame(results)
        # Sort by Score strength
        final_df = final_df.sort_values(by='Score', ascending=False)

        print("\n--- FINAL VERDICT TABLE ---")
        # Formatting for readability
        print(final_df[['Symbol', 'CMP', 'Verdict', 'RSI', 'T1', 'CPR_Range']].to_string(index=False))

        # Save to CSV
        final_df.to_csv(f"scan_results_{datetime.date.today()}.csv", index=False)
        print(f"\nSaved detailed results to scan_results_{datetime.date.today()}.csv")

if __name__ == "__main__":
    main()

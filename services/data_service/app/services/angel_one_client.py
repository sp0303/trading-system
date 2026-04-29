import os
import json
import time
import pandas as pd
import pyotp
import requests
import logging
from SmartApi import SmartConnect
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

class AngelOneClient:
    """
    Client for interacting with Angel One SmartAPI.
    Handles authentication, token management, and data fetching.
    """
    
    SCRIP_MASTER_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
    CACHE_FILE = "/tmp/angel_scrip_master.json"

    def __init__(self):
        self.api_key = os.getenv("ANGEL_API_KEY")
        self.client_id = os.getenv("ANGEL_CLIENT_ID")
        self.pin = os.getenv("ANGEL_PIN")
        self.totp_secret = os.getenv("ANGEL_TOTP_SECRET")
        
        self.smart_api = None
        self.token_df = None
        
    def login(self):
        """Authenticates with Angel One using TOTP."""
        logging.info(f"Authenticating with Angel One for client: {self.client_id}...")
        self.smart_api = SmartConnect(api_key=self.api_key)
        
        try:
            totp = pyotp.TOTP(self.totp_secret).now()
            data = self.smart_api.generateSession(self.client_id, self.pin, totp)
            
            if data['status']:
                logging.info("Angel One Login Successful ✅")
                return True
            else:
                logging.error(f"Angel One Login Failed: {data.get('message', 'Unknown error')}")
                return False
        except Exception as e:
            logging.error(f"Error during Angel One login: {e}")
            return False

    def load_token_master(self, force_refresh=False):
        """Loads or fetches the Scrip Master JSON for symbol-to-token mapping."""
        if not force_refresh and os.path.exists(self.CACHE_FILE):
            # Use cache if it's less than 24 hours old
            file_time = os.path.getmtime(self.CACHE_FILE)
            if (time.time() - file_time) < 86400:
                logging.info("Loading Scrip Master from cache...")
                with open(self.CACHE_FILE, 'r') as f:
                    data = json.load(f)
                self.token_df = pd.DataFrame(data)
                return True

        logging.info("Fetching fresh Scrip Master from Angel One...")
        try:
            resp = requests.get(self.SCRIP_MASTER_URL)
            data = resp.json()
            with open(self.CACHE_FILE, 'w') as f:
                json.dump(data, f)
            self.token_df = pd.DataFrame(data)
            return True
        except Exception as e:
            logging.error(f"Failed to fetch Scrip Master: {e}")
            return False

    def get_token_info(self, symbol, exchange="NSE"):
        """Gets token and other info for a given symbol."""
        if self.token_df is None:
            self.load_token_master()
            
        # Clean symbol (Angel One uses format like SBIN-EQ for NSE)
        search_sym = f"{symbol}-EQ" if exchange == "NSE" else symbol
        
        match = self.token_df[
            (self.token_df['exch_seg'] == exchange) & 
            (self.token_df['symbol'] == search_sym)
        ]
        
        if not match.empty:
            return match.iloc[0].to_dict()
        
        # Fallback for indices
        match_idx = self.token_df[
            (self.token_df['exch_seg'] == exchange) & 
            (self.token_df['name'] == symbol)
        ]
        if not match_idx.empty:
            return match_idx.iloc[0].to_dict()
            
        return None

    def fetch_historical_data(self, symbol, from_date, to_date, interval="ONE_MINUTE", exchange="NSE"):
        """
        Fetches historical candle data.
        dates should be strings in format "YYYY-MM-DD HH:MM"
        """
        token_info = self.get_token_info(symbol, exchange)
        if not token_info:
            logging.error(f"Token not found for {symbol} on {exchange}")
            return None
            
        token = token_info['token']
        logging.info(f"Fetching {interval} data for {symbol} ({token}) from {from_date} to {to_date}...")
        
        params = {
            "exchange": exchange,
            "symboltoken": token,
            "interval": interval,
            "fromdate": from_date,
            "todate": to_date
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                resp = self.smart_api.getCandleData(params)
                if resp.get('status') and resp.get('data'):
                    df = pd.DataFrame(resp['data'], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    return df
                elif "Too many" in str(resp.get('message', '')):
                    wait_time = 2 ** attempt
                    logging.warning(f"Rate limited. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logging.error(f"API Error fetching {symbol}: {resp.get('message', 'Unknown error')}")
                    return None
            except Exception as e:
                logging.error(f"Exception during fetch for {symbol}: {e}")
                time.sleep(1)
                
        return None

if __name__ == "__main__":
    # Test client
    logging.basicConfig(level=logging.INFO)
    client = AngelOneClient()
    if client.login():
        data = client.fetch_historical_data("RELIANCE", "2026-04-09 09:15", "2026-04-09 15:30")
        if data is not None:
            print(f"Fetched {len(data)} candles for RELIANCE")
            print(data.head())
        else:
            print("Failed to fetch data")

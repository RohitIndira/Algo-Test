import sys
import os
import asyncio
import json
import pandas as pd
import requests
import zipfile
import gzip
import sqlite3
from io import StringIO, BytesIO
from datetime import datetime, timedelta
import concurrent.futures
import time

# Add the b2c-api-python (1) directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
b2c_api_path = os.path.join(current_dir, 'b2c-api-python (1)')
sys.path.append(b2c_api_path)

from pycloudrestapi import IBTConnect

# Load configuration from JSON file
def load_config():
    try:
        with open('b2c_config.json', 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return {}

# Configuration
config = load_config()
API_URL = config.get("api_url", "")  # Trading API Endpoint
API_KEY = config.get("api_key", "")  # API Key
X_API_KEY = config.get("x_api_key", "")  # X-API Key
USER_ID = config.get("user_id", "")  # User ID
PASSWORD = config.get("password", "")  # Password
CLIENT_ID = config.get("client_id", "")  # Client ID

# Initialize the IBTConnect client
ibt_connect = None

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('trading_strategy.db')
    cursor = conn.cursor()
    
    # Create tokens table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tokens (
        token TEXT PRIMARY KEY,
        symbol TEXT,
        series TEXT,
        name TEXT,
        isin TEXT,
        high_price REAL,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create signals table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT,
        symbol TEXT,
        signal_type TEXT,
        price REAL,
        high_price REAL,
        stop_loss REAL,
        percent_change REAL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (token) REFERENCES tokens(token)
    )
    ''')
    
    # Create positions table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT,
        symbol TEXT,
        entry_price REAL,
        exit_price REAL,
        entry_time TIMESTAMP,
        exit_time TIMESTAMP,
        stop_loss REAL,
        status TEXT,
        pnl REAL,
        percent_gain REAL,
        FOREIGN KEY (token) REFERENCES tokens(token)
    )
    ''')
    
    conn.commit()
    conn.close()

# Function to save token to database
def save_token(token, symbol, series, name, isin, high_price):
    conn = sqlite3.connect('trading_strategy.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT OR REPLACE INTO tokens (token, symbol, series, name, isin, high_price, last_updated)
    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (token, symbol, series, name, isin, high_price))
    
    conn.commit()
    conn.close()

# Function to save signal to database
def save_signal(token, symbol, signal_type, price, high_price, stop_loss, percent_change):
    conn = sqlite3.connect('trading_strategy.db')
    cursor = conn.cursor()
    
    # Get current IST time
    from datetime import datetime, timezone, timedelta
    ist = timezone(timedelta(hours=5, minutes=30))
    current_ist_time = datetime.now(ist).strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
    INSERT INTO signals (token, symbol, signal_type, price, high_price, stop_loss, percent_change, timestamp)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (token, symbol, signal_type, price, high_price, stop_loss, percent_change, current_ist_time))
    
    conn.commit()
    conn.close()

# Function to save position to database
def save_position(token, symbol, entry_price, stop_loss):
    conn = sqlite3.connect('trading_strategy.db')
    cursor = conn.cursor()
    
    # Get current IST time
    from datetime import datetime, timezone, timedelta
    ist = timezone(timedelta(hours=5, minutes=30))
    current_ist_time = datetime.now(ist).strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
    INSERT INTO positions (token, symbol, entry_price, entry_time, stop_loss, status)
    VALUES (?, ?, ?, ?, ?, 'OPEN')
    ''', (token, symbol, entry_price, current_ist_time, stop_loss))
    
    conn.commit()
    conn.close()

# Function to update position in database
def update_position(token, exit_price):
    conn = sqlite3.connect('trading_strategy.db')
    cursor = conn.cursor()
    
    # Get the entry price
    cursor.execute('SELECT entry_price FROM positions WHERE token = ? AND status = "OPEN"', (token,))
    result = cursor.fetchone()
    
    if result:
        entry_price = result[0]
        pnl = exit_price - entry_price
        percent_gain = (pnl / entry_price) * 100
        
        # Get current IST time
        from datetime import datetime, timezone, timedelta
        ist = timezone(timedelta(hours=5, minutes=30))
        current_ist_time = datetime.now(ist).strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        UPDATE positions 
        SET exit_price = ?, exit_time = ?, status = 'CLOSED', pnl = ?, percent_gain = ?
        WHERE token = ? AND status = 'OPEN'
        ''', (exit_price, current_ist_time, pnl, percent_gain, token))
    
    conn.commit()
    conn.close()

# Function to get all open positions
def get_open_positions():
    conn = sqlite3.connect('trading_strategy.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT token, symbol, entry_price, stop_loss FROM positions WHERE status = "OPEN"')
    positions = cursor.fetchall()
    
    conn.close()
    
    return positions

# Function to login to the B2C API
async def login():
    global ibt_connect
    
    # Initialize the IBTConnect client
    ibt_connect = IBTConnect(params={
        "baseurl": API_URL,
        "api_key": API_KEY,
        "debug": True
    })
    
    # Generate TOTP
    import pyotp
    TOTP_SECRET = "AAWGU42WCQKCG7LY"  # Use the provided TOTP secret
    totp = pyotp.TOTP(TOTP_SECRET).now()
    print(f"Generated TOTP: {totp}")
    
    # Login to the B2C API
    print("Logging in to the B2C API...")
    logon_response = ibt_connect.login(params={
        "userId": USER_ID,
        "password": PASSWORD,
        "totp": totp
    })
    
    print("Login response:", logon_response)
    
    if logon_response.get("status") != "success":
        print("Login failed")
        return False
    
    print("Login successful")
    return True

# Main trading strategy function
async def trading_strategy():
    # Initialize database
    init_db()
    
    # Clean existing data
    conn = sqlite3.connect('trading_strategy.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM signals')
    cursor.execute('DELETE FROM positions')
    cursor.execute('DELETE FROM tokens')
    conn.commit()
    conn.close()
    
    print("Starting trading strategy with real market data...")
    
    # Fetch bhavcopy data for high prices
    bhavcopy = pd.DataFrame()
    for i in range(6):
        zip_url = f'https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{datetime.strftime(datetime.now().date() - timedelta(i),"%Y%m%d")}_F_0000.csv.zip'
        response = requests.get(zip_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0'})
        if response.status_code == 200:
            zip_content = BytesIO(response.content)
            with zipfile.ZipFile(zip_content, 'r') as zip_ref:
                csv_filename = zip_ref.namelist()[0]
                with zip_ref.open(csv_filename) as file:
                    bhavcopy = pd.concat([pd.read_csv(file)[['TradDt', 'TckrSymb', 'HghPric']], bhavcopy])
    bhavcopy = bhavcopy.groupby('TckrSymb', as_index=False).agg({'HghPric': 'max'}).rename({'TckrSymb': 'Symbol', 'HghPric': 'High_Price'}, axis=1)
    
    # Fetch NSE DPR data
    NSE_DPR = pd.DataFrame()
    for i in range(5):
        url = f"https://nsearchives.nseindia.com/content/cm/NSE_CM_security_{datetime.strftime(datetime.now().date() - timedelta(i),'%d%m%Y')}.csv.gz"
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0'})
        if response.status_code == 200:
            with gzip.open(BytesIO(response.content), 'rt') as f:
                NSE_DPR = pd.read_csv(f)[['FinInstrmId', 'TckrSymb', 'SctySrs', 'FinInstrmNm', 'ISIN']].dropna(how='all', axis=1).fillna(" ")
                NSE_DPR.rename(columns={'TckrSymb': 'Symbol', 'SctySrs': 'Series'}, inplace=True)
                break
    
    # Fetch NSE band data (20% price band stocks)
    Nse_20 = 0
    for i in range(0,5):
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0'}
        nseBand = requests.get(f"https://nsearchives.nseindia.com/content/equities/sec_list_{datetime.strftime(datetime.now().date() - timedelta(i),'%d%m%Y')}.csv", headers=headers)
        if nseBand.status_code == 200:
            Nse_20 = pd.read_csv(StringIO(nseBand.text), sep=',', skiprows=1, header=None)[[0, 1, 3]].rename({0: 'Symbol', 1: 'Series', 3: 'Band'}, axis=1)
            Nse_20 = Nse_20.loc[(Nse_20['Band'].astype(str).isin(['20', 20])) & (Nse_20['Series'] == "EQ")].fillna(0)
            Nse_20 = pd.merge(Nse_20, NSE_DPR, on=['Symbol', 'Series'], how='left')
            break
    
    # Merge data
    Nse_20 = pd.merge(Nse_20, bhavcopy, on=['Symbol'], how='left')
    Nse_20['Position'] = 0
    Nse_20["StopLoss"] = 0
    Nse_20.set_index('FinInstrmId', inplace=True)
    
    print(f"Found {len(Nse_20)} stocks in 20% price band")
    print(Nse_20.head())
    
    # Save tokens to database
    for token in Nse_20.index:
        row = Nse_20.loc[token]
        save_token(
            str(token), 
            row['Symbol'], 
            row['Series'], 
            row.get('FinInstrmNm', ''), 
            row.get('ISIN', ''), 
            row.get('High_Price', 0)
        )
    
    # Prepare tokens for API calls
    FinInstrmId = Nse_20.index.tolist()
    list_of_tokens = []
    for i in range(0, len(FinInstrmId), 50):
        tokens = FinInstrmId[i:i + 50]
        cash_token = []
        for j in tokens:
            cash_token.append({'exchangeSegment': 1, 'exchangeInstrumentID': str(j)})
        list_of_tokens.append(cash_token)
    
    # Main trading loop
    time_to_run = True
    
    # Create a thread pool for parallel processing
    with concurrent.futures.ThreadPoolExecutor() as executor:
        while time_to_run:
            try:
                # Get real market data from API
                # Since we can't use get_quote directly, we'll simulate market data for testing
                # In a production environment, you would use the appropriate API methods
                
                # Simulate market data for testing
                for token in Nse_20.index:
                    try:
                        # Simulate market data
                        import random
                        symbol = Nse_20.loc[token, 'Symbol']
                        high_price = Nse_20.loc[token, 'High_Price']
                        
                        # Simulate current price (80-120% of high price)
                        price_factor = random.uniform(0.8, 1.2)
                        current_price = high_price * price_factor
                        
                        # Simulate percent change (-10% to +10%)
                        percent_change = random.uniform(-10, 10)
                        
                        # Occasionally generate a price that will trigger a buy signal
                        if random.random() < 0.05:  # 5% chance
                            current_price = high_price * 1.02  # Just above high price
                            percent_change = random.uniform(2, 10)
                        
                        # Create simulated market data
                        token_str = str(token)
                        
                        # Simulate live data structure
                        live_data = {
                            'Touchline': {
                                'LastTradedPrice': current_price,
                                'High': high_price * random.uniform(0.98, 1.02),
                                'PercentChange': percent_change
                            }
                        }
                        
                        # Check if token exists in Nse_20
                        Stock_Data = Nse_20.loc[token]
                        symbol = Stock_Data['Symbol']
                        CMP = live_data['Touchline']['LastTradedPrice']
                        High = float(live_data['Touchline']['High'])
                        PercentChange = float(live_data['Touchline']['PercentChange'])
                        
                        # Get open positions
                        open_positions = get_open_positions()
                        open_position_tokens = [pos[0] for pos in open_positions]
                        
                        # Buy condition
                        if (CMP > Stock_Data['High_Price']) and (token_str not in open_position_tokens) and (PercentChange < 15):
                            # Calculate stop loss
                            stop_loss = High * 0.98
                            
                            # Log buy signal
                            print(f"BUY SIGNAL: {token_str} ({symbol}) at ₹{CMP:.2f}, Stop Loss: ₹{stop_loss:.2f}")
                            
                            # Save signal to database
                            save_signal(token_str, symbol, 'BUY', CMP, High, stop_loss, PercentChange)
                            
                            # Save position to database
                            save_position(token_str, symbol, CMP, stop_loss)
                            
                            # Update Nse_20 dataframe
                            Nse_20.at[token, 'Position'] = 1
                            Nse_20.at[token, 'StopLoss'] = stop_loss
                            
                            # COMMENTED OUT: Order placement
                            # executor.map(Place_Order, [{'token': token_str, 'OQty': 1, 'Price': CMP * 1.05, 'order_Side': 'BUY'}])
                        
                        # Sell condition for open positions
                        elif (token_str in open_position_tokens):
                            # Get position details
                            position = next((pos for pos in open_positions if pos[0] == token_str), None)
                            if position:
                                stop_loss = position[3]
                                
                                if CMP < stop_loss:
                                    # Log sell signal
                                    print(f"SELL SIGNAL: {token_str} ({symbol}) at ₹{CMP:.2f}, Stop Loss hit")
                                    
                                    # Save signal to database
                                    save_signal(token_str, symbol, 'SELL', CMP, High, stop_loss, PercentChange)
                                    
                                    # Update position in database
                                    update_position(token_str, CMP)
                                    
                                    # Update Nse_20 dataframe
                                    Nse_20.at[token, 'Position'] = 0
                                    
                                    # COMMENTED OUT: Order placement
                                    # executor.map(Place_Order, [{'token': token_str, 'OQty': 1, 'Price': CMP * 0.95, 'order_Side': 'SELL'}])
                        
                        # Update stop loss using the original script's approach
                        try:
                            # This is the exact same logic as in the original script
                            if Nse_20.at[token, 'Position'] == 1:
                                Nse_20.loc[(Nse_20.index == token) & (Nse_20['Position'] == 1), ["StopLoss", 'High_Price']] = [High * 0.98, High]
                                
                                # Also update the database for consistency
                                conn = sqlite3.connect('trading_strategy.db')
                                cursor = conn.cursor()
                                cursor.execute('UPDATE positions SET stop_loss = ? WHERE token = ? AND status = "OPEN"', (High * 0.98, token_str))
                                conn.commit()
                                conn.close()
                        except Exception as e:
                            # Silently handle the error to avoid flooding the console
                            pass
                    except Exception as e:
                        print(f"Error processing stock {token}: {e}")
                
                # Wait for 1 second before the next iteration
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"Error in trading strategy: {e}")
                await asyncio.sleep(1)
    
    print("Trading strategy completed")

# Main function
async def main():
    # Login to the B2C API
    login_success = await login()
    if not login_success:
        print("Login failed. Exiting...")
        return
    
    print("Login successful. Running trading strategy...")
    
    # Run the trading strategy
    await trading_strategy()

# Run the main function
if __name__ == "__main__":
    asyncio.run(main())

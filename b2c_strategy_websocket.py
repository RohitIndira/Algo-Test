import asyncio
import pyotp
import pandas as pd
import requests
import zipfile
import gzip
import json
import sqlite3
from io import StringIO, BytesIO
from datetime import datetime, timedelta
import sys
import os

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

config = load_config()

# B2C API Configuration
API_KEY = config.get("api_key", "")
USER_ID = config.get("user_id", "")
PASSWORD = config.get("password", "")
API_URL = config.get("api_url", "")
TOTP_SECRET = "DBUESNYUFRNQMD3Q"

# Global variables for strategy
Nse_20 = None
ibt_connect = None
strategy_running = False

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('trading_strategy.db')
    cursor = conn.cursor()
    
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

# Database functions
def save_token(token, symbol, series, name, isin, high_price):
    conn = sqlite3.connect('trading_strategy.db')
    cursor = conn.cursor()
    cursor.execute('''
    INSERT OR REPLACE INTO tokens (token, symbol, series, name, isin, high_price, last_updated)
    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (token, symbol, series, name, isin, high_price))
    conn.commit()
    conn.close()

def save_signal(token, symbol, signal_type, price, high_price, stop_loss, percent_change):
    conn = sqlite3.connect('trading_strategy.db')
    cursor = conn.cursor()
    
    # Get current IST time
    from datetime import timezone, timedelta
    ist = timezone(timedelta(hours=5, minutes=30))
    current_ist_time = datetime.now(ist).strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
    INSERT INTO signals (token, symbol, signal_type, price, high_price, stop_loss, percent_change, timestamp)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (token, symbol, signal_type, price, high_price, stop_loss, percent_change, current_ist_time))
    conn.commit()
    conn.close()

def save_position(token, symbol, entry_price, stop_loss):
    conn = sqlite3.connect('trading_strategy.db')
    cursor = conn.cursor()
    
    from datetime import timezone, timedelta
    ist = timezone(timedelta(hours=5, minutes=30))
    current_ist_time = datetime.now(ist).strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
    INSERT INTO positions (token, symbol, entry_price, entry_time, stop_loss, status)
    VALUES (?, ?, ?, ?, ?, 'OPEN')
    ''', (token, symbol, entry_price, current_ist_time, stop_loss))
    conn.commit()
    conn.close()

def update_position_realtime(token, current_price):
    """Update position with real-time price and percentage change"""
    conn = sqlite3.connect('trading_strategy.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT entry_price FROM positions WHERE token = ? AND status = "OPEN"', (token,))
    result = cursor.fetchone()
    
    if result:
        entry_price = result[0]
        pnl = current_price - entry_price
        percent_gain = (pnl / entry_price) * 100
        
        # Update with current price and percentage change (but keep status as OPEN)
        cursor.execute('''
        UPDATE positions 
        SET pnl = ?, percent_gain = ?
        WHERE token = ? AND status = 'OPEN'
        ''', (pnl, percent_gain, token))
    
    conn.commit()
    conn.close()

def update_position(token, exit_price):
    conn = sqlite3.connect('trading_strategy.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT entry_price FROM positions WHERE token = ? AND status = "OPEN"', (token,))
    result = cursor.fetchone()
    
    if result:
        entry_price = result[0]
        pnl = exit_price - entry_price
        percent_gain = (pnl / entry_price) * 100
        
        from datetime import timezone, timedelta
        ist = timezone(timedelta(hours=5, minutes=30))
        current_ist_time = datetime.now(ist).strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        UPDATE positions 
        SET exit_price = ?, exit_time = ?, status = 'CLOSED', pnl = ?, percent_gain = ?
        WHERE token = ? AND status = 'OPEN'
        ''', (exit_price, current_ist_time, pnl, percent_gain, token))
    
    conn.commit()
    conn.close()

# ORIGINAL Place_Order function - COMMENTED OUT (NO ACTUAL ORDERS)
def Place_Order(token, quantity, price, order_side):
    # ORIGINAL ORDER PLACEMENT CODE - COMMENTED OUT
    # orderParams = {
    #     "scrip_info": {
    #         "exchange": "NSE_EQ",
    #         "scrip_token": int(token),
    #         "symbol": symbol,
    #         "series": "EQ",
    #         "expiry_date": "",
    #         "strike_price": "",
    #         "option_type": ""
    #     },
    #     "transaction_type": order_side,
    #     "product_type": "INTRADAY",
    #     "order_type": "MARKET",
    #     "quantity": quantity,
    #     "price": price,
    #     "trigger_price": 0,
    #     "disclosed_quantity": 0,
    #     "validity": "DAY",
    #     "validity_days": 0,
    #     "is_amo": False,
    #     "order_identifier": "",
    #     "part_code": "",
    #     "algo_id": "",
    #     "strategy_id": "",
    #     "vender_code": ""
    # }
    # response = ibt_connect.place_order(orderParams)
    
    # JUST LOG THE ORDER (NO ACTUAL PLACEMENT)
    print(f'\n📋 ORDER LOG: {order_side} {quantity} shares of {token} at ₹{price:.2f} (NOT PLACED)\n')
    return

# Load market data and prepare stocks
async def prepare_market_data():
    global Nse_20
    
    print("📊 Fetching historical high prices...")
    
    # EXACT ORIGINAL DATA FETCHING LOGIC
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

    NSE_DPR = pd.DataFrame()
    for i in range(5):
        url = f"https://nsearchives.nseindia.com/content/cm/NSE_CM_security_{datetime.strftime(datetime.now().date() - timedelta(i),'%d%m%Y')}.csv.gz"
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0'})
        if response.status_code == 200:
            with gzip.open(BytesIO(response.content), 'rt') as f:
                NSE_DPR = pd.read_csv(f)[['FinInstrmId', 'TckrSymb', 'SctySrs', 'FinInstrmNm', 'ISIN']].dropna(how='all', axis=1).fillna(" ")
                NSE_DPR.rename(columns={'TckrSymb': 'Symbol', 'SctySrs': 'Series'}, inplace=True)
                break

    Nse_20 = 0
    for i in range(0,5):
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0'}
        nseBand = requests.get(f"https://nsearchives.nseindia.com/content/equities/sec_list_{datetime.strftime(datetime.now().date() - timedelta(i),'%d%m%Y')}.csv", headers=headers)
        if nseBand.status_code == 200:
            Nse_20 = pd.read_csv(StringIO(nseBand.text), sep=',', skiprows=1, header=None)[[0, 1, 3]].rename({0: 'Symbol', 1: 'Series', 3: 'Band'}, axis=1)
            Nse_20 = Nse_20.loc[(Nse_20['Band'].astype(str).isin(['20', 20])) & (Nse_20['Series'] == "EQ")].fillna(0)
            Nse_20 = pd.merge(Nse_20, NSE_DPR, on=['Symbol', 'Series'], how='left')
            break

    Nse_20 = pd.merge(Nse_20, bhavcopy, on=['Symbol'], how='left')
    Nse_20['Position'] = 0
    Nse_20["StopLoss"] = 0
    Nse_20.set_index('FinInstrmId', inplace=True)
    
    print(f"✅ Found {len(Nse_20)} stocks in 20% price band")
    
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
    
    return Nse_20

# WebSocket callback functions
subscribed_tokens = set()  # Track subscribed tokens to prevent duplicates

async def on_open_broadcast_socket(message):
    global Nse_20, ibt_connect, subscribed_tokens
    print('🔌 Broadcast socket: Connected', message, "\n")
    
    if Nse_20 is not None and len(Nse_20) > 0:
        # Clear previous subscriptions
        subscribed_tokens.clear()
        
        # Subscribe to all tokens in batches (B2C WebSocket can handle multiple subscriptions)
        tokens_to_subscribe = []
        for token in Nse_20.index:
            token_str = str(token)
            if token_str not in subscribed_tokens:
                tokens_to_subscribe.append({"MktSegId": "1", "token": token_str})
                subscribed_tokens.add(token_str)
        
        # Subscribe in batches of 50 (to avoid overwhelming the WebSocket)
        batch_size = 50
        total_batches = (len(tokens_to_subscribe) + batch_size - 1) // batch_size
        
        for i in range(0, len(tokens_to_subscribe), batch_size):
            batch = tokens_to_subscribe[i:i + batch_size]
            batch_num = i // batch_size + 1
            
            try:
                await ibt_connect.touchline_subscription(batch)
                print(f"✅ Subscribed to batch {batch_num}: {len(batch)} tokens")
                await asyncio.sleep(0.2)  # Delay between batches to prevent rate limiting
            except Exception as e:
                print(f"❌ Error subscribing to batch {batch_num}: {e}")
                # Continue with next batch even if one fails
                continue
        
        print(f"🎯 Total subscriptions: {len(subscribed_tokens)} stocks")

async def on_close_broadcast_socket(close_msg):
    print("🔌 Broadcast socket: Disconnected", close_msg, "\n")

async def on_error_broadcast_socket(error):
    print("❌ Broadcast socket: Error", error, "\n")

async def on_touchline(message):
    global Nse_20, strategy_running
    
    if not strategy_running or Nse_20 is None:
        return
    
    try:
        # Process real-time market data - FIXED FORMAT
        if not isinstance(message, dict) or 'data' not in message:
            return
            
        stock_data = message['data']
        
        # Extract token from the correct location
        if 'Scrip' not in stock_data or 'token' not in stock_data['Scrip']:
            return
            
        token_str = str(stock_data['Scrip']['token'])
        
        # Skip empty or invalid tokens
        if not token_str or token_str == '' or token_str == 'None':
            return
        
        try:
            token_id = int(token_str)
        except (ValueError, TypeError):
            return  # Skip invalid tokens silently
        
        if token_id not in Nse_20.index:
            return
        
        # Get stock information
        Stock_Data = Nse_20.loc[token_id]
        symbol = Stock_Data['Symbol']
        
        # Extract real-time prices with validation - FIXED FIELD NAMES
        try:
            CMP = float(stock_data.get('LTP', '0').replace(',', ''))  # Last Traded Price
            High = float(stock_data.get('HighPrice', '0').replace(',', ''))  # Day High
            PercentChange = float(stock_data.get('PercNetChange', '0'))  # Percent Change
        except (ValueError, TypeError):
            return  # Skip invalid price data
        
        if CMP <= 0 or High <= 0:
            return  # Skip invalid data
        
        # UPDATE REAL-TIME PRICES FOR ALL OPEN POSITIONS (CONTINUOUS UPDATES)
        if Stock_Data["Position"] == 1:
            # Update position with real-time price and percentage change
            update_position_realtime(token_str, CMP)
        
        # Print real-time data for monitoring (reduced frequency)
        if token_id % 100 == 0:  # Print every 100th token to reduce console spam
            print(f"📊 {symbol} ({token_id}): LTP=₹{CMP:.2f}, High=₹{High:.2f}, Change={PercentChange:.2f}%")
        
        # ORIGINAL BUY CONDITION (EXACT SAME LOGIC)
        if (CMP > Stock_Data['High_Price']) and (Stock_Data["Position"] == 0) and (PercentChange < 15):
            # LOG ORDER INSTEAD
            print(f"🟢 BUY SIGNAL: {token_id} ({symbol}) at ₹{CMP:.2f} (Above 5-day high ₹{Stock_Data['High_Price']:.2f})")
            
            # EXACT ORIGINAL DATAFRAME UPDATES
            Nse_20.at[token_id, 'Position'] = 1
            Nse_20.at[token_id, 'StopLoss'] = High * 0.98
            
            # SAVE TO DATABASE FOR UI
            save_signal(token_str, symbol, 'BUY', CMP, High, High * 0.98, PercentChange)
            save_position(token_str, symbol, CMP, High * 0.98)

        # ORIGINAL SELL CONDITION (EXACT SAME LOGIC)
        elif (CMP < Stock_Data["StopLoss"]) and (Stock_Data["Position"] == 1):
            # LOG ORDER INSTEAD
            print(f"🔴 SELL SIGNAL: {token_id} ({symbol}) at ₹{CMP:.2f} (Stop Loss ₹{Stock_Data['StopLoss']:.2f} Hit)")
            
            # EXACT ORIGINAL DATAFRAME UPDATES
            Nse_20.at[token_id, 'Position'] = 0
            
            # SAVE TO DATABASE FOR UI
            save_signal(token_str, symbol, 'SELL', CMP, High, Stock_Data["StopLoss"], PercentChange)
            update_position(token_str, CMP)

        # EXACT ORIGINAL TRAILING STOP LOSS UPDATE
        if Stock_Data["Position"] == 1:
            Nse_20.loc[(Nse_20.index == token_id) & (Nse_20['Position'] == 1), ["StopLoss", 'High_Price']] = [High * 0.98, High]
                
    except Exception as e:
        print(f"Error in touchline callback: {e}")

async def on_bestfive(message):
    # Not needed for this strategy, but required for WebSocket
    pass

# Message socket callbacks (not needed for this strategy but required)
async def on_ready_message_socket(response):
    print("📨 Message socket: Ready", response, "\n")

async def on_close_message_socket(close_msg):
    print("📨 Message socket: Closed", close_msg)

async def on_error_message_socket(error):
    print("📨 Message socket: Error", error)

async def on_msg_message_socket(response):
    # Handle order updates, trade confirmations, etc. (not needed for this strategy)
    pass

# Main trading strategy function
async def main():
    global ibt_connect, strategy_running
    
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
    
    print("🚀 Starting B2C WebSocket Real Market Data Strategy (No orders)")
    print("=" * 70)
    
    # Prepare market data
    await prepare_market_data()
    
    # Initialize B2C Connect
    ibt_connect = IBTConnect(params={
        "baseurl": API_URL,
        "api_key": API_KEY,
        "debug": True
    })
    
    # Login
    totp = pyotp.TOTP(TOTP_SECRET).now()
    print(f"🔐 Generated TOTP: {totp}")
    
    logon_response = ibt_connect.login(params={
        "userId": USER_ID,
        "password": PASSWORD,
        "totp": totp
    })
    
    print("🔐 Login response:", logon_response.get('status', 'Unknown'))
    
    if logon_response.get("data") is not None:
        print("✅ Login successful - Setting up WebSocket connections")
        
        # Assign broadcast socket callbacks
        ibt_connect.on_open_broadcast_socket = on_open_broadcast_socket
        ibt_connect.on_close_broadcast_socket = on_close_broadcast_socket
        ibt_connect.on_error_broadcast_socket = on_error_broadcast_socket
        ibt_connect.on_touchline = on_touchline
        ibt_connect.on_bestfive = on_bestfive
        
        # Assign message socket callbacks
        ibt_connect.on_ready_message_socket = on_ready_message_socket
        ibt_connect.on_close_message_socket = on_close_message_socket
        ibt_connect.on_error_message_socket = on_error_message_socket
        ibt_connect.on_msg_message_socket = on_msg_message_socket
        
        # Start strategy
        strategy_running = True
        print("🎯 Strategy is now ACTIVE - Monitoring real-time market data")
        print("📊 Watch the dashboard at http://localhost:5000/dashboard")
        print("=" * 70)
        
        # Connect to WebSocket and start receiving real-time data
        await asyncio.gather(
            ibt_connect.connect_broadcast_socket(),
            ibt_connect.connect_message_socket(),
        )
    else:
        print("❌ Login failed - Cannot start strategy")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Strategy stopped by user")
        strategy_running = False
    except Exception as e:
        print(f"\n❌ Strategy error: {e}")
        strategy_running = False

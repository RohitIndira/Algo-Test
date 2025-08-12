"""
B2C TRADING STRATEGY - WEBSOCKET IMPLEMENTATION

This file implements a real-time algorithmic trading strategy that:
1. Connects to B2C broker via WebSocket for live market data
2. Monitors 1600+ NSE stocks in 20% price band
3. Executes momentum breakout strategy (buy when price > 5-day high)
4. Implements 2% trailing stop loss for risk management
5. Stores all data in SQLite database for tracking and analysis

Strategy Logic:
- BUY: When current price > 5-day high AND no existing position AND daily change < 15%
- SELL: When current price < stop loss (98% of day high) AND have open position
- STOP LOSS: Trailing stop at 98% of day's highest price (updates automatically)

Author: Trading Strategy Team
Version: 2.0 with Quantity Support
"""

# ============================================================================
# IMPORTS - All required libraries for the trading system
# ============================================================================

import asyncio          # For asynchronous programming (WebSocket handling)
import pyotp           # For generating TOTP codes (Two-Factor Authentication)
import pandas as pd    # For data manipulation and analysis
import requests        # For making HTTP requests to download market data
import zipfile         # For extracting NSE BhavCopy zip files
import gzip           # For extracting NSE security master gzip files
import json           # For handling JSON configuration files
import sqlite3        # For SQLite database operations
from io import StringIO, BytesIO  # For handling file-like objects in memory
from datetime import datetime, timedelta  # For date and time operations
import sys            # For system-specific parameters and functions
import os             # For operating system interface (file paths)

# ============================================================================
# SETUP B2C API LIBRARY PATH
# ============================================================================

# Add the b2c-api-python (1) directory to the Python path
# This allows us to import the B2C API library from the subdirectory
current_dir = os.path.dirname(os.path.abspath(__file__))  # Get current script directory
b2c_api_path = os.path.join(current_dir, 'b2c-api-python (1)')  # Build path to API library
sys.path.append(b2c_api_path)  # Add to Python path for imports

from pycloudrestapi import IBTConnect  # Import B2C API client library

# ============================================================================
# CONFIGURATION MANAGEMENT
# ============================================================================

def load_config():
    """
    Load trading configuration from b2c_config.json file
    
    Returns:
        dict: Configuration dictionary containing API credentials and trading parameters
        
    Configuration includes:
        - API credentials (user_id, password, api_key, api_url)
        - Trading parameters (order_quantity, stop_loss_percentage, etc.)
        - Risk management settings (max_percent_change, auto_square_off_time)
    """
    try:
        with open('b2c_config.json', 'r') as f:  # Open configuration file
            config = json.load(f)                # Parse JSON content
        return config                            # Return configuration dictionary
    except Exception as e:
        print(f"Error loading configuration: {e}")  # Print error if file not found/invalid
        return {}                                    # Return empty dictionary as fallback

# Load configuration into global variable for use throughout the application
config = load_config()

# ============================================================================
# TRADING PARAMETERS FROM CONFIGURATION
# ============================================================================

# Extract order quantity from config (how many shares to buy/sell per trade)
order_quantity = config.get('order_quantity', 1)  # Default to 1 share if not specified
print(f"📊 Order Quantity: {order_quantity} shares per trade")

# ============================================================================
# B2C API CREDENTIALS AND SETTINGS
# ============================================================================

# Extract B2C API configuration from loaded config file
API_KEY = config.get("api_key", "")      # API key for B2C authentication
USER_ID = config.get("user_id", "")      # User ID for B2C login
PASSWORD = config.get("password", "")     # Password for B2C login
API_URL = config.get("api_url", "")      # Base URL for B2C API endpoints
TOTP_SECRET = "DBUESNYUFRNQMD3Q"         # TOTP secret for 2FA (hardcoded for this implementation)

# ============================================================================
# GLOBAL VARIABLES FOR STRATEGY STATE
# ============================================================================

# Global variables to maintain strategy state across functions
Nse_20 = None           # Will store pandas DataFrame with filtered stock data (20% price band stocks)
ibt_connect = None      # Will store IBTConnect object for B2C API communication
strategy_running = False # Boolean flag to track if trading strategy is currently active

# ============================================================================
# DATABASE INITIALIZATION AND SCHEMA MANAGEMENT
# ============================================================================

def init_db():
    """
    Initialize SQLite database with all required tables for trading strategy
    
    Creates three main tables:
    1. tokens: Store stock information and 5-day high prices
    2. signals: Store every buy/sell decision made by the strategy
    3. positions: Store open and closed trading positions with P&L tracking
    
    Also handles database migration for quantity support in existing installations
    """
    conn = sqlite3.connect('trading_strategy.db')  # Connect to SQLite database file
    cursor = conn.cursor()                         # Create cursor for SQL operations
    
    # ========================================================================
    # CREATE TOKENS TABLE - Store basic stock information
    # ========================================================================
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tokens (
        token TEXT PRIMARY KEY,        -- Unique stock identifier (e.g., "1594" for RELIANCE)
        symbol TEXT,                   -- Stock symbol (e.g., "RELIANCE")
        series TEXT,                   -- Trading series (usually "EQ" for equity)
        name TEXT,                     -- Full company name (e.g., "Reliance Industries Ltd")
        isin TEXT,                     -- ISIN code for international identification
        high_price REAL,              -- 5-day highest price (breakout trigger level)
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- When this record was last updated
    )
    ''')
    
    # ========================================================================
    # CREATE SIGNALS TABLE - Store every trading decision (buy/sell signals)
    # ========================================================================
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,  -- Auto-incrementing unique ID
        token TEXT,                            -- Stock token (foreign key to tokens table)
        symbol TEXT,                           -- Stock symbol for easy reference
        signal_type TEXT,                      -- 'BUY' or 'SELL' signal type
        price REAL,                           -- Price at which signal was generated
        high_price REAL,                      -- Day's high price when signal was generated
        stop_loss REAL,                       -- Stop loss price calculated for this signal
        percent_change REAL,                  -- Percentage change from previous day
        quantity INTEGER DEFAULT 1,           -- Number of shares for this signal
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- When signal was generated
        FOREIGN KEY (token) REFERENCES tokens(token)    -- Link to tokens table
    )
    ''')
    
    # ========================================================================
    # CREATE POSITIONS TABLE - Track open and closed trading positions
    # ========================================================================
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,  -- Auto-incrementing unique ID
        token TEXT,                            -- Stock token (foreign key to tokens table)
        symbol TEXT,                           -- Stock symbol for easy reference
        entry_price REAL,                      -- Total amount invested (price × quantity)
        exit_price REAL,                       -- Total amount received when sold (NULL if still open)
        entry_time TIMESTAMP,                  -- When position was opened
        exit_time TIMESTAMP,                   -- When position was closed (NULL if still open)
        stop_loss REAL,                        -- Current stop loss price (updates with trailing stop)
        status TEXT,                           -- 'OPEN' or 'CLOSED' position status
        pnl REAL,                             -- Current profit/loss in rupees
        percent_gain REAL,                     -- Current profit/loss in percentage
        quantity INTEGER DEFAULT 1,           -- Number of shares in this position
        FOREIGN KEY (token) REFERENCES tokens(token)  -- Link to tokens table
    )
    ''')
    
    # ========================================================================
    # DATABASE MIGRATION - Add quantity columns to existing tables
    # ========================================================================
    # This section handles upgrading existing databases that don't have quantity support
    
    # Check if quantity column exists in signals table
    cursor.execute("PRAGMA table_info(signals)")
    signals_columns = [column[1] for column in cursor.fetchall()]
    
    if 'quantity' not in signals_columns:
        try:
            cursor.execute('ALTER TABLE signals ADD COLUMN quantity INTEGER DEFAULT 1')
            print("✅ Added quantity column to signals table")
        except sqlite3.OperationalError as e:
            print(f"⚠️ Could not add quantity to signals: {e}")
    
    # Check if quantity column exists in positions table
    cursor.execute("PRAGMA table_info(positions)")
    positions_columns = [column[1] for column in cursor.fetchall()]
    
    if 'quantity' not in positions_columns:
        try:
            cursor.execute('ALTER TABLE positions ADD COLUMN quantity INTEGER DEFAULT 1')
            print("✅ Added quantity column to positions table")
        except sqlite3.OperationalError as e:
            print(f"⚠️ Could not add quantity to positions: {e}")
    
    # Update existing records to have quantity = 1 for backward compatibility
    try:
        cursor.execute('UPDATE signals SET quantity = 1 WHERE quantity IS NULL')
        cursor.execute('UPDATE positions SET quantity = 1 WHERE quantity IS NULL')
    except sqlite3.OperationalError:
        pass  # Columns might not exist yet
    
    conn.commit()  # Save all changes to database
    conn.close()   # Close database connection
    print("🎯 Database schema updated with quantity support!")

# ============================================================================
# DATABASE HELPER FUNCTIONS - Save and update trading data
# ============================================================================

def save_token(token, symbol, series, name, isin, high_price):
    """
    Save or update stock information in the tokens table
    
    Args:
        token (str): Stock token/ID
        symbol (str): Stock symbol (e.g., "RELIANCE")
        series (str): Trading series (e.g., "EQ")
        name (str): Company name
        isin (str): ISIN code
        high_price (float): 5-day highest price
    """
    conn = sqlite3.connect('trading_strategy.db')
    cursor = conn.cursor()
    cursor.execute('''
    INSERT OR REPLACE INTO tokens (token, symbol, series, name, isin, high_price, last_updated)
    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (token, symbol, series, name, isin, high_price))
    conn.commit()
    conn.close()

def save_signal(token, symbol, signal_type, price, high_price, stop_loss, percent_change, quantity):
    """
    Save a trading signal (buy/sell decision) to the database
    
    Args:
        token (str): Stock token
        symbol (str): Stock symbol
        signal_type (str): 'BUY' or 'SELL'
        price (float): Price at which signal was generated
        high_price (float): Day's high price
        stop_loss (float): Calculated stop loss price
        percent_change (float): Daily percentage change
        quantity (int): Number of shares
    """
    conn = sqlite3.connect('trading_strategy.db')
    cursor = conn.cursor()
    
    # Get current IST time (Indian Standard Time)
    from datetime import timezone, timedelta
    ist = timezone(timedelta(hours=5, minutes=30))  # IST is UTC+5:30
    current_ist_time = datetime.now(ist).strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
    INSERT INTO signals (token, symbol, signal_type, price, high_price, stop_loss, percent_change, quantity, timestamp)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (token, symbol, signal_type, price, high_price, stop_loss, percent_change, quantity, current_ist_time))
    conn.commit()
    conn.close()

def save_position(token, symbol, entry_price, stop_loss, quantity, day_high=None):
    """
    Save a new trading position (when we buy a stock) to the database
    
    Args:
        token (str): Stock token
        symbol (str): Stock symbol
        entry_price (float): Price per share at which we bought
        stop_loss (float): Initial stop loss price
        quantity (int): Number of shares bought
        day_high (float, optional): Day's high price
    """
    conn = sqlite3.connect('trading_strategy.db')
    cursor = conn.cursor()
    
    # Get current IST time
    from datetime import timezone, timedelta
    ist = timezone(timedelta(hours=5, minutes=30))
    current_ist_time = datetime.now(ist).strftime('%Y-%m-%d %H:%M:%S')
    
    # Calculate total entry value based on quantity (total money invested)
    total_entry_value = entry_price * quantity
    
    # Add day_high column if it doesn't exist (database migration)
    try:
        cursor.execute('ALTER TABLE positions ADD COLUMN day_high REAL')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # 🔧 NEW: Add columns for LTP-based stop loss strategy
    try:
        cursor.execute('ALTER TABLE positions ADD COLUMN entry_price_per_share REAL')
        cursor.execute('ALTER TABLE positions ADD COLUMN profit_threshold REAL')
        cursor.execute('ALTER TABLE positions ADD COLUMN is_trailing BOOLEAN DEFAULT 0')
    except sqlite3.OperationalError:
        pass  # Columns already exist
    
    # 🔧 NEW: Calculate LTP-based stop loss data
    entry_price_per_share = entry_price  # This is the actual entry price per share
    profit_threshold = entry_price_per_share * 1.02  # 2% above entry price
    
    cursor.execute('''
    INSERT INTO positions (token, symbol, entry_price, entry_time, stop_loss, status, quantity, day_high, entry_price_per_share, profit_threshold, is_trailing)
    VALUES (?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?, 0)
    ''', (token, symbol, total_entry_value, current_ist_time, stop_loss, quantity, day_high or entry_price, entry_price_per_share, profit_threshold))
    conn.commit()
    conn.close()

def update_position_realtime(token, current_price, day_high):
    """
    Update position with real-time price data, P&L calculation, and day high tracking
    
    This function is called every time we receive new price data for a stock we own.
    It calculates current profit/loss and updates the day high if needed.
    
    Args:
        token (str): Stock token
        current_price (float): Current market price per share
        day_high (float): Today's highest price for this stock
    """
    conn = sqlite3.connect('trading_strategy.db')
    cursor = conn.cursor()
    
    # Get existing position data
    cursor.execute('SELECT entry_price, quantity, day_high FROM positions WHERE token = ? AND status = "OPEN"', (token,))
    result = cursor.fetchone()
    
    if result:  # If we have an open position for this stock
        total_entry_value = result[0]                                    # Total money we invested
        quantity = result[1] if result[1] is not None else 1            # Number of shares (handle NULL)
        current_day_high = result[2] if result[2] is not None else current_price  # Current day high
        entry_price_per_share = total_entry_value / quantity            # Calculate price per share
        
        # Update day high if today's high is higher than stored day high
        updated_day_high = max(current_day_high, day_high)
        
        # Calculate current P&L based on quantity
        current_total_value = current_price * quantity                   # Current total value of our position
        pnl = current_total_value - total_entry_value                   # Profit/Loss in rupees
        percent_gain = (pnl / total_entry_value) * 100                 # Profit/Loss in percentage
        
        # Update database with current P&L and day high (keep status as OPEN)
        cursor.execute('''
        UPDATE positions 
        SET pnl = ?, percent_gain = ?, day_high = ?
        WHERE token = ? AND status = 'OPEN'
        ''', (pnl, percent_gain, updated_day_high, token))
    
    conn.commit()
    conn.close()

def update_position(token, exit_price):
    """
    Close a position (when we sell a stock) and calculate final P&L
    
    Args:
        token (str): Stock token
        exit_price (float): Price per share at which we sold
    """
    conn = sqlite3.connect('trading_strategy.db')
    cursor = conn.cursor()
    
    # Get position data for the stock we're selling
    cursor.execute('SELECT entry_price, quantity FROM positions WHERE token = ? AND status = "OPEN"', (token,))
    result = cursor.fetchone()
    
    if result:  # If we have an open position
        total_entry_value = result[0]                                    # Total money we invested
        quantity = result[1] if result[1] is not None else 1            # Number of shares
        
        # Calculate final exit value and P&L based on quantity
        total_exit_value = exit_price * quantity                        # Total money we received
        pnl = total_exit_value - total_entry_value                     # Final profit/loss
        percent_gain = (pnl / total_entry_value) * 100                # Final percentage gain/loss
        
        # Get current IST time for exit timestamp
        from datetime import timezone, timedelta
        ist = timezone(timedelta(hours=5, minutes=30))
        current_ist_time = datetime.now(ist).strftime('%Y-%m-%d %H:%M:%S')
        
        # Update position to CLOSED with final P&L
        cursor.execute('''
        UPDATE positions 
        SET exit_price = ?, exit_time = ?, status = 'CLOSED', pnl = ?, percent_gain = ?
        WHERE token = ? AND status = 'OPEN'
        ''', (total_exit_value, current_ist_time, pnl, percent_gain, token))
    
    conn.commit()
    conn.close()

# ============================================================================
# ORDER PLACEMENT FUNCTION (CURRENTLY DISABLED FOR SIMULATION)
# ============================================================================

def Place_Order(token, quantity, price, order_side):
    """
    Order placement function - CURRENTLY DISABLED FOR SIMULATION MODE
    
    This function would normally place actual buy/sell orders with the broker.
    For safety and testing purposes, it's currently disabled and only logs orders.
    
    Args:
        token (str): Stock token
        quantity (int): Number of shares to buy/sell
        price (float): Price per share
        order_side (str): 'BUY' or 'SELL'
    
    Note: To enable actual trading, uncomment the order placement code below
    """
    # ORIGINAL ORDER PLACEMENT CODE - COMMENTED OUT FOR SAFETY
    # This code would place actual orders with the broker:
    # 
    # orderParams = {
    #     "scrip_info": {
    #         "exchange": "NSE_EQ",           # NSE Equity exchange
    #         "scrip_token": int(token),      # Stock token as integer
    #         "symbol": symbol,               # Stock symbol
    #         "series": "EQ",                 # Equity series
    #         "expiry_date": "",              # Not applicable for equity
    #         "strike_price": "",             # Not applicable for equity
    #         "option_type": ""               # Not applicable for equity
    #     },
    #     "transaction_type": order_side,     # 'BUY' or 'SELL'
    #     "product_type": "INTRADAY",         # Intraday trading (square off same day)
    #     "order_type": "MARKET",             # Market order (execute at current price)
    #     "quantity": quantity,               # Number of shares
    #     "price": price,                     # Price per share
    #     "trigger_price": 0,                 # Not used for market orders
    #     "disclosed_quantity": 0,            # Show full quantity
    #     "validity": "DAY",                  # Order valid for current trading day
    #     "validity_days": 0,                 # Not applicable for DAY orders
    #     "is_amo": False,                    # Not an After Market Order
    #     "order_identifier": "",             # Optional order identifier
    #     "part_code": "",                    # Optional part code
    #     "algo_id": "",                      # Optional algorithm ID
    #     "strategy_id": "",                  # Optional strategy ID
    #     "vender_code": ""                   # Optional vendor code
    # }
    # response = ibt_connect.place_order(orderParams)  # Place the actual order
    
    # SIMULATION MODE - JUST LOG THE ORDER (NO ACTUAL PLACEMENT)
    total_value = quantity * price  # Calculate total order value
    print(f'\n📋 ORDER LOG: {order_side} {quantity} shares of {token} at ₹{price:.2f} each (Total: ₹{total_value:.2f}) (NOT PLACED)\n')
    return  # Return without placing actual order

# ============================================================================
# MARKET DATA PREPARATION - Download and process NSE data
# ============================================================================

async def prepare_market_data():
    """
    Download and prepare market data for trading strategy
    
    This function performs several key tasks:
    1. Downloads NSE BhavCopy data for last 6 days to calculate 5-day high prices
    2. Downloads NSE security master data for stock details
    3. Downloads list of stocks in 20% price band (high volatility stocks)
    4. Merges all data into a single DataFrame for strategy use
    5. Saves all stock information to database
    
    Returns:
        pandas.DataFrame: Processed stock data ready for trading strategy
    """
    global Nse_20  # Use global variable to store processed data
    
    print("📊 Fetching historical high prices...")
    
    # ========================================================================
    # STEP 1: Download NSE BhavCopy data for 5-day high price calculation
    # ========================================================================
    
    bhavcopy = pd.DataFrame()  # Initialize empty DataFrame to store BhavCopy data
    
    # Loop through last 6 days to get sufficient data for 5-day high calculation
    for i in range(6):
        # Format date for NSE BhavCopy URL (YYYYMMDD format)
        date_str = datetime.strftime(datetime.now().date() - timedelta(i), "%Y%m%d")
        
        # Build URL for NSE BhavCopy zip file
        zip_url = f'https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{date_str}_F_0000.csv.zip'
        
        # Download with proper User-Agent header to avoid blocking
        response = requests.get(zip_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0'
        })
        
        if response.status_code == 200:  # If download successful
            zip_content = BytesIO(response.content)              # Create file-like object from response
            with zipfile.ZipFile(zip_content, 'r') as zip_ref:   # Open zip file
                csv_filename = zip_ref.namelist()[0]             # Get CSV filename inside zip
                with zip_ref.open(csv_filename) as file:         # Open CSV file
                    # Read CSV and extract required columns: Trade Date, Symbol, High Price
                    daily_data = pd.read_csv(file)[['TradDt', 'TckrSymb', 'HghPric']]
                    bhavcopy = pd.concat([daily_data, bhavcopy])  # Append to main DataFrame
    
    # Group by symbol and calculate maximum high price (5-day high)
    bhavcopy = bhavcopy.groupby('TckrSymb', as_index=False).agg({'HghPric': 'max'})
    bhavcopy = bhavcopy.rename(columns={'TckrSymb': 'Symbol', 'HghPric': 'High_Price'})

    # ========================================================================
    # STEP 2: Download NSE security master data for stock details
    # ========================================================================
    
    NSE_DPR = pd.DataFrame()  # Initialize empty DataFrame for security master data
    
    # Try last 5 days to find available security master file
    for i in range(5):
        # Format date for security master URL (DDMMYYYY format)
        date_str = datetime.strftime(datetime.now().date() - timedelta(i), '%d%m%Y')
        url = f"https://nsearchives.nseindia.com/content/cm/NSE_CM_security_{date_str}.csv.gz"
        
        # Download with proper User-Agent header
        response = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0'
        })
        
        if response.status_code == 200:  # If download successful
            with gzip.open(BytesIO(response.content), 'rt') as f:  # Open gzip file
                # Read CSV and extract required columns
                NSE_DPR = pd.read_csv(f)[['FinInstrmId', 'TckrSymb', 'SctySrs', 'FinInstrmNm', 'ISIN']]
                NSE_DPR = NSE_DPR.dropna(how='all', axis=1).fillna(" ")  # Clean data
                NSE_DPR.rename(columns={'TckrSymb': 'Symbol', 'SctySrs': 'Series'}, inplace=True)
                break  # Stop after first successful download

    # ========================================================================
    # STEP 3: Download list of stocks in 20% price band (high volatility)
    # ========================================================================
    
    Nse_20 = 0  # Initialize variable
    
    # Try last 5 days to find available price band file
    for i in range(0, 5):
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0'}
        date_str = datetime.strftime(datetime.now().date() - timedelta(i), '%d%m%Y')
        url = f"https://nsearchives.nseindia.com/content/equities/sec_list_{date_str}.csv"
        
        nseBand = requests.get(url, headers=headers)
        if nseBand.status_code == 200:  # If download successful
            # Read CSV, skip first row (header), use columns 0, 1, 3
            Nse_20 = pd.read_csv(StringIO(nseBand.text), sep=',', skiprows=1, header=None)[[0, 1, 3]]
            Nse_20 = Nse_20.rename(columns={0: 'Symbol', 1: 'Series', 3: 'Band'})
            
            # Filter for stocks in 20% price band and EQ (equity) series
            Nse_20 = Nse_20.loc[(Nse_20['Band'].astype(str).isin(['20', 20])) & (Nse_20['Series'] == "EQ")]
            Nse_20 = Nse_20.fillna(0)  # Fill missing values with 0
            
            # Merge with security master data to get additional stock details
            Nse_20 = pd.merge(Nse_20, NSE_DPR, on=['Symbol', 'Series'], how='left')
            break  # Stop after first successful download

    # ========================================================================
    # STEP 4: Merge all data and prepare final DataFrame
    # ========================================================================
    
    # Merge with BhavCopy data to get 5-day high prices
    Nse_20 = pd.merge(Nse_20, bhavcopy, on=['Symbol'], how='left')
    
    # Add columns for position tracking (used by trading strategy)
    Nse_20['Position'] = 0      # 0 = no position, 1 = have position
    Nse_20["StopLoss"] = 0      # Current stop loss price (0 = no stop loss)
    
    # Set FinInstrmId (token) as index for fast lookup during trading
    Nse_20.set_index('FinInstrmId', inplace=True)
    
    print(f"✅ Found {len(Nse_20)} stocks in 20% price band")
    
    # ========================================================================
    # STEP 5: Save all stock information to database
    # ========================================================================
    
    # Save each stock's information to the tokens table
    for token in Nse_20.index:
        row = Nse_20.loc[token]  # Get row data for this token
        save_token(
            str(token),                    # Stock token as string
            row['Symbol'],                 # Stock symbol (e.g., "RELIANCE")
            row['Series'],                 # Trading series (e.g., "EQ")
            row.get('FinInstrmNm', ''),   # Company name (with fallback)
            row.get('ISIN', ''),          # ISIN code (with fallback)
            row.get('High_Price', 0)      # 5-day high price (with fallback)
        )
    
    return Nse_20  # Return the prepared DataFrame for use by trading strategy

# ============================================================================
# WEBSOCKET CALLBACK FUNCTIONS - Handle real-time market data
# ============================================================================

# Global set to track which stock tokens we've subscribed to (prevents duplicates)
subscribed_tokens = set()

# ============================================================================
# PRODUCTION FIX: DATABASE AS SINGLE SOURCE OF TRUTH
# ============================================================================

def check_position_from_database(token):
    """
    PRODUCTION FIX: Always check position status from database, not DataFrame
    This prevents race conditions and ensures accurate state
    """
    conn = sqlite3.connect('trading_strategy.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT COUNT(*), MAX(entry_time) 
    FROM positions 
    WHERE token = ? AND status = "OPEN"
    ''', (token,))
    
    result = cursor.fetchone()
    has_position = result[0] > 0
    last_entry_time = result[1]
    
    conn.close()
    return has_position, last_entry_time

def get_stop_loss_from_database(token):
    """
    PRODUCTION FIX: Get current stop loss from database, not DataFrame
    """
    conn = sqlite3.connect('trading_strategy.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT stop_loss 
    FROM positions 
    WHERE token = ? AND status = "OPEN" 
    ORDER BY entry_time DESC LIMIT 1
    ''', (token,))
    
    result = cursor.fetchone()
    stop_loss = result[0] if result else 0
    
    conn.close()
    return stop_loss

def get_precise_timestamp():
    """
    PRODUCTION FIX: Get timestamp with millisecond precision
    """
    from datetime import timezone, timedelta
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

# ============================================================================
# 🔧 NEW: LTP-BASED STOP LOSS HELPER FUNCTIONS
# ============================================================================

def get_position_details_from_database(token):
    """
    🔧 NEW: Get complete position details for LTP-based stop loss strategy
    
    Returns:
        tuple: (entry_price_per_share, profit_threshold, is_trailing, current_stop_loss)
    """
    conn = sqlite3.connect('trading_strategy.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT entry_price_per_share, profit_threshold, is_trailing, stop_loss 
    FROM positions 
    WHERE token = ? AND status = "OPEN" 
    ORDER BY entry_time DESC LIMIT 1
    ''', (token,))
    
    result = cursor.fetchone()
    if result:
        entry_price_per_share = result[0] if result[0] is not None else 0
        profit_threshold = result[1] if result[1] is not None else 0
        is_trailing = result[2] if result[2] is not None else 0
        current_stop_loss = result[3] if result[3] is not None else 0
        conn.close()
        return entry_price_per_share, profit_threshold, is_trailing, current_stop_loss
    
    conn.close()
    return 0, 0, 0, 0

def update_trailing_status(token, is_trailing):
    """
    🔧 NEW: Update trailing status when stock moves 2% above entry
    """
    conn = sqlite3.connect('trading_strategy.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    UPDATE positions 
    SET is_trailing = ? 
    WHERE token = ? AND status = 'OPEN'
    ''', (is_trailing, token))
    
    conn.commit()
    conn.close()

def calculate_ltp_based_stop_loss(entry_price, current_price, day_high, is_trailing):
    """
    🔧 NEW: Calculate stop loss based on LTP strategy
    
    Args:
        entry_price (float): Entry price per share
        current_price (float): Current market price
        day_high (float): Today's highest price
        is_trailing (bool): Whether we're in trailing mode
    
    Returns:
        tuple: (new_stop_loss, should_start_trailing)
    """
    # Calculate profit threshold (2% above entry)
    profit_threshold = entry_price * 1.02
    
    if current_price >= profit_threshold and not is_trailing:
        # Start trailing from day high
        new_stop_loss = day_high * 0.98
        should_start_trailing = True
        print(f"🎯 STARTING TRAILING: Price ₹{current_price:.2f} >= Threshold ₹{profit_threshold:.2f}")
    elif is_trailing:
        # Continue trailing from day high
        new_stop_loss = day_high * 0.98
        should_start_trailing = False
    else:
        # Keep original stop loss (2% below entry price)
        new_stop_loss = entry_price * 0.98
        should_start_trailing = False
    
    return new_stop_loss, should_start_trailing

async def on_open_broadcast_socket(message):
    """
    Called when WebSocket connection is established
    
    This function subscribes to real-time price updates for all stocks in our watchlist.
    It processes stocks in batches to avoid overwhelming the WebSocket connection.
    
    Args:
        message: Connection status message from WebSocket
    """
    global Nse_20, ibt_connect, subscribed_tokens
    print('🔌 Broadcast socket: Connected', message, "\n")
    
    if Nse_20 is not None and len(Nse_20) > 0:
        # Clear any previous subscriptions to start fresh
        subscribed_tokens.clear()
        
        # Prepare list of all stock tokens to subscribe to
        tokens_to_subscribe = []
        for token in Nse_20.index:  # Loop through all stocks in our filtered list
            token_str = str(token)  # Convert token to string format
            if token_str not in subscribed_tokens:  # Avoid duplicate subscriptions
                # Add token to subscription list with market segment ID
                tokens_to_subscribe.append({"MktSegId": "1", "token": token_str})
                subscribed_tokens.add(token_str)  # Track that we've subscribed to this token
        
        # Subscribe in batches to avoid overwhelming the WebSocket
        batch_size = 50  # Process 50 stocks at a time
        total_batches = (len(tokens_to_subscribe) + batch_size - 1) // batch_size
        
        # Process each batch of stock subscriptions
        for i in range(0, len(tokens_to_subscribe), batch_size):
            batch = tokens_to_subscribe[i:i + batch_size]  # Get current batch
            batch_num = i // batch_size + 1  # Calculate batch number for logging
            
            try:
                # Subscribe to this batch of stocks
                await ibt_connect.touchline_subscription(batch)
                print(f"✅ Subscribed to batch {batch_num}: {len(batch)} tokens")
                await asyncio.sleep(0.2)  # Small delay to prevent rate limiting
            except Exception as e:
                print(f"❌ Error subscribing to batch {batch_num}: {e}")
                # Continue with next batch even if one fails (robust error handling)
                continue
        
        print(f"🎯 Total subscriptions: {len(subscribed_tokens)} stocks")

async def on_close_broadcast_socket(close_msg):
    """
    Called when WebSocket connection is closed
    
    Args:
        close_msg: Message explaining why connection was closed
    """
    print("🔌 Broadcast socket: Disconnected", close_msg, "\n")

async def on_error_broadcast_socket(error):
    """
    Called when WebSocket encounters an error
    
    Args:
        error: Error details from WebSocket
    """
    print("❌ Broadcast socket: Error", error, "\n")

async def on_touchline(message):
    """
    MAIN TRADING LOGIC - Called every time we receive real-time stock price data
    
    This is the heart of the trading strategy. It processes each price update and:
    1. Validates the incoming data
    2. Checks current position status from database
    3. Implements buy logic (momentum breakout)
    4. Implements sell logic (stop loss hit)
    5. Updates trailing stop loss
    6. Updates real-time P&L for open positions
    
    Args:
        message: Real-time stock price data from WebSocket
    """
    global Nse_20, strategy_running, order_quantity
    
    if not strategy_running or Nse_20 is None:
        return
    
    try:
        # 🔧 ENHANCED WebSocket data validation
        if not isinstance(message, dict) or 'data' not in message:
            return
            
        stock_data = message['data']
        
        # Validate WebSocket data structure
        if not isinstance(stock_data, dict) or 'Scrip' not in stock_data:
            return
            
        if 'token' not in stock_data['Scrip']:
            return
            
        token_str = str(stock_data['Scrip']['token'])
        
        # Enhanced token validation
        if not token_str or token_str in ['', 'None', '0']:
            return
        
        try:
            token_id = int(token_str)
        except (ValueError, TypeError):
            return
        
        if token_id not in Nse_20.index:
            return
        
        # Get stock information
        Stock_Data = Nse_20.loc[token_id]
        symbol = Stock_Data['Symbol']
        
        # 🔧 ENHANCED price data validation
        try:
            CMP = float(stock_data.get('LTP', '0').replace(',', ''))
            High = float(stock_data.get('HighPrice', '0').replace(',', ''))
            PercentChange = float(stock_data.get('PercNetChange', '0'))
        except (ValueError, TypeError, AttributeError):
            return
        
        # Validate price data quality
        if CMP <= 0 or High <= 0 or CMP > 100000 or High > 100000:
            return
        
        # 🔧 PRODUCTION FIX: Use DATABASE as single source of truth for position status
        has_open_position, last_entry_time = check_position_from_database(token_str)
        current_stop_loss = get_stop_loss_from_database(token_str)
        
        # No artificial cooldown - use real market timing
        can_trade = True
        
        # UPDATE REAL-TIME PRICES FOR ALL OPEN POSITIONS
        if has_open_position:
            update_position_realtime(token_str, CMP, High)
        
        # Enhanced monitoring with position status
        if token_id % 100 == 0:
            print(f"📊 {symbol} ({token_id}): LTP=₹{CMP:.2f}, High=₹{High:.2f}, Change={PercentChange:.2f}%, Position={has_open_position}")
        
        # 🔧 FIXED BUY CONDITION - Use database state + enhanced validation
        if (CMP > Stock_Data['High_Price']) and (not has_open_position) and (PercentChange < 15):
            # Get precise entry timestamp
            from datetime import timezone, timedelta
            ist = timezone(timedelta(hours=5, minutes=30))
            entry_timestamp = datetime.now(ist).strftime('%Y-%m-%d %H:%M:%S')
            
            # 🔧 NEW: Calculate LTP-based stop loss (2% below entry price)
            total_investment = CMP * order_quantity
            stop_loss_price = CMP * 0.98  # Use entry price instead of day high
            
            # Enhanced logging
            print(f"\n🟢 BUY SIGNAL TRIGGERED:")
            print(f"   📈 Stock: {symbol} ({token_id})")
            print(f"   💰 Price: ₹{CMP:.2f} per share")
            print(f"   📊 Quantity: {order_quantity} shares")
            print(f"   💵 Total Investment: ₹{total_investment:.2f}")
            print(f"   📅 Entry Time: {entry_timestamp}")
            print(f"   🛡️ Stop Loss: ₹{stop_loss_price:.2f}")
            print(f"   📈 Condition: CMP (₹{CMP:.2f}) > 5-day High (₹{Stock_Data['High_Price']:.2f})")
            
            # Update DataFrame state AFTER logging (fix pandas warning)
            Nse_20.at[token_id, 'Position'] = 1
            Nse_20.at[token_id, 'StopLoss'] = float(stop_loss_price)
            
            # Save to database
            save_signal(token_str, symbol, 'BUY', CMP, High, stop_loss_price, PercentChange, order_quantity)
            save_position(token_str, symbol, CMP, stop_loss_price, order_quantity, High)

        # 🔧 FIXED SELL CONDITION - Use database state + enhanced validation (NO COOLDOWN)
        elif (CMP < current_stop_loss) and (has_open_position) and (current_stop_loss > 0):
            # Get precise exit timestamp
            from datetime import timezone, timedelta
            ist = timezone(timedelta(hours=5, minutes=30))
            exit_timestamp = datetime.now(ist).strftime('%Y-%m-%d %H:%M:%S')
            
            # Calculate exit value
            total_exit_value = CMP * order_quantity
            
            # Enhanced logging
            print(f"\n🔴 SELL SIGNAL TRIGGERED:")
            print(f"   📉 Stock: {symbol} ({token_id})")
            print(f"   💰 Exit Price: ₹{CMP:.2f} per share")
            print(f"   📊 Quantity: {order_quantity} shares")
            print(f"   💵 Total Exit Value: ₹{total_exit_value:.2f}")
            print(f"   📅 Exit Time: {exit_timestamp}")
            print(f"   🛡️ Stop Loss Hit: ₹{current_stop_loss:.2f}")
            print(f"   📉 Condition: CMP (₹{CMP:.2f}) < Stop Loss (₹{current_stop_loss:.2f})")
            
            # Update DataFrame state AFTER logging
            Nse_20.at[token_id, 'Position'] = 0
            Nse_20.at[token_id, 'StopLoss'] = 0
            
            # Save to database
            save_signal(token_str, symbol, 'SELL', CMP, High, current_stop_loss, PercentChange, order_quantity)
            update_position(token_str, CMP)

        # 🔧 NEW: LTP-BASED TRAILING STOP LOSS LOGIC
        if has_open_position and High > 0:
            # Get position details for LTP-based strategy
            entry_price_per_share, profit_threshold, is_trailing, current_stop_loss = get_position_details_from_database(token_str)
            
            if entry_price_per_share > 0:  # Valid position data
                # Calculate new stop loss using LTP-based strategy
                new_stop_loss, should_start_trailing = calculate_ltp_based_stop_loss(
                    entry_price_per_share, CMP, High, is_trailing
                )
                
                # Update trailing status if we should start trailing
                if should_start_trailing:
                    update_trailing_status(token_str, 1)  # Set is_trailing = 1
                
                # Only update stop loss if it's higher than current (never lower stop loss)
                if new_stop_loss > current_stop_loss:
                    # Update DataFrame
                    Nse_20.at[token_id, 'StopLoss'] = new_stop_loss
                    Nse_20.at[token_id, 'High_Price'] = High
                    
                    # Update database for persistence
                    conn = sqlite3.connect('trading_strategy.db')
                    cursor = conn.cursor()
                    cursor.execute('''
                    UPDATE positions 
                    SET stop_loss = ? 
                    WHERE token = ? AND status = 'OPEN'
                    ''', (new_stop_loss, token_str))
                    conn.commit()
                    conn.close()
                    
                    # Log trailing update
                    if token_id % 100 == 0:  # Log for every 100th token to avoid spam
                        trailing_status = "TRAILING" if is_trailing or should_start_trailing else "FIXED"
                        print(f"🛡️ {symbol}: Stop Loss updated to ₹{new_stop_loss:.2f} ({trailing_status})")
                
    except Exception as e:
        print(f"❌ Error in touchline callback for {symbol if 'symbol' in locals() else 'unknown'}: {e}")
        import traceback
        traceback.print_exc()

async def on_bestfive(message):
    """
    Called when we receive best 5 bid/ask data from WebSocket
    
    This callback is not used by our current strategy but is required by the WebSocket API.
    Best 5 data shows the top 5 buy and sell orders with their quantities and prices.
    
    Args:
        message: Best 5 bid/ask data from WebSocket
    """
    # Not needed for this momentum breakout strategy, but required for WebSocket
    pass

# ============================================================================
# MESSAGE SOCKET CALLBACKS - Handle order updates and confirmations
# ============================================================================

async def on_ready_message_socket(response):
    """
    Called when message socket is ready to receive order updates
    
    The message socket handles order confirmations, trade updates, and other
    account-related messages. Currently not used since we're in simulation mode.
    
    Args:
        response: Ready status message from message socket
    """
    print("📨 Message socket: Ready", response, "\n")

async def on_close_message_socket(close_msg):
    """
    Called when message socket connection is closed
    
    Args:
        close_msg: Message explaining why connection was closed
    """
    print("📨 Message socket: Closed", close_msg)

async def on_error_message_socket(error):
    """
    Called when message socket encounters an error
    
    Args:
        error: Error details from message socket
    """
    print("📨 Message socket: Error", error)

async def on_msg_message_socket(response):
    """
    Called when we receive order updates, trade confirmations, etc.
    
    This would handle:
    - Order placement confirmations
    - Order execution notifications
    - Trade confirmations
    - Account balance updates
    - Error messages from broker
    
    Currently not needed since we're running in simulation mode.
    
    Args:
        response: Order/trade update message from broker
    """
    # Handle order updates, trade confirmations, etc. (not needed for simulation mode)
    pass

# ============================================================================
# MAIN FUNCTION - Entry point for the trading strategy
# ============================================================================

async def main():
    """
    Main function that orchestrates the entire trading strategy
    
    This function:
    1. Initializes the database
    2. Cleans existing data for fresh start
    3. Downloads and prepares market data
    4. Connects to B2C API with authentication
    5. Sets up WebSocket callbacks
    6. Starts real-time trading strategy
    
    The function runs indefinitely, processing real-time market data
    and making trading decisions based on the momentum breakout strategy.
    """
    global ibt_connect, strategy_running
    
    # ========================================================================
    # STEP 1: Initialize database and clean existing data
    # ========================================================================
    
    # Initialize database with quantity support and handle migrations
    init_db()
    
    # Clean existing data for fresh start (optional - can be commented out to preserve data)
    conn = sqlite3.connect('trading_strategy.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM signals')    # Remove old trading signals
    cursor.execute('DELETE FROM positions')  # Remove old positions
    cursor.execute('DELETE FROM tokens')     # Remove old stock data
    conn.commit()
    conn.close()
    
    # ========================================================================
    # STEP 2: Display startup information
    # ========================================================================
    
    print("🚀 Starting B2C WebSocket Real Market Data Strategy with Quantity Support")
    print(f"📊 Configured for {order_quantity} shares per trade")
    print("=" * 70)
    
    # ========================================================================
    # STEP 3: Prepare market data (download NSE data and filter stocks)
    # ========================================================================
    
    # Download and process market data (this takes a few minutes)
    await prepare_market_data()
    
    # ========================================================================
    # STEP 4: Initialize B2C API connection
    # ========================================================================
    
    # Create B2C API client with configuration
    ibt_connect = IBTConnect(params={
        "baseurl": API_URL,    # B2C API base URL
        "api_key": API_KEY,    # API key for authentication
        "debug": True          # Enable debug logging
    })
    
    # ========================================================================
    # STEP 5: Authenticate with B2C broker
    # ========================================================================
    
    # Generate TOTP code for two-factor authentication
    totp = pyotp.TOTP(TOTP_SECRET).now()
    print(f"🔐 Generated TOTP: {totp}")
    
    # Attempt login with credentials
    logon_response = ibt_connect.login(params={
        "userId": USER_ID,      # User ID from configuration
        "password": PASSWORD,   # Password from configuration
        "totp": totp           # Generated TOTP code
    })
    
    print("🔐 Login response:", logon_response.get('status', 'Unknown'))
    
    # ========================================================================
    # STEP 6: Set up WebSocket connections and start strategy
    # ========================================================================
    
    if logon_response.get("data") is not None:  # If login successful
        print("✅ Login successful - Setting up WebSocket connections")
        
        # Assign broadcast socket callbacks (for market data)
        ibt_connect.on_open_broadcast_socket = on_open_broadcast_socket    # Connection established
        ibt_connect.on_close_broadcast_socket = on_close_broadcast_socket  # Connection closed
        ibt_connect.on_error_broadcast_socket = on_error_broadcast_socket  # Connection error
        ibt_connect.on_touchline = on_touchline                           # Real-time price data (MAIN LOGIC)
        ibt_connect.on_bestfive = on_bestfive                             # Best 5 bid/ask data
        
        # Assign message socket callbacks (for order updates)
        ibt_connect.on_ready_message_socket = on_ready_message_socket      # Message socket ready
        ibt_connect.on_close_message_socket = on_close_message_socket      # Message socket closed
        ibt_connect.on_error_message_socket = on_error_message_socket      # Message socket error
        ibt_connect.on_msg_message_socket = on_msg_message_socket          # Order/trade updates
        
        # ====================================================================
        # STEP 7: Start the trading strategy
        # ====================================================================
        
        # Set strategy as active
        strategy_running = True
        print("🎯 Strategy is now ACTIVE - Monitoring real-time market data")
        print("📊 Watch the dashboard at http://localhost:5000/dashboard")
        print("=" * 70)
        
        # Connect to both WebSocket streams and start processing data
        # This will run indefinitely until interrupted
        await asyncio.gather(
            ibt_connect.connect_broadcast_socket(),  # Connect to market data stream
            ibt_connect.connect_message_socket(),    # Connect to order update stream
        )
    else:
        print("❌ Login failed - Cannot start strategy")

# ============================================================================
# SCRIPT ENTRY POINT - Run the strategy when script is executed
# ============================================================================

if __name__ == "__main__":
    """
    Entry point when script is run directly
    
    Handles:
    - Running the async main function
    - Graceful shutdown on Ctrl+C
    - Error handling and logging
    """
    try:
        # Run the main async function
        asyncio.run(main())
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        print("\n🛑 Strategy stopped by user")
        strategy_running = False
    except Exception as e:
        # Handle any other errors
        print(f"\n❌ Strategy error: {e}")
        strategy_running = False

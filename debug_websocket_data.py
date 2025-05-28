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

# Global variables
ibt_connect = None
strategy_running = False
message_count = 0

# DEBUG: Enhanced WebSocket callback functions with detailed logging
async def on_open_broadcast_socket(message):
    global ibt_connect
    print('🔌 DEBUG: Broadcast socket opened')
    print(f'📨 DEBUG: Open message: {message}')
    
    # Subscribe to just a few test tokens to see if we get data
    test_tokens = [
        {"MktSegId": "1", "token": "11536"},  # RELIANCE
        {"MktSegId": "1", "token": "11723"},  # TCS
        {"MktSegId": "1", "token": "10604"},  # INFY
    ]
    
    try:
        print(f"🔍 DEBUG: Subscribing to test tokens: {test_tokens}")
        await ibt_connect.touchline_subscription(test_tokens)
        print("✅ DEBUG: Test subscription successful")
    except Exception as e:
        print(f"❌ DEBUG: Subscription error: {e}")

async def on_close_broadcast_socket(close_msg):
    print(f"🔌 DEBUG: Broadcast socket closed: {close_msg}")

async def on_error_broadcast_socket(error):
    print(f"❌ DEBUG: Broadcast socket error: {error}")

async def on_touchline(message):
    global message_count
    message_count += 1
    
    print(f"\n🎯 DEBUG: TOUCHLINE DATA RECEIVED! (Message #{message_count})")
    print(f"📊 DEBUG: Raw message type: {type(message)}")
    print(f"📊 DEBUG: Raw message: {message}")
    
    try:
        # Try to extract data
        if isinstance(message, dict):
            data = message.get('data', [])
            print(f"📊 DEBUG: Extracted data: {data}")
            
            if isinstance(data, list):
                print(f"📊 DEBUG: Data is list with {len(data)} items")
                for i, item in enumerate(data):
                    print(f"📊 DEBUG: Item {i}: {item}")
            else:
                print(f"📊 DEBUG: Data is not list: {type(data)}")
        else:
            print(f"📊 DEBUG: Message is not dict: {type(message)}")
            
    except Exception as e:
        print(f"❌ DEBUG: Error processing touchline data: {e}")

async def on_bestfive(message):
    print(f"📊 DEBUG: BESTFIVE DATA RECEIVED: {message}")

# Message socket callbacks with debug
async def on_ready_message_socket(response):
    print(f"📨 DEBUG: Message socket ready: {response}")

async def on_close_message_socket(close_msg):
    print(f"📨 DEBUG: Message socket closed: {close_msg}")

async def on_error_message_socket(error):
    print(f"📨 DEBUG: Message socket error: {error}")

async def on_msg_message_socket(response):
    print(f"📨 DEBUG: Message socket data: {response}")

# Main debug function
async def debug_websocket():
    global ibt_connect, strategy_running
    
    print("🔍 DEBUG: Starting WebSocket Debug Session")
    print("=" * 60)
    
    # Initialize B2C Connect
    ibt_connect = IBTConnect(params={
        "baseurl": API_URL,
        "api_key": API_KEY,
        "debug": True
    })
    
    # Login
    totp = pyotp.TOTP(TOTP_SECRET).now()
    print(f"🔐 DEBUG: Generated TOTP: {totp}")
    
    logon_response = ibt_connect.login(params={
        "userId": USER_ID,
        "password": PASSWORD,
        "totp": totp
    })
    
    print(f"🔐 DEBUG: Login response: {logon_response}")
    
    if logon_response.get("data") is not None:
        print("✅ DEBUG: Login successful - Setting up WebSocket callbacks")
        
        # Assign ALL callback functions with debug
        ibt_connect.on_open_broadcast_socket = on_open_broadcast_socket
        ibt_connect.on_close_broadcast_socket = on_close_broadcast_socket
        ibt_connect.on_error_broadcast_socket = on_error_broadcast_socket
        ibt_connect.on_touchline = on_touchline
        ibt_connect.on_bestfive = on_bestfive
        
        ibt_connect.on_ready_message_socket = on_ready_message_socket
        ibt_connect.on_close_message_socket = on_close_message_socket
        ibt_connect.on_error_message_socket = on_error_message_socket
        ibt_connect.on_msg_message_socket = on_msg_message_socket
        
        strategy_running = True
        print("🎯 DEBUG: Starting WebSocket connections...")
        print("🔍 DEBUG: Waiting for data... (Press Ctrl+C to stop)")
        print("=" * 60)
        
        # Connect and wait for data
        await asyncio.gather(
            ibt_connect.connect_broadcast_socket(),
            ibt_connect.connect_message_socket(),
        )
    else:
        print("❌ DEBUG: Login failed")

if __name__ == "__main__":
    try:
        asyncio.run(debug_websocket())
    except KeyboardInterrupt:
        print(f"\n🛑 DEBUG: Stopped by user. Received {message_count} messages total.")
        strategy_running = False
    except Exception as e:
        print(f"\n❌ DEBUG: Error: {e}")
        strategy_running = False

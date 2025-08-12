import asyncio
import json
import pyotp
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
API_URL = config.get("api_url", "")
API_KEY = config.get("api_key", "")
X_API_KEY = config.get("x_api_key", "")
USER_ID = config.get("user_id", "")
PASSWORD = config.get("password", "")
TOTP_SECRET = "AAWGU42WCQKCG7LY"  # Use the provided TOTP secret

async def main():
    print("Testing B2C API connection...")
    print(f"API URL: {API_URL}")
    print(f"API Key: {API_KEY}")
    print(f"User ID: {USER_ID}")
    
    # Generate TOTP
    totp = pyotp.TOTP(TOTP_SECRET).now()
    print(f"Generated TOTP: {totp}")
    
    # Initialize the IBTConnect client
    ibt_connect = IBTConnect(params={
        "baseurl": API_URL,
        "api_key": API_KEY,
        "x-api-key": X_API_KEY,
        "debug": True
    })
    
    # Login to the B2C API
    print("Logging in to the B2C API...")
    login_params = {
        "user_id": USER_ID,
        "login_type": "PASSWORD",
        "password": PASSWORD,
        "second_auth_type": "TOTP",
        "second_auth": totp,
        "api_key": API_KEY,
        "source": "WEBAPI"
    }
    
    logon_response = ibt_connect.login(params=login_params)
    print("Login response:", json.dumps(logon_response, indent=2))
    
    if logon_response.get("status") == "success":
        print("Login successful")
        
        # Get balance
        print("Fetching balance...")
        balance_response = ibt_connect.balance()
        print("Balance response:", json.dumps(balance_response, indent=2))
        
        # Get order book
        print("Fetching order book...")
        order_book_response = ibt_connect.get_order_book({})
        print("Order book response:", json.dumps(order_book_response, indent=2))
        
        # Get trade book
        print("Fetching trade book...")
        trade_book_response = ibt_connect.get_trade_book({})
        print("Trade book response:", json.dumps(trade_book_response, indent=2))
        
        # Get positions
        print("Fetching positions...")
        positions_response = ibt_connect.get_positions({"type": "all"})
        print("Positions response:", json.dumps(positions_response, indent=2))
        
        # Get holdings
        print("Fetching holdings...")
        holdings_response = ibt_connect.get_holdings()
        print("Holdings response:", json.dumps(holdings_response, indent=2))
        
        # Logout
        print("Logging out...")
        logout_response = ibt_connect.logout()
        print("Logout response:", json.dumps(logout_response, indent=2))
    else:
        print("Login failed")
    
    print("Test completed")

if __name__ == "__main__":
    asyncio.run(main())

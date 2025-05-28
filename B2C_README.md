# B2C Trading Strategy

This project implements a trading strategy using the B2C API SDK. It fetches market data, subscribes to real-time price feeds, and executes trades based on a specific strategy.

## Setup

1. Install the dependencies by running the `install_dependencies.bat` file.
2. Configure the API credentials in the `b2c_config.json` file:
   ```json
   {
       "api_url": "Your API URL",
       "api_key": "Your API Key",
       "x_api_key": "Your X-API Key",
       "user_id": "Your User ID",
       "password": "Your Password",
       "totp_secret": "Your TOTP Secret Key",
       "client_id": "Your Client ID"
   }
   ```
3. Run the strategy by executing the `run_b2c_strategy.bat` file.

## How It Works

The script performs the following steps:

1. Loads the configuration from the `b2c_config.json` file.
2. Logs in to the B2C API using the provided credentials.
3. Fetches market data from NSE:
   - Bhavcopy data
   - NSE DPR data
   - NSE band data
4. Merges the data to identify stocks with a band of 20.
5. Subscribes to real-time price feeds for the selected stocks.
6. Executes trades based on the following strategy:
   - Buy when the current price is higher than the highest price in the bhavcopy data and the percent change is less than 15%.
   - Sell when the current price falls below the stop loss (98% of the high price).

## Files

- `b2c_strategy.py`: The main script that implements the trading strategy.
- `b2c_config.json`: Configuration file for API credentials.
- `b2c_requirements.txt`: List of Python dependencies.
- `install_dependencies.bat`: Batch file to install the dependencies.
- `run_b2c_strategy.bat`: Batch file to run the trading strategy.

## Requirements

- Python 3.6 or higher
- pandas
- requests
- pyotp
- B2C API SDK (included in the b2c-api-python folder)

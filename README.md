# B2C Trading Strategy - Algorithmic Trading System

A comprehensive algorithmic trading system built with Python that implements a momentum breakout strategy using B2C API for real-time market data and trade execution.

## 🚀 Features

### Core Trading Strategy
- **Momentum Breakout Strategy**: Buys stocks when they break above their 5-day high
- **Risk Management**: 2% trailing stop loss to protect capital
- **Real-time Monitoring**: Live WebSocket feeds for 1636+ stocks
- **Automated Execution**: Fully automated buy/sell signal generation

### Dashboard & Monitoring
- **Live Dashboard**: Real-time web interface for monitoring positions
- **Performance Analytics**: Detailed P&L tracking and statistics
- **Position Management**: View current positions with live price updates
- **Trade History**: Complete record of all executed trades
- **Export Functionality**: CSV export of signals and positions

### Technical Features
- **WebSocket Integration**: Real-time market data feeds
- **Database Storage**: SQLite for persistent data storage
- **RESTful API**: Flask-based API for dashboard communication
- **Responsive UI**: Bootstrap-based responsive web interface
- **Error Handling**: Robust error handling and logging

## 📋 Prerequisites

- Python 3.7+
- B2C Trading Account with API access
- TOTP authenticator app (for 2FA)

## 🛠️ Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/RohitIndira/Algo-Test.git
   cd Algo-Test
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure credentials**
   ```bash
   cp b2c_config_template.json b2c_config.json
   ```
   Edit `b2c_config.json` with your B2C credentials:
   ```json
   {
       "user_id": "YOUR_USER_ID",
       "password": "YOUR_PASSWORD",
       "client_id": "YOUR_CLIENT_ID",
       "second_auth_type": "TOTP",
       "second_auth": "YOUR_TOTP_CODE",
       "order_quantity": 1,
       "stop_loss_percentage": 0.98,
       "buy_price_multiplier": 1.05,
       "sell_price_multiplier": 0.95,
       "max_percent_change": 15,
       "auto_square_off_time": "15:20:00"
   }
   ```

## 🚀 Usage

### Start the Dashboard
```bash
python app.py
```
Access the dashboard at: `http://localhost:5000/dashboard`

### Run the Trading Strategy
```bash
python b2c_strategy_websocket.py
```

### Alternative: Start via Dashboard
1. Open the dashboard
2. Click "Start Strategy" button
3. Monitor real-time performance

## 📊 Strategy Logic

### Buy Conditions
```python
if (current_price > five_day_high) and (position == 0) and (daily_change < 15%):
    # Generate BUY signal
    # Set stop loss at 98% of day high
```

### Sell Conditions
```python
if (current_price < stop_loss) and (position == 1):
    # Generate SELL signal
    # Close position
```

### Risk Management
- **Stop Loss**: 2% trailing stop loss (98% of day high)
- **Position Sizing**: Configurable quantity per trade
- **Daily Limit**: Maximum 15% daily change filter
- **Auto Square-off**: Configurable time-based exit

## 📁 Project Structure

```
trading-strategy-poc/
├── app.py                          # Flask web application
├── b2c_strategy_websocket.py       # Main trading strategy
├── b2c_config_template.json        # Configuration template
├── requirements.txt                # Python dependencies
├── README.md                       # Project documentation
├── templates/                      # HTML templates
│   ├── index.html                  # Configuration page
│   └── dashboard.html              # Main dashboard
├── static/                         # Static assets
│   ├── dashboard.js                # Dashboard JavaScript
│   └── exports/                    # CSV export files
├── b2c-api-python (1)/            # B2C API library
└── trading_strategy.db             # SQLite database
```

## 🔧 Configuration Options

| Parameter | Description | Default |
|-----------|-------------|---------|
| `order_quantity` | Number of shares per trade | 1 |
| `stop_loss_percentage` | Stop loss as % of day high | 0.98 (2% stop) |
| `buy_price_multiplier` | Buy price multiplier | 1.05 |
| `sell_price_multiplier` | Sell price multiplier | 0.95 |
| `max_percent_change` | Max daily change filter | 15% |
| `auto_square_off_time` | Auto exit time | 15:20:00 |

## 📈 Dashboard Features

### Real-time Statistics
- **Active Positions**: Current open positions count
- **Total Orders**: Completed trades count
- **Realized P&L**: Profit/Loss from closed trades
- **Unrealized P&L**: Current floating P&L

### Position Monitoring
- **Current Price**: Live market price
- **Entry Price**: Purchase price
- **High Price**: 5-day breakout level
- **Stop Loss**: Current exit trigger
- **% Change**: Live percentage change
- **Status**: Position status

### Performance Analytics
- **Win Rate**: Percentage of profitable trades
- **Average P&L**: Average profit per trade
- **Max Profit/Loss**: Best and worst single trades
- **Trade History**: Complete transaction log

## 🔒 Security Features

- **Credential Protection**: Sensitive data excluded from git
- **Configuration Templates**: Safe credential management
- **Error Handling**: Robust error management
- **Logging**: Comprehensive activity logging

## 📊 Data Sources

- **Market Data**: B2C WebSocket feeds
- **Historical Data**: NSE BhavCopy archives
- **Price Discovery**: Real-time tick data
- **Volume Analysis**: Live trading volumes

## 🧪 Testing & Validation

### Test Scripts
- `test_credentials.py` - Validate B2C API credentials
- `test_websocket_*.py` - WebSocket connection tests
- `debug_*.py` - Debugging utilities
- `verify_*.py` - Data validation scripts

### Simulation Mode
The system runs in simulation mode by default:
- Generates signals without actual trades
- Safe for testing and validation
- Full performance tracking
- Risk-free strategy evaluation

## 📝 Logging & Exports

### Export Features
- **CSV Export**: Signals and positions data
- **Performance Reports**: Detailed analytics
- **Trade History**: Complete transaction logs
- **Real-time Logs**: Live strategy activity

### Log Files
- Strategy execution logs
- Error and exception tracking
- Performance metrics
- WebSocket connection status

## ⚠️ Risk Disclaimer

This software is for educational and research purposes only. Trading involves substantial risk of loss and is not suitable for all investors. Past performance does not guarantee future results. Use at your own risk.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
1. Check the documentation
2. Review test scripts for examples
3. Open an issue on GitHub
4. Ensure credentials are properly configured

## 🔄 Updates & Maintenance

- Regular dependency updates
- Performance optimizations
- New feature additions
- Bug fixes and improvements

---

**Happy Trading! 📈**

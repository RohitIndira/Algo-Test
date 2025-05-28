import os
import sys
import json
import sqlite3
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime

# Add the b2c-api-python (1) directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
b2c_api_path = os.path.join(current_dir, 'b2c-api-python (1)')
sys.path.append(b2c_api_path)

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)  # Enable CORS for all routes

# Create static directory if it doesn't exist
os.makedirs('static', exist_ok=True)

# Store the process ID of the running strategy
strategy_process = None

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
    print("Database initialized successfully")

# Load configuration from JSON file
def load_config():
    try:
        with open('b2c_config.json', 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return {}

# Function to get all signals
def get_signals(limit=50):
    try:
        conn = sqlite3.connect('trading_strategy.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT token, symbol, signal_type, price, high_price, stop_loss, percent_change, timestamp FROM signals ORDER BY timestamp DESC LIMIT ?', (limit,))
        signals = cursor.fetchall()
        
        conn.close()
        
        return signals
    except Exception as e:
        print(f"Error getting signals: {e}")
        return []

# Function to get all open positions
def get_open_positions():
    try:
        conn = sqlite3.connect('trading_strategy.db')
        cursor = conn.cursor()
        
        # Check if the stop_loss column exists
        cursor.execute("PRAGMA table_info(positions)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'stop_loss' in columns:
            cursor.execute('SELECT token, symbol, entry_price, stop_loss, entry_time FROM positions WHERE status = "OPEN"')
        else:
            # If stop_loss column doesn't exist, use a default value
            cursor.execute('SELECT token, symbol, entry_price, 0, entry_time FROM positions WHERE status = "OPEN"')
        
        positions = cursor.fetchall()
        
        conn.close()
        
        return positions
    except Exception as e:
        print(f"Error getting open positions: {e}")
        return []

# Function to get all closed positions
def get_closed_positions(limit=50):
    try:
        conn = sqlite3.connect('trading_strategy.db')
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT token, symbol, entry_price, exit_price, entry_time, exit_time, pnl, percent_gain 
        FROM positions 
        WHERE status = 'CLOSED' 
        ORDER BY exit_time DESC 
        LIMIT ?
        ''', (limit,))
        positions = cursor.fetchall()
        
        conn.close()
        
        return positions
    except Exception as e:
        print(f"Error getting closed positions: {e}")
        return []

# Function to get performance statistics
def get_performance_stats():
    try:
        conn = sqlite3.connect('trading_strategy.db')
        cursor = conn.cursor()
        
        # Total trades
        cursor.execute('SELECT COUNT(*) FROM positions WHERE status = "CLOSED"')
        total_trades = cursor.fetchone()[0]
        
        # Winning trades
        cursor.execute('SELECT COUNT(*) FROM positions WHERE status = "CLOSED" AND pnl > 0')
        winning_trades = cursor.fetchone()[0]
        
        # Losing trades
        cursor.execute('SELECT COUNT(*) FROM positions WHERE status = "CLOSED" AND pnl < 0')
        losing_trades = cursor.fetchone()[0]
        
        # Win rate
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # Total P&L
        cursor.execute('SELECT SUM(pnl) FROM positions WHERE status = "CLOSED"')
        total_pnl = cursor.fetchone()[0] or 0
        
        # Average P&L per trade
        avg_pnl = total_pnl / total_trades if total_trades > 0 else 0
        
        # Max profit
        cursor.execute('SELECT MAX(pnl) FROM positions WHERE status = "CLOSED"')
        max_profit = cursor.fetchone()[0] or 0
        
        # Max loss
        cursor.execute('SELECT MIN(pnl) FROM positions WHERE status = "CLOSED"')
        max_loss = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl,
            'max_profit': max_profit,
            'max_loss': max_loss
        }
    except Exception as e:
        print(f"Error getting performance stats: {e}")
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'total_pnl': 0,
            'avg_pnl': 0,
            'max_profit': 0,
            'max_loss': 0
        }

@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        print(f"Error rendering index.html: {e}")
        return f"Error: {str(e)}", 500

@app.route('/dashboard')
def dashboard():
    try:
        return render_template('dashboard.html')
    except Exception as e:
        print(f"Error rendering dashboard.html: {e}")
        return f"Error: {str(e)}", 500

@app.route('/api/config', methods=['GET', 'POST'])
def config():
    if request.method == 'POST':
        try:
            config_data = request.json
            with open('b2c_config.json', 'w') as f:
                json.dump(config_data, f, indent=4)
            return jsonify({"status": "success", "message": "Configuration saved successfully"})
        except Exception as e:
            print(f"Error saving configuration: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
    else:
        try:
            config = load_config()
            return jsonify(config)
        except Exception as e:
            print(f"Error loading configuration: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/validate', methods=['POST'])
def validate():
    # This would normally validate the credentials with the B2C API
    # For now, just return success
    return jsonify({"status": "success", "message": "Credentials validated successfully"})

@app.route('/api/signals')
def signals():
    try:
        signals_data = get_signals()
        signals_list = []
        for signal in signals_data:
            signals_list.append({
                "token": signal[0],
                "symbol": signal[1],
                "signal_type": signal[2],
                "price": signal[3],
                "high_price": signal[4],
                "stop_loss": signal[5],
                "percent_change": signal[6],
                "timestamp": signal[7]
            })
        return jsonify({"signals": signals_list})
    except Exception as e:
        print(f"Error getting signals: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/positions')
def positions():
    try:
        conn = sqlite3.connect('trading_strategy.db')
        cursor = conn.cursor()
        
        # Get open positions with 5-day high from tokens table
        cursor.execute('''
        SELECT p.token, p.symbol, p.entry_price, p.stop_loss, p.entry_time, t.high_price
        FROM positions p
        LEFT JOIN tokens t ON p.token = t.token
        WHERE p.status = "OPEN"
        ''')
        open_positions = cursor.fetchall()
        
        conn.close()
        
        positions_list = []
        for position in open_positions:
            positions_list.append({
                "token": position[0],
                "symbol": position[1],
                "entry_price": position[2],
                "stop_loss": position[3],
                "entry_time": position[4],
                "five_day_high": position[5] or position[2]  # Use 5-day high or entry price as fallback
            })
        return jsonify({"positions": positions_list})
    except Exception as e:
        print(f"Error getting positions: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/positions_realtime')
def positions_realtime():
    try:
        conn = sqlite3.connect('trading_strategy.db')
        cursor = conn.cursor()
        
        # Get all open positions with real-time PnL and percentage data
        cursor.execute('''
        SELECT token, symbol, entry_price, pnl, percent_gain 
        FROM positions 
        WHERE status = "OPEN"
        ''')
        positions = cursor.fetchall()
        
        conn.close()
        
        positions_list = []
        for position in positions:
            # Calculate current price from entry price and PnL
            entry_price = position[2]
            pnl = position[3] or 0
            current_price = entry_price + pnl
            percent_gain = position[4] or 0
            
            positions_list.append({
                "token": position[0],
                "symbol": position[1],
                "entry_price": entry_price,
                "current_price": current_price,
                "pnl": pnl,
                "percent_gain": percent_gain
            })
        
        return jsonify({"positions": positions_list})
    except Exception as e:
        print(f"Error getting real-time positions: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/trade_history')
def trade_history():
    try:
        closed_positions = get_closed_positions()
        trades_list = []
        for trade in closed_positions:
            trades_list.append({
                "token": trade[0],
                "symbol": trade[1],
                "entry_price": trade[2],
                "exit_price": trade[3],
                "entry_time": trade[4],
                "exit_time": trade[5],
                "pnl": trade[6],
                "percent_gain": trade[7]
            })
        return jsonify({"trades": trades_list})
    except Exception as e:
        print(f"Error getting trade history: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/performance')
def performance():
    try:
        stats = get_performance_stats()
        return jsonify({"stats": stats})
    except Exception as e:
        print(f"Error getting performance stats: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/strategy/status')
def strategy_status():
    global strategy_process
    try:
        # Check if the strategy is running
        is_running = False
        if strategy_process is not None:
            # Check if process is still running using subprocess.poll()
            # poll() returns None if the process is still running
            is_running = strategy_process.poll() is None
        
        # Get statistics
        closed_positions = get_closed_positions()
        realized_pnl = sum([trade[6] for trade in closed_positions]) if closed_positions else 0
        
        # Calculate unrealized PnL from open positions
        conn = sqlite3.connect('trading_strategy.db')
        cursor = conn.cursor()
        cursor.execute('SELECT SUM(pnl) FROM positions WHERE status = "OPEN"')
        unrealized_pnl = cursor.fetchone()[0] or 0
        conn.close()
        
        # Count total completed trades (not individual signals)
        total_completed_trades = len(closed_positions)
        
        return jsonify({
            "running": is_running,
            "positions": len(get_open_positions()),
            "orders": total_completed_trades,  # Fixed: Count completed trades, not signals
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl  # Fixed: Show real unrealized PnL
        })
    except Exception as e:
        print(f"Error getting strategy status: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/strategy/start', methods=['POST'])
def start_strategy():
    global strategy_process
    try:
        # Check if the process is already running
        if strategy_process is not None and strategy_process.poll() is None:
            return jsonify({"status": "success", "message": "Strategy is already running", "pid": strategy_process.pid})
        
        # Start the b2c_strategy.py script
        import subprocess
        strategy_process = subprocess.Popen(['python', 'b2c_strategy.py'], 
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.PIPE,
                                  text=True)
        
        # Return success
        return jsonify({"status": "success", "message": "Strategy started successfully", "pid": strategy_process.pid})
    except Exception as e:
        print(f"Error starting strategy: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/strategy/stop', methods=['POST'])
def stop_strategy():
    global strategy_process
    try:
        # Check if the process is running
        if strategy_process is not None:
            # Use standard subprocess methods to terminate the process
            strategy_process.terminate()
            strategy_process = None
            return jsonify({"status": "success", "message": "Strategy stopped successfully"})
        else:
            return jsonify({"status": "success", "message": "Strategy was not running"})
    except Exception as e:
        print(f"Error stopping strategy: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/logs/export')
def export_logs():
    try:
        # Get all signals from the database
        conn = sqlite3.connect('trading_strategy.db')
        cursor = conn.cursor()
        
        # Get signals
        cursor.execute('SELECT token, symbol, signal_type, price, high_price, stop_loss, percent_change, timestamp FROM signals ORDER BY timestamp DESC')
        signals = cursor.fetchall()
        
        # Get positions
        cursor.execute('SELECT token, symbol, entry_price, exit_price, entry_time, exit_time, stop_loss, status, pnl, percent_gain FROM positions ORDER BY entry_time DESC')
        positions = cursor.fetchall()
        
        conn.close()
        
        # Create a CSV file
        import csv
        from datetime import datetime
        
        # Create directory for exports if it doesn't exist
        os.makedirs('static/exports', exist_ok=True)
        
        # Generate a unique filename based on timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        signals_filename = f'static/exports/signals_{timestamp}.csv'
        positions_filename = f'static/exports/positions_{timestamp}.csv'
        
        # Write signals to CSV
        with open(signals_filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Token', 'Symbol', 'Signal Type', 'Price', 'High Price', 'Stop Loss', 'Percent Change', 'Timestamp'])
            for signal in signals:
                writer.writerow(signal)
        
        # Write positions to CSV
        with open(positions_filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Token', 'Symbol', 'Entry Price', 'Exit Price', 'Entry Time', 'Exit Time', 'Stop Loss', 'Status', 'PnL', 'Percent Gain'])
            for position in positions:
                writer.writerow(position)
        
        # Return success with download links
        return jsonify({
            "status": "success", 
            "message": "Logs exported successfully",
            "signals_file": f"/static/exports/signals_{timestamp}.csv",
            "positions_file": f"/static/exports/positions_{timestamp}.csv"
        })
    except Exception as e:
        print(f"Error exporting logs: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/auth/update', methods=['POST'])
def update_auth():
    # This would normally update the authentication
    # For now, just return success
    return jsonify({"status": "success", "message": "Authentication updated successfully"})

@app.route('/api/test/add_signals', methods=['POST'])
def add_test_signals():
    try:
        data = request.json
        signals = data.get('signals', [])
        
        conn = sqlite3.connect('trading_strategy.db')
        cursor = conn.cursor()
        
        for signal in signals:
            # Insert token into tokens table if it doesn't exist
            cursor.execute('''
            INSERT OR IGNORE INTO tokens (token, symbol, series, name, isin, high_price)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                signal['token'],
                signal['symbol'],
                'EQ',
                f"{signal['symbol']} Ltd.",
                f"INE{signal['token']}01018",
                signal['high_price']
            ))
            
            # Insert signal into signals table
            cursor.execute('''
            INSERT INTO signals (token, symbol, signal_type, price, high_price, stop_loss, percent_change)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                signal['token'],
                signal['symbol'],
                signal['signal_type'],
                signal['price'],
                signal['high_price'],
                signal['stop_loss'],
                signal['percent_change']
            ))
        
        conn.commit()
        conn.close()
        
        return jsonify({"status": "success", "message": "Test signals added successfully"})
    except Exception as e:
        print(f"Error adding test signals: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

@app.errorhandler(404)
def page_not_found(e):
    return jsonify({"status": "error", "message": "Page not found"}), 404

@app.errorhandler(500)
def internal_server_error(e):
    return jsonify({"status": "error", "message": "Internal server error"}), 500

if __name__ == '__main__':
    init_db()
    print("Starting Flask server on http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)

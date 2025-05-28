import sqlite3
import os

def clean_database():
    """
    Clean the trading_strategy.db database by completely removing it and recreating it.
    This ensures the schema is correct and all test data is removed.
    """
    try:
        # Check if database file exists
        if os.path.exists('trading_strategy.db'):
            # Remove the database file
            os.remove('trading_strategy.db')
            print("Removed existing database file.")
        
        # Create a new database with the correct schema
        conn = sqlite3.connect('trading_strategy.db')
        cursor = conn.cursor()
        
        # Create tokens table
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
        
        # Create signals table
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
        
        # Create positions table
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
        
        # Commit changes and close connection
        conn.commit()
        conn.close()
        
        print("Database recreated with correct schema.")
    except Exception as e:
        print(f"Error recreating database: {e}")

if __name__ == "__main__":
    print("Recreating trading strategy database...")
    clean_database()
    print("Done.")

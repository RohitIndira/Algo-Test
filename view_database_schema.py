import sqlite3
import pandas as pd

def view_database_schema():
    """
    Display the complete schema of the trading_strategy.db database
    """
    try:
        conn = sqlite3.connect('trading_strategy.db')
        cursor = conn.cursor()
        
        print("=" * 80)
        print("🗄️  TRADING STRATEGY DATABASE SCHEMA")
        print("=" * 80)
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"\n📊 Total Tables: {len(tables)}")
        print("-" * 50)
        
        for table in tables:
            table_name = table[0]
            print(f"\n🔹 TABLE: {table_name.upper()}")
            print("-" * 30)
            
            # Get table schema
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            print("COLUMNS:")
            for col in columns:
                col_id, col_name, col_type, not_null, default_val, primary_key = col
                pk_indicator = " (PRIMARY KEY)" if primary_key else ""
                null_indicator = " NOT NULL" if not_null else ""
                default_indicator = f" DEFAULT {default_val}" if default_val else ""
                
                print(f"  • {col_name:<15} {col_type:<10}{pk_indicator}{null_indicator}{default_indicator}")
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            row_count = cursor.fetchone()[0]
            print(f"\nROW COUNT: {row_count:,} records")
            
            # Show sample data (first 3 rows)
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
            sample_data = cursor.fetchall()
            
            if sample_data:
                print("\nSAMPLE DATA (First 3 rows):")
                column_names = [description[0] for description in cursor.description]
                df = pd.DataFrame(sample_data, columns=column_names)
                print(df.to_string(index=False, max_cols=10))
            
            print("\n" + "=" * 50)
        
        # Show foreign key relationships
        print("\n🔗 FOREIGN KEY RELATIONSHIPS:")
        print("-" * 40)
        
        for table in tables:
            table_name = table[0]
            cursor.execute(f"PRAGMA foreign_key_list({table_name})")
            foreign_keys = cursor.fetchall()
            
            if foreign_keys:
                print(f"\n{table_name.upper()}:")
                for fk in foreign_keys:
                    print(f"  • {fk[3]} → {fk[2]}.{fk[4]}")
        
        # Show indexes
        print("\n📇 INDEXES:")
        print("-" * 20)
        cursor.execute("SELECT name, tbl_name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'")
        indexes = cursor.fetchall()
        
        if indexes:
            for index in indexes:
                print(f"  • {index[0]} on table {index[1]}")
        else:
            print("  No custom indexes found")
        
        conn.close()
        
        print("\n" + "=" * 80)
        print("✅ Database schema analysis complete!")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ Error viewing database schema: {e}")

def view_table_details(table_name):
    """
    View detailed information about a specific table
    """
    try:
        conn = sqlite3.connect('trading_strategy.db')
        cursor = conn.cursor()
        
        print(f"\n🔍 DETAILED VIEW: {table_name.upper()}")
        print("=" * 50)
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        if not cursor.fetchone():
            print(f"❌ Table '{table_name}' does not exist!")
            return
        
        # Get all data
        cursor.execute(f"SELECT * FROM {table_name}")
        all_data = cursor.fetchall()
        column_names = [description[0] for description in cursor.description]
        
        if all_data:
            df = pd.DataFrame(all_data, columns=column_names)
            print(f"📊 Total Records: {len(df):,}")
            print("\nFull Data:")
            print(df.to_string(index=False))
        else:
            print("📭 No data found in this table")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error viewing table details: {e}")

if __name__ == "__main__":
    # View complete database schema
    view_database_schema()
    
    # Uncomment below to view specific table details
    # print("\n" + "="*80)
    # view_table_details("positions")  # View positions table in detail
    # view_table_details("signals")    # View signals table in detail
    # view_table_details("tokens")     # View tokens table in detail

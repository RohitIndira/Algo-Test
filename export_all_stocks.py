import pandas as pd
import requests
import zipfile
import gzip
from io import StringIO, BytesIO
from datetime import datetime, timedelta

def export_all_stocks():
    print("📊 EXPORTING ALL 1634 STOCKS IN 20% PRICE BAND")
    print("=" * 60)
    
    # EXACT ORIGINAL DATA FETCHING LOGIC
    print("📊 Step 1: Fetching historical high prices...")
    bhavcopy = pd.DataFrame()
    for i in range(6):
        zip_url = f'https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{datetime.strftime(datetime.now().date() - timedelta(i),"%Y%m%d")}_F_0000.csv.zip'
        response = requests.get(zip_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0'})
        if response.status_code == 200:
            zip_content = BytesIO(response.content)
            with zipfile.ZipFile(zip_content, 'r') as zip_ref:
                csv_filename = zip_ref.namelist()[0]
                with zip_ref.open(csv_filename) as file:
                    daily_data = pd.read_csv(file)[['TradDt', 'TckrSymb', 'HghPric']]
                    print(f"   📅 {datetime.strftime(datetime.now().date() - timedelta(i),'%Y-%m-%d')}: {len(daily_data)} records")
                    bhavcopy = pd.concat([daily_data, bhavcopy])
            break  # Just get one day for debugging
    
    if bhavcopy.empty:
        print("❌ No bhavcopy data found!")
        return
    
    bhavcopy = bhavcopy.groupby('TckrSymb', as_index=False).agg({'HghPric': 'max'}).rename({'TckrSymb': 'Symbol', 'HghPric': 'High_Price'}, axis=1)
    print(f"✅ Bhavcopy processed: {len(bhavcopy)} unique symbols")

    print("\n📊 Step 2: Fetching NSE security master...")
    NSE_DPR = pd.DataFrame()
    for i in range(5):
        url = f"https://nsearchives.nseindia.com/content/cm/NSE_CM_security_{datetime.strftime(datetime.now().date() - timedelta(i),'%d%m%Y')}.csv.gz"
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0'})
        if response.status_code == 200:
            with gzip.open(BytesIO(response.content), 'rt') as f:
                NSE_DPR = pd.read_csv(f)[['FinInstrmId', 'TckrSymb', 'SctySrs', 'FinInstrmNm', 'ISIN']].dropna(how='all', axis=1).fillna(" ")
                NSE_DPR.rename(columns={'TckrSymb': 'Symbol', 'SctySrs': 'Series'}, inplace=True)
                print(f"✅ NSE Security Master: {len(NSE_DPR)} records")
                break

    if NSE_DPR.empty:
        print("❌ No NSE security master data found!")
        return

    print("\n📊 Step 3: Fetching 20% price band data...")
    Nse_20 = None
    for i in range(5):
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0'}
        nseBand = requests.get(f"https://nsearchives.nseindia.com/content/equities/sec_list_{datetime.strftime(datetime.now().date() - timedelta(i),'%d%m%Y')}.csv", headers=headers)
        if nseBand.status_code == 200:
            print(f"   📅 Found price band data for: {datetime.strftime(datetime.now().date() - timedelta(i),'%Y-%m-%d')}")
            
            # Parse the CSV content
            raw_data = pd.read_csv(StringIO(nseBand.text), sep=',', skiprows=1, header=None)
            
            # Rename columns
            Nse_20 = raw_data[[0, 1, 3]].rename({0: 'Symbol', 1: 'Series', 3: 'Band'}, axis=1)
            
            # Apply filters
            band_filter = Nse_20['Band'].astype(str).isin(['20', 20])
            series_filter = Nse_20['Series'] == "EQ"
            combined_filter = band_filter & series_filter
            
            Nse_20 = Nse_20.loc[combined_filter].fillna(0)
            print(f"   ✅ After filtering: {len(Nse_20)} records")
            break

    if Nse_20 is None or Nse_20.empty:
        print("❌ No 20% price band data found!")
        return

    print(f"\n📊 Step 4: Merging with NSE security master...")
    Nse_20 = pd.merge(Nse_20, NSE_DPR, on=['Symbol', 'Series'], how='left')

    print(f"\n📊 Step 5: Merging with historical high prices...")
    Nse_20 = pd.merge(Nse_20, bhavcopy, on=['Symbol'], how='left')

    # Add position tracking columns
    Nse_20['Position'] = 0
    Nse_20["StopLoss"] = 0
    
    # Remove records without FinInstrmId and set index
    Nse_20 = Nse_20.dropna(subset=['FinInstrmId'])
    
    print(f"\n📊 Final dataset: {len(Nse_20)} stocks")

    # Prepare export data
    export_data = Nse_20.copy()
    export_data = export_data.reset_index(drop=True)
    
    # Select and rename columns for export
    export_columns = {
        'FinInstrmId': 'Token_ID',
        'Symbol': 'Symbol', 
        'Series': 'Series',
        'Band': 'Price_Band',
        'FinInstrmNm': 'Company_Name',
        'ISIN': 'ISIN',
        'High_Price': 'High_Price_Rs'
    }
    
    # Keep only available columns
    available_export_cols = {k: v for k, v in export_columns.items() if k in export_data.columns}
    export_data = export_data[list(available_export_cols.keys())].rename(columns=available_export_cols)
    
    # Sort by symbol for easy reading
    export_data = export_data.sort_values('Symbol')
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'all_1634_stocks_{timestamp}.csv'
    
    # Export to CSV
    export_data.to_csv(filename, index=False)
    print(f"\n✅ EXPORTED TO: {filename}")
    print(f"📊 Total stocks exported: {len(export_data)}")
    
    # Show summary statistics
    print(f"\n📊 SUMMARY STATISTICS:")
    print(f"=" * 60)
    print(f"📊 Total stocks: {len(export_data)}")
    print(f"📊 Stocks with price data: {export_data['High_Price_Rs'].notna().sum()}")
    print(f"📊 Stocks without price data: {export_data['High_Price_Rs'].isna().sum()}")
    print(f"📊 Price range: ₹{export_data['High_Price_Rs'].min():.2f} - ₹{export_data['High_Price_Rs'].max():.2f}")
    print(f"📊 Average price: ₹{export_data['High_Price_Rs'].mean():.2f}")
    print(f"📊 Median price: ₹{export_data['High_Price_Rs'].median():.2f}")
    
    # Show first 20 and last 20 stocks
    print(f"\n🔍 FIRST 20 STOCKS (A-Z):")
    print("=" * 80)
    print(f"{'#':<3} {'Symbol':<15} {'Company Name':<40} {'Price (₹)':<12}")
    print("-" * 80)
    for i, (_, row) in enumerate(export_data.head(20).iterrows(), 1):
        symbol = row.get('Symbol', 'N/A')
        name = str(row.get('Company_Name', 'N/A'))[:38]
        price = row.get('High_Price_Rs', 0)
        print(f"{i:<3} {symbol:<15} {name:<40} ₹{price:<11.2f}")
    
    print(f"\n🔍 LAST 20 STOCKS (A-Z):")
    print("=" * 80)
    print(f"{'#':<3} {'Symbol':<15} {'Company Name':<40} {'Price (₹)':<12}")
    print("-" * 80)
    start_num = len(export_data) - 19
    for i, (_, row) in enumerate(export_data.tail(20).iterrows(), start_num):
        symbol = row.get('Symbol', 'N/A')
        name = str(row.get('Company_Name', 'N/A'))[:38]
        price = row.get('High_Price_Rs', 0)
        print(f"{i:<3} {symbol:<15} {name:<40} ₹{price:<11.2f}")
    
    # Show top 10 highest priced stocks
    print(f"\n💰 TOP 10 HIGHEST PRICED STOCKS:")
    print("=" * 80)
    print(f"{'#':<3} {'Symbol':<15} {'Company Name':<40} {'Price (₹)':<12}")
    print("-" * 80)
    top_10 = export_data.nlargest(10, 'High_Price_Rs')
    for i, (_, row) in enumerate(top_10.iterrows(), 1):
        symbol = row.get('Symbol', 'N/A')
        name = str(row.get('Company_Name', 'N/A'))[:38]
        price = row.get('High_Price_Rs', 0)
        print(f"{i:<3} {symbol:<15} {name:<40} ₹{price:<11.2f}")
    
    print(f"\n✅ Complete list saved to: {filename}")
    print(f"📊 You can open this file in Excel to verify all 1634 stocks")

if __name__ == "__main__":
    export_all_stocks()

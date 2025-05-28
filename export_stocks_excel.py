import pandas as pd
import requests
import zipfile
import gzip
from io import StringIO, BytesIO
from datetime import datetime, timedelta

def export_stocks_to_excel():
    print("📊 EXPORTING ALL 1634 STOCKS TO EXCEL FORMAT")
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
    
    # Add row numbers for easy reference
    export_data.insert(0, 'Sr_No', range(1, len(export_data) + 1))
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'All_1634_Stocks_{timestamp}.xlsx'
    
    # Create Excel writer with formatting
    try:
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # Write main data
            export_data.to_excel(writer, sheet_name='All_1634_Stocks', index=False)
            
            # Get the workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets['All_1634_Stocks']
            
            # Format headers
            from openpyxl.styles import Font, PatternFill, Alignment
            
            # Header formatting
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            
            for cell in worksheet[1]:
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center")
            
            # Auto-adjust column widths
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)  # Cap at 50 characters
                worksheet.column_dimensions[column_letter].width = adjusted_width
            
            # Add summary sheet
            summary_data = {
                'Metric': [
                    'Total Stocks',
                    'Stocks with Price Data',
                    'Stocks without Price Data',
                    'Minimum Price (₹)',
                    'Maximum Price (₹)',
                    'Average Price (₹)',
                    'Median Price (₹)',
                    'Date Generated'
                ],
                'Value': [
                    len(export_data),
                    export_data['High_Price_Rs'].notna().sum(),
                    export_data['High_Price_Rs'].isna().sum(),
                    f"₹{export_data['High_Price_Rs'].min():.2f}",
                    f"₹{export_data['High_Price_Rs'].max():.2f}",
                    f"₹{export_data['High_Price_Rs'].mean():.2f}",
                    f"₹{export_data['High_Price_Rs'].median():.2f}",
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ]
            }
            
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Format summary sheet
            summary_worksheet = writer.sheets['Summary']
            for cell in summary_worksheet[1]:
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center")
            
            # Auto-adjust summary column widths
            for column in summary_worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = max_length + 2
                summary_worksheet.column_dimensions[column_letter].width = adjusted_width
        
        print(f"\n✅ EXCEL FILE CREATED: {filename}")
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
        
        print(f"\n✅ Excel file created with:")
        print(f"   📋 Sheet 1: 'All_1634_Stocks' - Complete stock list")
        print(f"   📋 Sheet 2: 'Summary' - Statistics and overview")
        print(f"   🎨 Formatted headers and auto-sized columns")
        print(f"   📊 Serial numbers for easy reference")
        
        print(f"\n📂 File location: {filename}")
        print(f"💡 Double-click the file to open in Excel")
        
    except ImportError:
        print("❌ openpyxl not installed. Installing...")
        import subprocess
        subprocess.check_call(['pip', 'install', 'openpyxl'])
        print("✅ openpyxl installed. Please run the script again.")
        
    except Exception as e:
        print(f"❌ Error creating Excel file: {e}")
        print("📄 Falling back to CSV format...")
        
        # Fallback to CSV
        csv_filename = f'All_1634_Stocks_{timestamp}.csv'
        export_data.to_csv(csv_filename, index=False)
        print(f"✅ CSV file created: {csv_filename}")

if __name__ == "__main__":
    export_stocks_to_excel()

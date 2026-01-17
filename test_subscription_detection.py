"""
Test script to validate subscription data detection accuracy.
Tests the core parsing logic of pay_1768488210080.py
"""
import json
from datetime import datetime, timedelta

# Mock API responses for testing
MOCK_RESPONSES = {
    "active_subscription": {
        "success": {
            "page": {
                "id": "payment",
                "spaces": {
                    "content": {
                        "widget_wrappers": [
                            {
                                "template": "PaymentHistoryTableWidget",
                                "widget": {
                                    "data": {
                                        "rows": [
                                            {
                                                "title": ["Premium 3 Month Plan"],
                                                "desc": ["5 Jan, 2026 to 5 Apr, 2026"]
                                            },
                                            {
                                                "title": ["₹899"],
                                                "desc": ["Via Upi"]
                                            }
                                        ]
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }
    },
    "expired_subscription": {
        "success": {
            "page": {
                "id": "payment",
                "spaces": {
                    "content": {
                        "widget_wrappers": [
                            {
                                "template": "PaymentHistoryTableWidget",
                                "widget": {
                                    "data": {
                                        "rows": [
                                            {
                                                "title": ["Super Monthly"],
                                                "desc": ["10 Oct, 2025 to 10 Nov, 2025"]
                                            },
                                            {
                                                "title": ["₹299"],
                                                "desc": ["Via JIO"]
                                            }
                                        ]
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }
    },
    "jio_cricket_offer": {
        "success": {
            "page": {
                "id": "payment",
                "spaces": {
                    "content": {
                        "widget_wrappers": [
                            {
                                "template": "PaymentHistoryTableWidget",
                                "widget": {
                                    "data": {
                                        "rows": [
                                            {
                                                "title": ["Jio Cricket Offer - Mobile4K TV"],
                                                "desc": ["16 Jan, 2026 to 15 Feb, 2026"]
                                            },
                                            {
                                                "title": ["₹0"],
                                                "desc": ["Via JIO"]
                                            }
                                        ]
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }
    },
    "no_history": {
        "success": {
            "page": {
                "id": "payment",
                "spaces": {
                    "content": {
                        "widget_wrappers": []
                    }
                }
            }
        }
    },
    "empty_rows": {
        "success": {
            "page": {
                "id": "payment",
                "spaces": {
                    "content": {
                        "widget_wrappers": [
                            {
                                "template": "PaymentHistoryTableWidget",
                                "widget": {
                                    "data": {
                                        "rows": []
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }
    },
    "missing_desc": {
        "success": {
            "page": {
                "id": "payment",
                "spaces": {
                    "content": {
                        "widget_wrappers": [
                            {
                                "template": "PaymentHistoryTableWidget",
                                "widget": {
                                    "data": {
                                        "rows": [
                                            {
                                                "title": ["Premium Plan"],
                                                "desc": []
                                            },
                                            {
                                                "title": ["₹899"],
                                                "desc": ["Via Upi"]
                                            }
                                        ]
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }
    }
}


def parse_subscription_data(data):
    """
    Extracted and improved parsing logic from pay_1768488210080.py
    Returns: (plan_status, details_str, is_valid)
    """
    plan_status = "NO❌"
    details_str = ""
    is_valid = False
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
                except Exception as e:
                    # If date parsing fails, assume active if it's the top row, but mark as check needed
                    is_active = True 
                    details_str = f"Plan: {plan_name}\nRange: {date_range}\nPayment: {payment_mode}\nPrice: {plan_price}"
                    print(f"    [WARNING] Date parsing failed: {e}")

                if is_active:
                    plan_status = f"{plan_name}✅"
                    is_valid = True
                else:
                    plan_status = "Expired❌"

    except Exception as e:
        print(f"    [ERROR] Parsing error: {e}")
        
    # Fallback: If no history found but page loaded, might be a fresh/free account
    if plan_status == "NO❌":
        if data.get('success', {}).get('page', {}).get('id') == 'payment':
            plan_status = "Free/No History✅"
            is_valid = False  # Don't count free as valid hit

    return plan_status, details_str, is_valid


def test_output_formatting(details_str):
    """
    Test the output formatting logic that could crash in original code.
    Original line 144 could fail if details_str doesn't have enough lines.
    """
    try:
        if details_str:
            lines = details_str.splitlines()
            if len(lines) >= 3:
                exp_line = lines[1].replace('Expiry: ', '')
                pay_line = lines[2]
                return f"Exp: {exp_line} | {pay_line}"
            else:
                return f"Details: {details_str}"
        return "No details"
    except Exception as e:
        return f"ERROR: {e}"


def run_tests():
    """Run all subscription detection tests."""
    print("=" * 60)
    print("   Subscription Data Detection Tests")
    print("=" * 60 + "\n")
    
    test_cases = [
        ("active_subscription", True, "Premium 3 Month Plan"),
        ("expired_subscription", False, "Expired"),
        ("jio_cricket_offer", True, "Jio Cricket Offer"),
        ("no_history", False, "Free/No History"),
        ("empty_rows", False, "Free/No History"),
        ("missing_desc", True, None),  # Should handle gracefully
    ]
    
    passed = 0
    failed = 0
    
    for test_name, expected_valid, expected_plan_keyword in test_cases:
        print(f"Test: {test_name}")
        
        data = MOCK_RESPONSES[test_name]
        plan_status, details_str, is_valid = parse_subscription_data(data)
        
        # Validate result
        valid_match = is_valid == expected_valid
        plan_match = True
        if expected_plan_keyword:
            plan_match = expected_plan_keyword.lower() in plan_status.lower()
        
        # Test output formatting
        output = test_output_formatting(details_str)
        
        if valid_match and plan_match:
            print(f"  ✅ PASSED")
            print(f"     Status: {plan_status}")
            print(f"     Valid: {is_valid}")
            print(f"     Output: {output}")
            passed += 1
        else:
            print(f"  ❌ FAILED")
            print(f"     Expected valid={expected_valid}, got {is_valid}")
            print(f"     Expected keyword='{expected_plan_keyword}' in '{plan_status}'")
            print(f"     Details: {details_str}")
            failed += 1
        
        print()
    
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


def test_cookie_loading():
    """Test the Netscape cookie file loading."""
    print("\n" + "=" * 60)
    print("   Cookie Loading Tests")
    print("=" * 60 + "\n")
    
    def load_cookies_from_netscape_file(cookie_file):
        """Copy of the function from pay_1768488210080.py"""
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
    
    import os
    test_folder = "/workspace/test_cookies"
    if os.path.isdir(test_folder):
        txt_files = [f for f in os.listdir(test_folder) if f.lower().endswith(".txt")][:3]
        
        for filename in txt_files:
            filepath = os.path.join(test_folder, filename)
            cookies = load_cookies_from_netscape_file(filepath)
            
            has_userup = 'userUP' in cookies or 'userup' in cookies.lower() if cookies else False
            # Check case-insensitive
            has_userup = any(k.lower() == 'userup' for k in cookies.keys())
            
            print(f"File: {filename[:50]}...")
            print(f"  Cookies loaded: {len(cookies)}")
            print(f"  Has userUP: {has_userup}")
            
            if has_userup:
                print("  ✅ Cookie file valid")
            else:
                print("  ❌ Missing userUP token")
            print()
    else:
        print("No test cookies folder found.")


def test_date_parsing_edge_cases():
    """Test date parsing with various formats."""
    print("\n" + "=" * 60)
    print("   Date Parsing Edge Cases")
    print("=" * 60 + "\n")
    
    test_dates = [
        ("12 Jan, 2026 to 12 Apr, 2026", "12 Apr, 2026", True),
        ("1 Jan, 2026 to 1 Feb, 2026", "1 Feb, 2026", True),
        ("5 Jan, 2026 to 5 Apr, 2026", "5 Apr, 2026", True),
        ("25 Dec, 2025 to 25 Dec, 2026", "25 Dec, 2026", True),
        ("10 Oct, 2025 to 10 Nov, 2025", "10 Nov, 2025", False),  # Expired
        ("Unknown Dates", None, None),  # Should handle gracefully
    ]
    
    for date_range, expected_end, expected_active in test_dates:
        print(f"Testing: '{date_range}'")
        
        try:
            if " to " in date_range:
                end_date_str = date_range.split(" to ")[1].strip()
                expiry_dt = datetime.strptime(end_date_str, "%d %b, %Y")
                is_active = expiry_dt >= datetime.now()
                
                if expected_end and end_date_str == expected_end:
                    print(f"  ✅ Parsed end date: {end_date_str}")
                else:
                    print(f"  ❌ Parsed: {end_date_str}, expected: {expected_end}")
                
                if expected_active is not None:
                    if is_active == expected_active:
                        print(f"  ✅ Active status: {is_active}")
                    else:
                        print(f"  ❌ Active: {is_active}, expected: {expected_active}")
            else:
                print(f"  ⚠️ No ' to ' separator found - handled gracefully")
        except Exception as e:
            print(f"  ❌ Parse error: {e}")
        
        print()


if __name__ == "__main__":
    success = run_tests()
    test_cookie_loading()
    test_date_parsing_edge_cases()
    
    print("\n" + "=" * 60)
    if success:
        print("   All core tests PASSED!")
    else:
        print("   Some tests FAILED - Review issues above")
    print("=" * 60)

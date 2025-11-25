import csv
import requests
import json
import re
import os
import random
from faker import Faker
from datetime import datetime
import time
import secrets
import string
from constants import (
    LOQATE_API_KEY, URL_EMAIL_BATCH, URL_PHONE_INDIVIDUAL, 
    MAILTM_BASE_URL, URL_PUBLIC_SMS_SOURCE, 
    URL_PUBLIC_SMS_SOURCE_FALLBACK, COUNTRY_PREFIXES
)

# initialize faker
fake = Faker()

def _random_local_part(length: int = 10) -> str:
    """Generate a random local part for the email address."""
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def get_professional_fake_email(retries=3):
    """
    Creates a working disposable email.
    Retries on failure. Falls back to 1secmail if Mail.tm fails completely.
    """
    for attempt in range(retries):
        try:
            # 1. Get Domains
            domains_resp = requests.get(f"{MAILTM_BASE_URL}/domains", timeout=5)
            if domains_resp.status_code != 200:
                time.sleep(1)
                continue
                
            data = domains_resp.json()
            domains = data.get("hydra:member", [])
            if not domains:
                time.sleep(1)
                continue

            domain = domains[0]["domain"]
            local_part = _random_local_part()
            address = f"{local_part}@{domain}"
            password = secrets.token_urlsafe(12)

            # 2. Create Account
            acc_resp = requests.post(
                f"{MAILTM_BASE_URL}/accounts",
                json={"address": address, "password": password},
                timeout=5
            )
            
            if acc_resp.status_code in (200, 201):
                return address
            elif acc_resp.status_code == 429:
                secs = round(random.uniform(2, 5), 2)
                print(f"   [Mail.tm] Rate limited (429). Retrying in {secs}s...")
                time.sleep(secs)
            else:
                # e.g. 422 Unprocessable Entity
                pass

        except Exception as e:
            print(f"   [Mail.tm] Error on attempt {attempt+1}: {e}")
            time.sleep(1)
    
        except Exception:
            print("   [Warning] Failed to generate professional fake email.")
            time.sleep(1)
            pass
    
    print("   [Warning] Mail.tm failed.")
    return None

def extract_numbers_from_text(text):
    """Helper to find international format numbers in raw HTML text."""
    # look for patterns like +123456789 or +1 234 567 89
    # allows for optional spaces between digits
    matches = re.findall(r'\+(\d[\d\s]{7,16})', text)
    cleaned_matches = []
    for m in matches:
        # remove spaces to check against prefixes
        clean_num = "+" + m.replace(" ", "").replace("-", "")
        cleaned_matches.append(clean_num)
    return cleaned_matches

def fetch_real_active_numbers(active=True):
    """
    Scrapes public SMS receiver sites to find ACTUAL, REAL, ACTIVE phone numbers.
    Returns a dict: {'US': ['+1...', ...], 'GB': ['+44...', ...]}
    """
    found_numbers = {code: [] for code in COUNTRY_PREFIXES}
    
    # headers to mimic a real Chrome browser to bypass 403s
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        'Referer': 'https://www.google.com/',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
    }
    
    session = requests.Session()
    session.headers.update(headers)
    
    if active is None:
        sources = [URL_PUBLIC_SMS_SOURCE, URL_PUBLIC_SMS_SOURCE_FALLBACK]
    else:
        sources = [URL_PUBLIC_SMS_SOURCE] if active else [URL_PUBLIC_SMS_SOURCE_FALLBACK]
    
    for url in sources:
        print(f"--- Fetching Numbers from {url} ---")
        try:
            response = session.get(url, timeout=15)
            
            if response.status_code == 200:
                raw_numbers = extract_numbers_from_text(response.text)
                
                # sort prefixes by length (desc) to match +44 before +4
                sorted_prefixes = sorted(COUNTRY_PREFIXES.items(), key=lambda x: len(x[1]), reverse=True)

                count_new = 0
                for full_num in raw_numbers:
                    for code, prefix in sorted_prefixes:
                        if full_num.startswith(prefix):
                            if full_num not in found_numbers[code]:
                                found_numbers[code].append(full_num)
                                count_new += 1 
                
                print(f"   [Success] Found {count_new} numbers from this source.")
            else:
                print(f"   [Warning] Status {response.status_code} from {url}")

        except Exception as e:
            print(f"   [Warning] Error scraping {url}: {e}")

        total_found = sum(len(x) for x in found_numbers.values())
        print(f"   [Total] Collected {total_found} numbers across all countries.")
    return found_numbers

def generate_data(num_standard=2, num_pro=2, phones_per_country=2):
    """
    Generates data:
    - Standard Emails
    - Pro Emails
    - Phones (per country)
    """
    data = {
        "std_emails": [],
        "pro_emails": [],
        "scraped_real_phones_by_country": {code: [] for code in COUNTRY_PREFIXES},
        "fake_phones_by_country": {code: [] for code in COUNTRY_PREFIXES},
        "scraped_inactive_phones_by_country": {code: [] for code in COUNTRY_PREFIXES}
    }
    
    print(f"--- Generating Data: {num_standard} Std Email, {num_pro} Pro Email, {phones_per_country} Phones/Country ---")
    
    # emails
    for _ in range(num_standard):
        data["std_emails"].append(fake.email())

    for _ in range(num_pro):
        pro_email = get_professional_fake_email()
        if pro_email:
            data["pro_emails"].append(pro_email)
        
    # phones per country

    # try to get real numbers cache
    real_numbers_cache = fetch_real_active_numbers()
    inactive_numbers_cache = fetch_real_active_numbers(active=False)

    for code, prefix in COUNTRY_PREFIXES.items():
        # get real numbers available for this country
        real_available = real_numbers_cache.get(code, [])
        inactive_available = inactive_numbers_cache.get(code, [])

        country_list = []
        for i in range(phones_per_country):
            # if we have a real number available, use it
            # this prioritizes "real" testing if available
            if real_available:
                # pop one to use
                real_num = real_available.pop(0)
                data["scraped_real_phones_by_country"][code].append(real_num)
                print(f"   [{code}] Using scraped real active number: {real_num}")
                continue
                
            # fallback to inactive / fake generation
            # if secrets.choice([True, False]):
            if inactive_available: # real but inactive --> not reachable, thus "fake"
                # pop one to use
                inactive_num = inactive_available.pop(0)
                data["scraped_inactive_phones_by_country"][code].append(inactive_num)
                print(f"   [{code}] Using scraped real inactive number: {inactive_num}")
                continue
            else:
                # basic structured fake
                base_num = fake.basic_phone_number().replace("-", "").replace("(", "").replace(")", "").replace(" ", "").replace(".", "")
                if base_num.startswith("0"): 
                    base_num = base_num[1:]
                full_num = f"{prefix}{base_num}"
                print(f"   [{code}] Using structured fake number: {full_num}")
                
            # else:
            #     # random phone number
            #     full_num = fake.phone_number()
            
            country_list.append(full_num)
        
        data["fake_phones_by_country"][code] = country_list
        
    return data

def verify_emails_batch(emails):
    """Verifies a list of emails and returns the results."""
    if not emails:
        return []

    # prepare results list
    results = []
    
    chunk_size = 100
    for i in range(0, len(emails), chunk_size):
        chunk = emails[i:i + chunk_size]
        params = {"Key": LOQATE_API_KEY, "Emails": ",".join(chunk)}
        
        print(f"[Email Batch] Verifying {len(chunk)} emails...")
    
        try:
            response = requests.post(URL_EMAIL_BATCH, data=params)
            response.raise_for_status()
            data = response.json()
            
            if "Items" in data:
                for item in data["Items"]:
                    # specific "clean" dict for our CSV

                    # valid means status starts with "valid", but not if disposable ("Unknown" is treated as invalid)
                    isValid = item.get('Status', '').lower().startswith("valid") and not item.get('IsDisposible', False)
                    record = {
                        "Type": "Email",
                        "Input": item.get('EmailAddress'),
                        "Status": item.get('Status'),
                        "IsValid": "Yes" if isValid else "No",
                        "Account": item.get('Account'),
                        "Domain": item.get('Domain'),
                        "IsDisposable": item.get('IsDisposible'),
                        "IsSystemMailbox": item.get('IsSystemMailbox'),
                        # "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    if record not in results:
                        results.append(record)
                    print(f"   Processed: {record['Input']} -> {record['Status']}")
        except Exception as e:
            print(f"[Email Batch] Error: {e}")
        
    return results

def verify_phone_individual(phone):
    """Verifies a single phone and returns the result."""
    params = {
        "Key": LOQATE_API_KEY,
        "Phone": phone
    }
    
    try:
        response = requests.get(URL_PHONE_INDIVIDUAL, params=params)
        response.raise_for_status()
        data = response.json()
        
        if "Items" in data and len(data["Items"]) > 0:
            item = data["Items"][0]
            record = {
                "Type": "Phone",
                "Input": phone,
                "RequestProcessed": item.get('RequestProcessed'),
                "IsValid": item.get('IsValid'), # "Yes"/"No"
                "NetworkCode": item.get('NetworkCode'),
                "NetworkName": item.get('NetworkName'),
                "NetworkCountry": item.get('NetworkCountry'),
                "NationalFormat": item.get('NationalFormat'),
                "CountryPrefix": item.get('CountryPrefix'),
                "NumberType": item.get('NumberType'),
                # "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            print(f"   Processed: {record['Input']} -> {record['IsValid']}")
            return record
            
    except Exception as e:
        print(f"[Phone] Error verifying {phone}: {e}")
    
    return None

def detect_country(phone_str):
    """Matches a real phone number string to a country code based on prefix."""
    if not phone_str: return None
    # sort prefixes by length desc to match +44 before +4
    sorted_prefixes = sorted(COUNTRY_PREFIXES.items(), key=lambda x: len(x[1]), reverse=True)
    
    for code, prefix in sorted_prefixes:
        if phone_str.startswith(prefix):
            return code
    return "Unknown"

def calculate_metrics_subset(results, real_inputs, fake_inputs, label="Overall"):
    """
    Calculates metrics for a specific subset of data.
    """
    real_set = {str(x).lower().strip() for x in real_inputs if x}
    fake_set = {str(x).lower().strip() for x in fake_inputs if x}
    
    tp, tn, fp, fn = 0, 0, 0, 0
    processed_count = 0

    for row in results:
        val = str(row.get('Input', '')).lower().strip()
        
        # determine ground truth
        if val in real_set:
            actual = "Real"
        elif val in fake_set:
            actual = "Fake"
        else:
            continue # not in this subset
        
        processed_count += 1
        
        # determine prediction
        predicted_valid = False
        valid_str = str(row.get('IsValid', '')).lower()
        if valid_str in ["yes", "true"]:
            predicted_valid = True
        elif not valid_str in ["no", "false", "maybe"]:
            print(f"   [Warning] Unknown IsValid value for {val}: {row.get('IsValid')}")
            continue # skip unknowns
        
        # Confusion matrix
        if actual == "Real":
            if predicted_valid: tp += 1
            else: fn += 1
        else: # actual is fake
            if predicted_valid: fp += 1
            else: tn += 1

    if processed_count == 0:
        return # skip print if empty

    total = tp + tn + fp + fn
    accuracy = (tp + tn) / total if total > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    print(f"\n--- Metrics: {label} ---")
    print(f"Total: {total} | TP: {tp} | TN: {tn} | FP: {fp} | FN: {fn}")
    print(f"Accuracy:  {accuracy:.2%} | Precision: {precision:.2f} | Recall: {recall:.2f} | F1: {f1:.2f}")

def save_list_to_json(data_list, filename):
    """Helper to save a simple list to a JSON file."""
    if not data_list: 
        return
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data_list, f, indent=4)
    print(f"[File] Saved {len(data_list)} items to {filename}")

def save_final_results(results, filename):
    if not results: 
        return

    # save JSON
    filename_base = os.path.splitext(filename)[0]
    json_file = f"{filename_base}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=4)
    print(f"\n[File] Results saved to {json_file}")

    # save CSV
    csv_file = f"{filename_base}.csv"
    
    # collect all possible keys from the results dictionary
    keys = set()
    for item in results:
        keys.update(item.keys())
    
    # organize keys: Type, Input, GroundTruth first, then the rest
    ordered_keys = ['Type', 'Input', 'GroundTruth', 'Status', 'IsValid']
    remaining_keys = [k for k in keys if k not in ordered_keys]
    fieldnames = ordered_keys + sorted(remaining_keys)

    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"[File] Results saved to {csv_file}")

def load_json_file(filepath):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        print(f"[Warning] File not found: {filepath}. Using empty data.")
        return {}
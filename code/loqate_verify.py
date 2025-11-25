import argparse
import os
import sys
from datetime import datetime
from utils import (
    generate_data, 
    verify_emails_batch, 
    verify_phone_individual, 
    save_list_to_json, 
    calculate_metrics_subset, 
    save_final_results, 
    detect_country,
    load_json_file
)
from constants import COUNTRY_PREFIXES, DATA_PATH, OUT_PATH, LOGS_PATH

class DualLogger:
    """
    Writes output to both the console (stdout) and a log file.
    """
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.logfile = open(filename, "a", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.logfile.write(message)

    def flush(self):
        # for compatibility with flush() calls
        self.terminal.flush()
        self.logfile.flush()

def main():
    # setup logging
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = LOGS_PATH / f"loqate_run_{timestamp}.log"
    
    # redirect all print statements to the DualLogger
    sys.stdout = DualLogger(log_filename)

    print(f"--- Starting Verification Run: {timestamp} ---")
    print(f"--- Logs will be saved to: {log_filename} ---")

    parser = argparse.ArgumentParser()
    parser.add_argument("--standard", type=int, default=2, help="Standard emails count")
    parser.add_argument("--pro", type=int, default=2, help="Professional emails count")
    parser.add_argument("--phones_per_country", type=int, default=2, help="Fakes per country")
    parser.add_argument("--generate_new_data", action="store_true", help="Generate new data even if existing data is present")
    args = parser.parse_args()

    if args.generate_new_data:
        print("[Info] Generating new data as per --generate_new_data flag.")
        # generate & save
        gen_data = generate_data(
            num_standard=args.standard, 
            num_pro=args.pro, 
            phones_per_country=args.phones_per_country
        )
        
        save_list_to_json(gen_data["std_emails"], DATA_PATH / "input_standard_emails.json")
        save_list_to_json(gen_data["pro_emails"], DATA_PATH / "input_pro_emails.json")
        save_list_to_json(gen_data["scraped_real_phones_by_country"], DATA_PATH / "input_real_scraped_phones.json")
        save_list_to_json(gen_data["scraped_inactive_phones_by_country"], DATA_PATH / "input_inactive_scraped_phones.json")
        save_list_to_json(gen_data["fake_phones_by_country"], DATA_PATH / "input_fake_phones.json")

    else:
        print("[Info] Loading existing generated data from disk.")
        # load existing
        gen_data = {
            "std_emails": load_json_file(DATA_PATH / "input_standard_emails.json"),
            "pro_emails": load_json_file(DATA_PATH / "input_pro_emails.json"),
            "scraped_real_phones_by_country": load_json_file(DATA_PATH / "input_real_scraped_phones.json"),
            "scraped_inactive_phones_by_country": load_json_file(DATA_PATH / "input_inactive_scraped_phones.json"),
            "fake_phones_by_country": load_json_file(DATA_PATH / "input_fake_phones.json"),
        }
    
    # flatten fake phones list for verification
    active_scraped_phones = [p for sublist in gen_data["scraped_real_phones_by_country"].values() for p in sublist]
    inactive_scraped_phones = [p for sublist in gen_data["scraped_inactive_phones_by_country"].values() for p in sublist]
    all_scraped_phones = active_scraped_phones + inactive_scraped_phones
    all_generated_phones = [p for sublist in gen_data["fake_phones_by_country"].values() for p in sublist]

    # load real data
    real_emails = [e.strip() for e in os.getenv("REAL_EMAILS", "").split(",") if e.strip()]
    real_phones_manual = [p.strip() for p in os.getenv("REAL_PHONES", "").split(",") if p.strip()]
    
    # bucket manual phones
    manual_phones_by_country = {code: [] for code in COUNTRY_PREFIXES}
    for p in real_phones_manual:
        code = detect_country(p)
        if code in manual_phones_by_country: manual_phones_by_country[code].append(p)

    all_emails = gen_data["std_emails"] + gen_data["pro_emails"] + real_emails
    all_phones = all_scraped_phones + all_generated_phones + real_phones_manual
    
    final_results = []
    final_results.extend(verify_emails_batch(all_emails))

    print(f"\n[Phone] Verifying {len(all_phones)} numbers...")
    for p in all_phones:
        res = verify_phone_individual(p)
        if res: final_results.append(res)

    # tag ground truth
    # sets for fast lookup
    total_real_inputs = set([str(x).lower().strip() for x in (real_emails + real_phones_manual + active_scraped_phones)])
    total_fake_inputs = set([str(x).lower().strip() for x in (gen_data["std_emails"] + gen_data["pro_emails"] + all_generated_phones + inactive_scraped_phones)])
    
    for row in final_results:
        val = str(row.get('Input', '')).lower().strip()
        if val in total_real_inputs:
            row['GroundTruth'] = 'Real'
        elif val in total_fake_inputs:
            row['GroundTruth'] = 'Fake'
        else:
            row['GroundTruth'] = 'Unknown'

    # calculate metrics
    # ground truth buckets
    # real = manual real + scraped real
    # fake = generared standard + generated pro + generated phones + scraped fake (inactive) phones
    
    # 1) overall
    total_real = real_emails + real_phones_manual + active_scraped_phones
    total_fake = gen_data["std_emails"] + gen_data["pro_emails"] + all_generated_phones + inactive_scraped_phones
    calculate_metrics_subset(final_results, total_real, total_fake, label="OVERALL")

    # 2) emails
    print("\n--- EMAIL METRICS ---")
    calculate_metrics_subset(final_results, [], gen_data["std_emails"], label="EMAILS (Standard Fakes)")
    calculate_metrics_subset(final_results, [], gen_data["pro_emails"], label="EMAILS (Pro Fakes)")

    # 3) phones overall
    phones_real = real_phones_manual + active_scraped_phones
    phones_fake = all_generated_phones + inactive_scraped_phones
    calculate_metrics_subset(final_results, phones_real, phones_fake, label="PHONES (Global)")
    calculate_metrics_subset(final_results, active_scraped_phones, inactive_scraped_phones, label="PHONES (Scraped Only)")
    calculate_metrics_subset(final_results, active_scraped_phones, [], label="PHONES (Active Scraped Only)")
    calculate_metrics_subset(final_results, [], inactive_scraped_phones, label="PHONES (Inactive Scraped Only)")

    # 4) phones per country
    print("\n--- PHONE METRICS PER COUNTRY ---")
    for code in COUNTRY_PREFIXES:
        # real = manual for this country + scraped for this country
        c_real = manual_phones_by_country.get(code, []) + gen_data["scraped_real_phones_by_country"].get(code, [])
        # fake = generated for this country
        c_fake = gen_data["fake_phones_by_country"].get(code, []) + gen_data["scraped_inactive_phones_by_country"].get(code, [])
        
        if c_real or c_fake:
            lbl = f"Phone: {code} ({len(c_real)} Real, {len(c_fake)} Fake)"
            calculate_metrics_subset(final_results, c_real, c_fake, label=lbl)

    # save results
    if final_results:
        save_final_results(final_results, OUT_PATH)
        print(f"\n[Done] Results saved to {OUT_PATH}")

if __name__ == "__main__":
    main()
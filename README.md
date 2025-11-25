# Loqate Verification Tool Results

## Overview

This tool assesses the performance of the Loqate Email and Phone Validation APIs by testing them against a mixed dataset of real and fake entries.

## Methodology:

- Generation: Creates standard fake data (using the Faker library) and "professional" fakes (real disposable inboxes via Mail.tm).
- Scraping: Fetches real, active phone numbers from public SMS receiver sites to serve as positive controls. Also fetches real but inactive phone numbers from the same website, marked as negative controls (they are not reachable).
- Validation: Runs all data through Loqate's Batch Email and Individual Phone endpoints.
- Scoring: Calculates classification metrics (Accuracy, Precision, Recall, F1) based on the known ground truth.

## Ground Truth Definitions:

- Real (Positive): Scraped active numbers + manual inputs (in .env file).
- Fake (Negative): Randomly generated numbers + scraped inactive numbers + Faker emails + disposable "pro" emails.

## Usage

### Prerequisites

- Ensure you have Python 3.x installed.
- Install the required dependencies:
    - `pip install -r requirements.txt`
- Create a .env file in the root directory with your API key and optional manual test data:

``` bash
    LOQATE_API_KEY=your_api_key_here
    REAL_EMAILS=myrealemail@example.com,another@test.com
    REAL_PHONES=+15550123456,+447700900123
``` 

### Running the Tool

Run the main script from the command line. You can customize the volume of data generated using arguments:

``` bash 
python loqate_verify.py --standard 5 --pro 3 --phones_per_country 2 --generate_new_data
```

### Arguments:

- --standard: Number of standard fake emails (e.g., fake123@random.com) to generate.
- --pro: Number of "professional" fake emails (active inboxes on disposable domains) to generate.
- --phones_per_country: Number of phone numbers to process for each supported country code. This will prioritize scraped real numbers; if none are available, it generates fakes.
- generate_new_data: If set, generates data from scratch (takes some time). Otherwise, it reuses already existing data.

## Results Summary

### Overall Performance
- Sample size: 283
- Real: 36
- Fake: 130
- Accuracy: ~58.30%
- Recall: 97% (Loqate rarely rejects a real contact).
- Precision: 24% (Loqate frequently marks fake data as valid).
- F1: ~38%

### Email Validation

- Standard Fakes: 
    - Sample size: 50 emails
    - 100% Accuracy
    - Loqate perfectly identifies syntax-based fakes (e.g., fake@example.com).
- Disposable Inboxes: 
    - Sample size: 34 emails
    - Accuracy: 0.00%
    - Loqate failed to detect all "professional" fakes (real inboxes created via API, e.g., "honqp4iuk1@comfythings.com") and marks them as valid.
    - None of these emails were flagged as disposable.

### Phone Validation
- Sample size: 195
- Real: 33
- Fake: 162
- Global Accuracy: ~57%
- Recall: ~97%
- Precision: ~28%
- Behavior: The system leans heavily towards "Valid". It rarely rejects real numbers (High Recall) but allows a significant number of randomly generated fake or inactive numbers to pass as valid (Low Precision).
- "Maybe" Status: Observed in ~20 cases. In every instance, this correlated exactly with RequestProcessed: False, indicating a network/lookup failure rather than a data ambiguity.

### Country-Specific Variance

- Performance varied significantly by region.
- However, these metrics heavily depend on the type of fakes. Disposable inboxes and inactive numbers are just generally hard to detect and the number of such types of fakes varies heavily between countries.
- High Accuracy (100%): GB (United Kingdom), JP (Japan).
- Moderate Accuracy (~40-90%): AU, AT, IT, US.
- Low Accuracy (0-10%): FR, RU, SE. (In these regions, generated fakes were consistently marked as "Valid").

## Conclusion

The service looks good on the surface. It is fast and generally reliable. However, it (1) does not detect disposable mail boxes (although explicitly offered), and (2) does not detect inactive (formerly valid) phone numbers. It does not check if an email or an SMS would actually reach the recipient.
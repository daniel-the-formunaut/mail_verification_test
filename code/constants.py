import os
import dotenv
from pathlib import Path

# configurations
PROJECT_ROOT = Path(__file__).parent.parent

DATA_PATH = PROJECT_ROOT / "data"
DATA_PATH.mkdir(parents=True, exist_ok=True)

OUT_PATH = DATA_PATH / "verification_results.json"

LOGS_PATH = PROJECT_ROOT / "logs"
LOGS_PATH.mkdir(parents=True, exist_ok=True)

# load environment variables from .env file
dotenv.load_dotenv(PROJECT_ROOT / ".env")
LOQATE_API_KEY = os.getenv("LOQATE_API_KEY")

# API endpoints
URL_EMAIL_BATCH = "https://api.addressy.com/EmailValidation/Batch/Validate/v1.20/json3.ws"
URL_PHONE_INDIVIDUAL = "https://api.addressy.com/PhoneNumberValidation/Interactive/Validate/v2.20/json3.ws"
MAILTM_BASE_URL = "https://api.mail.tm"
URL_PUBLIC_SMS_SOURCE = "https://receive-smss.com/"  # Source for real, active numbers
URL_PUBLIC_SMS_SOURCE_FALLBACK = "https://receive-smss.com/inactive-numbers/"

# phone verification country prefixes
COUNTRY_PREFIXES = {
    "US": "+1",  # United States
    "GB": "+44", # United Kingdom
    "AU": "+61", # Australia
    "FR": "+33", # France
    "DE": "+49", # Germany
    "IN": "+91", # India
    "JP": "+81", # Japan
    "CN": "+86", # China
    "BR": "+55", # Brazil
    "AT": "+43", # Austria
    "BE": "+32", # Belgium
    "CH": "+41", # Switzerland
    "ES": "+34", # Spain
    "IT": "+39", # Italy
    "NL": "+31", # Netherlands
    "RU": "+7",  # Russia
    "SE": "+46", # Sweden
    "ZA": "+27", # South Africa
    "MX": "+52", # Mexico
}
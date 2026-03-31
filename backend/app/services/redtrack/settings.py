import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))

REDTRACK_API_KEY = os.getenv("REDTRACK_API_KEY")
REDTRACK_REPORT_URL = "https://api.redtrack.io/report"
REDTRACK_CONVERSIONS_URL = "https://api.redtrack.io/conversions"
SAO_PAULO_TZ = ZoneInfo("America/Sao_Paulo")

MAX_RETRIES = 5
INITIAL_BACKOFF = 1
MAX_BACKOFF = 60
RATE_LIMIT_DELAY = 0.5


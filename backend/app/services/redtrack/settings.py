import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))

REDTRACK_API_KEY = os.getenv("REDTRACK_API_KEY")
REDTRACK_REPORT_URL = "https://api.redtrack.io/report"
REDTRACK_CONVERSIONS_URL = "https://api.redtrack.io/conversions"
REDTRACK_OFFER_URL = "https://api.redtrack.io/offer"
SAO_PAULO_TZ = ZoneInfo("America/Sao_Paulo")

MAX_RETRIES = 5
INITIAL_BACKOFF = 2
MAX_BACKOFF = 120
RATE_LIMIT_DELAY = 2.0  # Mais tempo entre requisições para reduzir conflito/rate limit

# Conversões: buscar TODAS as páginas (sem limite artificial)
# Aumentado de 15 para 1000 para capturar dados completos
REDTRACK_CONVERSIONS_PER_PAGE = int(os.getenv("REDTRACK_CONVERSIONS_PER_PAGE", "1000"))
REDTRACK_CONVERSIONS_MAX_PAGES = int(os.getenv("REDTRACK_CONVERSIONS_MAX_PAGES", "1000"))

UNKNOWN_DIMENSION = "unknown"

# Estruturas orientadas a aliases: adicione novos valores apenas aqui.
CHECKOUT_MAPPINGS = [
	{"value": "Cartpanda", "aliases": ["cartpanda"]},
	{"value": "Clickbank", "aliases": ["clickbank"]},
]

SQUAD_MAPPINGS = [
	{"value": "yts", "aliases": ["yt shenlong"]},
	{"value": "ytf", "aliases": ["yt fenix"]},
	{"value": "nte", "aliases": ["nte"]},
	{"value": "ntl", "aliases": ["ntl"]},
	{"value": "fb", "aliases": ["fb"]},
]

PRODUCT_MAPPINGS = [
  { "value": "shapeon", "aliases": ["shapeon"] },
  { "value": "leanrise", "aliases": ["leanrise"] },
  { "value": "optivell", "aliases": ["optivell"] },
  { "value": "visium_max", "aliases": ["visium max", "visiummax"] },

  { "value": "memo_pezil", "aliases": ["memo pezil", "memopezil"] },
  { "value": "mind_boost", "aliases": ["mind boost", "mind_boost", "mindboost"] },
  { "value": "neurodyne", "aliases": ["neurodyne"] },
  { "value": "memotril", "aliases": ["memotril"] },

  { "value": "vapofil", "aliases": ["vapofil"] },
  { "value": "prime_pulse_male", "aliases": ["prime pulse male", "primepulsemale"] },

  { "value": "steelpower", "aliases": ["steelpower", "steel power"] },
  { "value": "vigorox_prime", "aliases": ["vigorox prime", "vigoroxprime"] },
  { "value": "vigorox", "aliases": ["vigorox"] },

  { "value": "revital_gluco", "aliases": ["revital gluco", "revitalgluco"] },
  { "value": "glycopezil", "aliases": ["glycopezil"] },
  { "value": "glycocore", "aliases": ["glycocore"] },
  { "value": "glycocare", "aliases": ["glycocare"] },

  { "value": "gelatide", "aliases": ["gelatide"] },
  { "value": "vitalpro", "aliases": ["vitalpro"] },

  { "value": "vigoryn", "aliases": ["vigoryn"] },
  { "value": "focusmax", "aliases": ["focusmax"] },

  { "value": "pregera", "aliases": ["pregera", "presgera"] },

  { "value": "brain_honey", "aliases": ["brain honey", "brainhoney"] },
  { "value": "jellyburn", "aliases": ["jellyburn"] },
  { "value": "neurosalt", "aliases": ["neurosalt"] },

  { "value": "bigcap", "aliases": ["bigcap"] },
  { "value": "echozen", "aliases": ["echozen"] },
  { "value": "nervetin", "aliases": ["nervetin"] },

  { "value": "gluco_off", "aliases": ["gluco off", "glucooff"] },

  { "value": "lipojaro", "aliases": ["lipojaro"] },

  { "value": "prostate_max", "aliases": ["prostate max", "prostatemax"] }
]


"""Central configuration for the Thai election OCR pipeline."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ==================== PROJECT ====================
PROJECT_ROOT = Path(__file__).resolve().parent

# ==================== API ====================
OCR_PROVIDER_TYPHOON = "typhoon"
OCR_PROVIDER_LLAMAPARSE = "llamaparse"
OCR_PROVIDER = os.getenv("OCR_PROVIDER", OCR_PROVIDER_TYPHOON).strip().lower()
OCR_PROVIDERS = (OCR_PROVIDER_TYPHOON, OCR_PROVIDER_LLAMAPARSE)

TYPHOON_API_KEY = os.getenv("TYPHOON_API_KEY", "")
TYPHOON_BASE_URL = os.getenv("TYPHOON_BASE_URL", "https://api.opentyphoon.ai/v1")
TYPHOON_OCR_URL = os.getenv("TYPHOON_OCR_URL", "https://api.opentyphoon.ai/v1/ocr")
TYPHOON_MODEL = os.getenv("TYPHOON_OCR_MODEL", "typhoon-ocr")
TYPHOON_TASK_TYPE = os.getenv("TYPHOON_TASK_TYPE", "")
TYPHOON_TEMPERATURE = float(os.getenv("TYPHOON_TEMPERATURE", "0.1"))
TYPHOON_MAX_TOKENS = int(os.getenv("TYPHOON_MAX_TOKENS", "16384"))
TYPHOON_TOP_P = float(os.getenv("TYPHOON_TOP_P", "0.6"))
TYPHOON_REPETITION_PENALTY = float(os.getenv("TYPHOON_REPETITION_PENALTY", "1.2"))

LLAMA_CLOUD_API_KEY = os.getenv(
    "LLAMA_CLOUD_API_KEY",
    os.getenv("LLAMA_PARSE_API_KEY", ""),
)
LLAMA_PARSE_CONFIG_FILE = os.getenv(
    "LLAMA_PARSE_CONFIG_FILE",
    str(PROJECT_ROOT / "parse-config.json"),
)
LLAMA_PARSE_TIER = os.getenv("LLAMA_PARSE_TIER", "")
LLAMA_PARSE_VERSION = os.getenv("LLAMA_PARSE_VERSION", "")
LLAMA_PARSE_EXPAND = os.getenv("LLAMA_PARSE_EXPAND", "markdown_full,text_full")
LLAMA_PARSE_POLLING_INTERVAL = float(os.getenv("LLAMA_PARSE_POLLING_INTERVAL", "1.0"))
LLAMA_PARSE_TIMEOUT = float(os.getenv("LLAMA_PARSE_TIMEOUT", "7200"))
LLAMA_PARSE_VERBOSE = os.getenv("LLAMA_PARSE_VERBOSE", "false").lower() == "true"

# ==================== PATH ====================
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_CONST_DIR = PROJECT_ROOT / "data" / "processed" / "constituency"
PROCESSED_PARTY_DIR = PROJECT_ROOT / "data" / "processed" / "partylist"
OUTPUT_DIR = PROJECT_ROOT / "output"
LOG_FILE = OUTPUT_DIR / "pipeline.log"

# ==================== PDF STRUCTURE ====================
PAGES_PER_UNIT = 6
CONST_PAGE_INDICES = [0]
PARTY_PAGE_INDICES = [2, 3, 4]
CONST_SPLIT_PAGES_PER_UNIT = 1
PARTY_SPLIT_PAGES_PER_UNIT = 3

# ==================== OCR ====================
DPI = 200
JPEG_QUALITY = 90
SLEEP_BETWEEN_CALLS = 0.5
MAX_RETRIES = 3
RETRY_BACKOFF_BASE_SECONDS = 1
API_KEY_PLACEHOLDER = "YOUR_API_KEY_HERE"

# ==================== OCR TEXT PARSING ====================
NUMBER_TOKEN_PATTERN = r"[-–]|[0-9๐-๙OoIlS][0-9๐-๙OoIlS,]*"
BALLOT_FIELD_ALIASES = {
    "ballot_total": [
        "จำนวนบัตรทั้งหมด",
        "บัตรทั้งหมด",
        "จำนวนบัตรเลือกตั้งที่ใช้",
        "บัตรเลือกตั้งที่ใช้",
        "จำนวนผู้มาใช้สิทธิ",
        "ผู้มาใช้สิทธิ",
        "จำนวนผู้มาแสดงตน",
        "ผู้มาแสดงตน",
    ],
    "ballot_valid": [
        "จำนวนบัตรดี",
        "บัตรดี",
        "บัตรที่ใช้ลงคะแนน",
    ],
    "ballot_invalid": [
        "จำนวนบัตรเสีย",
        "บัตรเสีย",
    ],
    "ballot_no_vote": [
        "จำนวนบัตรไม่ประสงค์ลงคะแนน",
        "บัตรไม่ประสงค์ลงคะแนน",
        "ไม่ประสงค์ลงคะแนน",
        "ไม่เลือกผู้สมัครผู้ใด",
        "ไม่เลือกบัญชีรายชื่อของพรรคการเมืองใด",
    ],
}

# ==================== FORM TYPES ====================
FORM_CONSTITUENCY = "constituency"
FORM_PARTYLIST = "partylist"
FORM_TYPES = (FORM_CONSTITUENCY, FORM_PARTYLIST)
FORM_DISPLAY_NAMES = {
    FORM_CONSTITUENCY: "Constituency",
    FORM_PARTYLIST: "Party-list",
}
FORM_OUTPUT_PREFIXES = {
    FORM_CONSTITUENCY: "Constituency_",
    FORM_PARTYLIST: "PartyList_",
}
FORM_JSON_PREFIXES = {
    FORM_CONSTITUENCY: "constituency",
    FORM_PARTYLIST: "partylist",
}
FORM_INPUT_DIRS = {
    FORM_CONSTITUENCY: PROCESSED_CONST_DIR,
    FORM_PARTYLIST: PROCESSED_PARTY_DIR,
}
FORM_SPLIT_PAGES_PER_UNIT = {
    FORM_CONSTITUENCY: CONST_SPLIT_PAGES_PER_UNIT,
    FORM_PARTYLIST: PARTY_SPLIT_PAGES_PER_UNIT,
}
FORM_ENTITY_LABELS = {
    FORM_CONSTITUENCY: "ผู้สมัคร",
    FORM_PARTYLIST: "พรรค",
}

# ==================== OUTPUT FILES ====================
CONSTITUENCY_CSV = "constituency.csv"
CONSTITUENCY_JSON = "constituency.json"
PARTYLIST_CSV = "partylist.csv"
PARTYLIST_JSON = "partylist.json"
FLAGGED_CSV = "flagged.csv"
CROSS_VALIDATION_CSV = "cross_validation.csv"
STATISTICAL_REPORT_CSV = "statistical_report.csv"
OUTPUT_FILES = {
    FORM_CONSTITUENCY: {
        "csv": CONSTITUENCY_CSV,
        "json": CONSTITUENCY_JSON,
    },
    FORM_PARTYLIST: {
        "csv": PARTYLIST_CSV,
        "json": PARTYLIST_JSON,
    },
}

# ==================== SOURCE NAMING ====================
UNKNOWN_DISTRICT_NAME = "unknown_district"
SOURCE_FILENAME_PREFIX_PATTERN = r"^\d+"
OUTPUT_FILENAME_INVALID_CHARS_PATTERN = r'[<>:"/\\|?*]+'

# ==================== SCHEMA FIELDS ====================
FIELD_SOURCE_FILE = "source_file"
FIELD_UNIT_INDEX = "unit_index"
FIELD_FORM_TYPE = "form_type"
FIELD_BALLOT_TOTAL = "ballot_total"
FIELD_BALLOT_VALID = "ballot_valid"
FIELD_BALLOT_INVALID = "ballot_invalid"
FIELD_BALLOT_NO_VOTE = "ballot_no_vote"
FIELD_SCORES = "scores"
FIELD_RAW_RESPONSE = "raw_response"
FIELD_PARSE_ERROR = "parse_error"
FIELD_STATUS = "status"
FIELD_CROSS_STATUS = "cross_status"
FIELD_CROSS_ISSUES = "cross_issues"
FIELD_STAT_FLAGS = "stat_flags"
FIELD_CLEANING_NOTES = "cleaning_notes"
FIELD_ISSUES = "issues"
FIELD_TURNOUT = "turnout"
BALLOT_FIELDS = (
    FIELD_BALLOT_TOTAL,
    FIELD_BALLOT_VALID,
    FIELD_BALLOT_INVALID,
    FIELD_BALLOT_NO_VOTE,
)
BASE_CSV_COLUMNS = [
    FIELD_SOURCE_FILE,
    FIELD_UNIT_INDEX,
    FIELD_STATUS,
    FIELD_CROSS_STATUS,
    FIELD_STAT_FLAGS,
    FIELD_BALLOT_TOTAL,
    FIELD_BALLOT_VALID,
    FIELD_BALLOT_INVALID,
    FIELD_BALLOT_NO_VOTE,
    FIELD_CLEANING_NOTES,
    FIELD_ISSUES,
]
CROSS_VALIDATION_COLUMNS = [
    FIELD_SOURCE_FILE,
    FIELD_UNIT_INDEX,
    "const_ballot_total",
    "partylist_ballot_total",
    "diff",
    FIELD_CROSS_STATUS,
    FIELD_CROSS_ISSUES,
]
STATISTICAL_REPORT_COLUMNS = [
    FIELD_SOURCE_FILE,
    FIELD_UNIT_INDEX,
    FIELD_FORM_TYPE,
    FIELD_BALLOT_TOTAL,
    FIELD_BALLOT_VALID,
    FIELD_TURNOUT,
    FIELD_STAT_FLAGS,
]

# ==================== STATUSES ====================
STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
CROSS_STATUS_OK = "OK"
CROSS_STATUS_MISMATCH = "MISMATCH"
CROSS_STATUS_MISSING_PAIR = "MISSING_PAIR"
DEFAULT_PENDING_STATUS = ""

# ==================== CLI ====================
STEP_ALL = "all"
STEP_SPLIT = "split"
STEP_OCR = "ocr"
STEP_CLEAN = "clean"
STEP_VALIDATE = "validate"
STEP_CHOICES = (STEP_ALL, STEP_SPLIT, STEP_OCR, STEP_CLEAN, STEP_VALIDATE)
DEFAULT_STEP = STEP_ALL

# ==================== CLEANING ====================
THAI_DIGIT_TRANSLATION = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
OCR_CONFUSION_MAP = {
    "O": "0",
    "o": "0",
    "I": "1",
    "l": "1",
    "S": "5",
}
DASH_VALUES = ("-", "–")
CSV_JOIN_SEPARATOR = "; "

# ==================== PROMPTS ====================
SYSTEM_PROMPT = (
    "คุณคือผู้เชี่ยวชาญในการอ่านเอกสารราชการไทย "
    "โดยเฉพาะแบบรายงานผลการนับคะแนนเลือกตั้ง\n"
    "ให้อ่านตัวเลขจากเอกสารและตอบเป็น JSON เท่านั้น "
    "ห้ามมีข้อความอื่นนอกจาก JSON"
)
USER_PROMPT_TEMPLATE = """อ่านข้อมูลจากภาพเอกสาร (อาจมีหลายภาพซึ่งเป็นหน้าต่อเนื่องของเอกสารเดียวกัน)

สิ่งที่ต้องการ:
1. จำนวนบัตรทั้งหมด
2. บัตรดี
3. บัตรเสีย
4. บัตรไม่ประสงค์ลงคะแนน
5. คะแนนของแต่ละ{entity_label}จากตาราง

กฎ:
- ตัวเลขให้ใส่เป็น integer ไม่มี comma
- ช่องว่างหรืออ่านไม่ได้ให้ใส่ null
- เลขไทย (๑๒๓) ให้แปลงเป็นอารบิก
- ตอบเป็น JSON เท่านั้น

รูปแบบ JSON:
{{
  "ballot_total": <int|null>,
  "ballot_valid": <int|null>,
  "ballot_invalid": <int|null>,
  "ballot_no_vote": <int|null>,
  "scores": {{
{score_entries}
  }}
}}
"""

# ==================== PARTY NAMES ====================
# constituency (แบ่งเขต) — ชื่อผู้สมัคร ปรับตามเขตที่เลือก
CONSTITUENCY_CANDIDATES = [
    "วรท เทอดวีระพงศ์",
    "ศุภกร ขุนชิต",
    "พ.ต.อ.พงศ์พสิษฐ์ ทองด้วง",
    "อธิคม ขุนแก้ว",
    "ภพเอกอัคร อินทรโม",
    "สมเสริม ชูรักษ์",
    "นิติศักดิ์ ธรรมเพชร",
]

# party-list (บัญชีรายชื่อ) — ชื่อพรรค เรียงตามลำดับในฟอร์ม
PARTY_LIST_PARTIES = [
    "ไทยทรัพย์ทวี",
    "เพื่อชาติไทย",
    "ใหม่",
    "มิติใหม่",
    "รวมใจไทย",
    "รวมไทยสร้างชาติ",
    "พลวัต",
    "ประชาธิปไดยใหม่",
    "เพื่อไทย",
    "ทางเลือกไทย",
    "เศรษฐกิจ",
    "เสรีรวมไทย",
    "รวมพลังประชาชน",
    "ท้องที่ไทย",
    "อนาคตไทย",
    "พลังเพื่อไทย",
    "ไทยชนะ",
    "พลังสังคมใหม่",
    "สังคมประชาธิปไดยไทย",
    "ฟิวชัน",
    "ไทรวมพลัง",
    "ก้าวอิสระ",
    "ปวงชนไทย",
    "วิชชั่นใหม่",
    "เพื่อชีวิตใหม่",
    "คลองไทย",
    "ประชาธิปัตย์",
    "ไทยก้าวหน้า",
    "ไทยภักดี",
    "แรงงานสร้างชาติ",
    "ประชากรไทย",
    "ครูไทยเพื่อประชาชน",
    "ประชาชาติ",
    "สร้างอนาคตไทย",
    "รักชาติ",
    "ไทยพร้อม",
    "ภูมิใจไทย",
    "พลังธรรมใหม่",
    "กรีน",
    "ไทยธรรม",
    "แผ่นดินธรรม",
    "กล้าธรรม",
    "พลังประชารัฐ",
    "โอกาสใหม่",
    "เป็นธรรม",
    "ประชาชน",
    "ประชาไทย",
    "ไทยสร้างไทย",
    "ไทยก้าวใหม่",
    "ประชาอาสาชาติ",
    "พร้อม",
    "เครือข่ายชาวนาแห่งประเทศไทย",
    "ไทยพิทักษ์ธรรม",
    "ความหวังใหม่",
    "ไทยรวมไทย",
    "เพื่อบ้านเมือง",
    "พลังไทยรักชาติ",
]

FORM_NAMES = {
    FORM_CONSTITUENCY: CONSTITUENCY_CANDIDATES,
    FORM_PARTYLIST: PARTY_LIST_PARTIES,
}

# Optional format:
# REGISTERED_VOTERS_BY_UNIT = {
#     ("24ตำบลมะกอกเหนือ(เทศบาล).pdf", 0): 850,
#     "24ตำบลมะกอกเหนือ(เทศบาล).pdf:1": 790,
# }
REGISTERED_VOTERS_BY_UNIT = {}

import csv
import io
import re
from datetime import datetime

import pdfplumber

from app.models.expense import ExpenseCategory

# ---------------------------------------------------------------------------
# Category keyword map (Indian context)
# ---------------------------------------------------------------------------
_CATEGORY_KEYWORDS: list[tuple[ExpenseCategory, list[str]]] = [
    (ExpenseCategory.food, [
        "swiggy", "zomato", "hotel", "restaurant", "cafe", "food", "kitchen",
        "dhaba", "biryani", "pizza", "burger", "bakery", "canteen", "mess",
        "dominos", "kfc", "mcdonalds", "subway", "haldirams", "barbeque",
        "eatery", "diner", "snacks", "juice", "tea", "coffee", "starbucks",
    ]),
    (ExpenseCategory.transport, [
        "uber", "ola", "rapido", "petrol", "fuel", "metro", "bus", "railway",
        "irctc", "redbus", "makemytrip", "goibibo", "indigo", "spicejet",
        "airindia", "cab", "auto", "toll", "parking", "diesel",
    ]),
    (ExpenseCategory.shopping, [
        "amazon", "flipkart", "myntra", "meesho", "ajio", "nykaa", "snapdeal",
        "mall", "store", "shop", "market", "retail", "bigbasket", "blinkit",
        "zepto", "grofers", "dmart", "reliance", "tata", "croma", "vijay sales",
    ]),
    (ExpenseCategory.entertainment, [
        "netflix", "spotify", "pvr", "inox", "bookmyshow", "hotstar", "disney",
        "youtube", "prime", "zee5", "sonyliv", "game", "gaming", "steam",
        "playstation", "xbox", "concert", "event", "ticket",
    ]),
    (ExpenseCategory.health, [
        "hospital", "pharmacy", "apollo", "medplus", "doctor", "clinic",
        "health", "med", "pharma", "diagnostic", "lab", "pathology",
        "netmeds", "1mg", "practo", "dental", "optician", "gym", "fitness",
    ]),
    (ExpenseCategory.education, [
        "school", "college", "university", "udemy", "coursera", "fees",
        "tuition", "book", "stationery", "byju", "unacademy", "vedantu",
        "coaching", "institute", "library", "exam",
    ]),
    (ExpenseCategory.housing, [
        "rent", "electricity", "water", "gas", "maintenance", "society",
        "broadband", "wifi", "airtel", "jio", "bsnl", "vi ", "vodafone",
        "idea", "recharge", "bill", "insurance", "lic", "housing",
        "property", "flat", "pg ", "hostel",
    ]),
]


def suggest_category(description: str) -> tuple[ExpenseCategory, str]:
    """Return (category, confidence) based on description keywords."""
    text = description.lower()
    for category, keywords in _CATEGORY_KEYWORDS:
        for kw in keywords:
            if kw in text:
                return category, "high"
    return ExpenseCategory.other, "low"


# ---------------------------------------------------------------------------
# Date parsing helpers
# ---------------------------------------------------------------------------
_DATE_FORMATS = [
    "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y",
    "%Y-%m-%d", "%d %b %Y", "%d %b %y", "%d%b%Y", "%d%b%y",
    "%d/%m/%Y %H:%M:%S", "%d-%m-%Y %H:%M:%S",
]


def _parse_date(raw: str) -> datetime | None:
    raw = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _clean_amount(raw: str) -> float | None:
    cleaned = re.sub(r"[₹$,\s]", "", raw).strip()
    try:
        return abs(float(cleaned))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Extract bank/account info from text
# ---------------------------------------------------------------------------
def extract_account_info(text: str) -> dict:
    info: dict = {"bank_name": None, "account_number": None, "account_holder": None}

    # account number — flexible: label then optional separators then the number
    # covers: Ac No, A/C No, Account No, Account Number, Acct No
    # number itself: digits and X/x/* masking chars, 4-20 chars
    acc_match = re.search(
        r"(?:a/?c\s*(?:no\.?|number)?|account\s*(?:no\.?|number)?|acct\.?\s*(?:no\.?)?)"
        r"[:\s#\-]*([Xx*\d][Xx*\d\s]{2,18}[Xx*\d])",
        text, re.IGNORECASE,
    )
    if acc_match:
        # strip internal spaces that may appear in masked numbers like "XXXX 1234"
        info["account_number"] = re.sub(r"\s+", "", acc_match.group(1)).strip()

    # fallback: bare 9-18 digit number on its own line (common in mini statements)
    if not info["account_number"]:
        bare_match = re.search(r"(?:^|\s)(\d{9,18})(?:\s|$)", text, re.MULTILINE)
        if bare_match:
            info["account_number"] = bare_match.group(1).strip()

    # account holder
    holder_match = re.search(
        r"(?:name|account\s*holder|a/?c\s*holder)[:\s]+([A-Za-z][A-Za-z\s]{2,48})",
        text, re.IGNORECASE,
    )
    if holder_match:
        info["account_holder"] = holder_match.group(1).strip()

    # bank name
    banks = [
        "SBI", "State Bank", "HDFC", "ICICI", "Axis", "Kotak", "Punjab National",
        "PNB", "Bank of Baroda", "BOB", "Canara", "Union Bank", "IndusInd",
        "Yes Bank", "IDFC", "Federal Bank", "South Indian Bank", "Karnataka Bank",
        "UCO Bank", "Central Bank", "Indian Bank", "Bank of India",
    ]
    for bank in banks:
        if re.search(bank, text, re.IGNORECASE):
            info["bank_name"] = bank
            break

    return info


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------
def _parse_text_lines(text: str) -> list[dict]:
    """
    Generic line-by-line parser for mini statements / raw text.
    Looks for lines containing a date + amount pattern.
    """
    transactions = []
    # pattern: date ... description ... amount (Dr/Cr suffix optional)
    line_pattern = re.compile(
        r"(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}|\d{1,2}\s*[A-Za-z]{3}\s*\d{2,4})"  # date
        r"(.+?)"                                                                      # description
        r"([\d,]+\.?\d*)\s*(?:Dr|CR|dr|cr)?",                                        # amount
        re.IGNORECASE,
    )
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = line_pattern.search(line)
        if not m:
            continue
        date = _parse_date(m.group(1))
        amount = _clean_amount(m.group(3))
        description = re.sub(r"\s+", " ", m.group(2)).strip(" :-|")
        if date and amount and description:
            # only debit — lines with "Dr" or no "Cr"
            is_credit = bool(re.search(r"\bCr\b", line, re.IGNORECASE))
            if not is_credit:
                transactions.append({"date": date, "description": description, "amount": amount})
    return transactions


def parse_pdf(file_bytes: bytes) -> tuple[dict, list[dict]]:
    text = ""
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text += (page.extract_text() or "") + "\n"
    account_info = extract_account_info(text)
    transactions = _parse_text_lines(text)
    return account_info, transactions


def parse_csv(file_bytes: bytes) -> tuple[dict, list[dict]]:
    text = file_bytes.decode("utf-8", errors="ignore")
    account_info = extract_account_info(text)
    transactions = []

    reader = csv.DictReader(io.StringIO(text))
    headers = [h.lower().strip() for h in (reader.fieldnames or [])]

    # map common CSV column names
    date_col = next((h for h in headers if "date" in h), None)
    desc_col = next((h for h in headers if any(k in h for k in ["desc", "narration", "particular", "detail", "remark"])), None)
    debit_col = next((h for h in headers if "debit" in h or "dr" in h or "withdrawal" in h), None)
    amount_col = next((h for h in headers if "amount" in h), None) if not debit_col else None

    for row in reader:
        raw_keys = {k.lower().strip(): v for k, v in row.items()}
        raw_date = raw_keys.get(date_col, "") if date_col else ""
        raw_desc = raw_keys.get(desc_col, "") if desc_col else ""
        raw_amount = raw_keys.get(debit_col or amount_col or "", "")

        date = _parse_date(raw_date)
        amount = _clean_amount(raw_amount)
        description = raw_desc.strip()

        if date and amount and amount > 0 and description:
            transactions.append({"date": date, "description": description, "amount": amount})

    # fallback to line parser if CSV parsing yielded nothing
    if not transactions:
        transactions = _parse_text_lines(text)

    return account_info, transactions


def parse_raw_text(text: str) -> tuple[dict, list[dict]]:
    account_info = extract_account_info(text)
    transactions = _parse_text_lines(text)
    return account_info, transactions


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def parse_statement(
    source: str,
    file_bytes: bytes | None = None,
    raw_text: str | None = None,
) -> tuple[dict, list[dict]]:
    """
    Returns (account_info, transactions).
    source: "pdf" | "csv" | "text"
    """
    if source == "pdf" and file_bytes:
        return parse_pdf(file_bytes)
    if source == "csv" and file_bytes:
        return parse_csv(file_bytes)
    if source == "text" and raw_text:
        return parse_raw_text(raw_text)
    return {}, []

import csv
import io
import re
from datetime import datetime

import pdfplumber

from app.models.expense import ExpenseCategory

# ---------------------------------------------------------------------------
# Category keyword map (Indian context)
# ---------------------------------------------------------------------------
# (keyword, whole_word_only) — whole_word=True uses \b to avoid false matches
_CATEGORY_KEYWORDS: list[tuple[ExpenseCategory, list[tuple[str, bool]]]] = [
    (ExpenseCategory.food, [
        ("swiggy", False), ("zomato", False), ("restaurant", False), ("cafe", False),
        ("kitchen", False), ("dhaba", False), ("biryani", False), ("pizza", False),
        ("burger", False), ("bakery", False), ("canteen", False), ("dominos", False),
        ("kfc", True), ("mcdonalds", False), ("subway", False), ("haldirams", False),
        ("barbeque", False), ("eatery", False), ("diner", False), ("starbucks", False),
        ("foodcourt", False), ("tiffin", False), ("hotel", True),
    ]),
    (ExpenseCategory.transport, [
        ("uber", False), ("ola", True), ("rapido", False), ("petrol", False),
        ("fuel", False), ("metro", False), ("irctc", False), ("redbus", False),
        ("makemytrip", False), ("goibibo", False), ("indigo", False), ("spicejet", False),
        ("airindia", False), ("fastag", False), ("diesel", False), ("railway", False),
        ("parking", False), ("tollway", False), ("rapido", False),
    ]),
    (ExpenseCategory.shopping, [
        ("amazon", False), ("flipkart", False), ("myntra", False), ("meesho", False),
        ("ajio", False), ("nykaa", False), ("snapdeal", False), ("bigbasket", False),
        ("blinkit", False), ("zepto", False), ("grofers", False), ("dmart", False),
        ("croma", False), ("vijaysales", False), ("shopify", False),
        ("stores", False), ("fancy", False), ("enterprises", False),
    ]),
    (ExpenseCategory.entertainment, [
        ("netflix", False), ("spotify", False), ("pvr", True), ("inox", False),
        ("bookmyshow", False), ("hotstar", False), ("disney", False), ("zee5", False),
        ("sonyliv", False), ("gaming", False), ("steam", False), ("playstation", False),
        ("xbox", False), ("concert", False), ("youtube", False),
    ]),
    (ExpenseCategory.health, [
        ("hospital", False), ("pharmacy", False), ("apollo", False), ("medplus", False),
        ("doctor", False), ("clinic", False), ("pharma", False), ("diagnostic", False),
        ("pathology", False), ("netmeds", False), ("1mg", False), ("practo", False),
        ("dental", False), ("optician", False), ("fitness", False), ("healthkart", False),
    ]),
    (ExpenseCategory.education, [
        ("school", False), ("college", False), ("university", False), ("udemy", False),
        ("coursera", False), ("tuition", False), ("stationery", False), ("byju", False),
        ("unacademy", False), ("vedantu", False), ("coaching", False), ("institute", False),
        ("admission", False),
    ]),
    (ExpenseCategory.housing, [
        ("electricity", False), ("maintenance", False), ("society", False),
        ("broadband", False), ("airtel", False), ("jio", True), ("bsnl", False),
        ("vodafone", False), ("recharge", False), ("insurance", False),
        ("housing", False), ("rentpay", False), ("nobroker", False),
    ]),
]


def suggest_category(description: str) -> tuple[ExpenseCategory, str]:
    """Return (category, confidence) based on description keywords.
    Splits UPI-style descriptions like UPI/SWIGGY ORDERS/REF123 into parts first.
    """
    # split on / - _ | to handle UPI/NEFT/POS style descriptions
    parts = re.split(r"[/\-_|]", description.lower())
    text = " ".join(parts)

    for category, keywords in _CATEGORY_KEYWORDS:
        for kw, whole_word in keywords:
            if whole_word:
                if re.search(rf"\b{re.escape(kw)}\b", text):
                    return category, "high"
            else:
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
    "%d %B %Y",  # 02 March 2026
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
_DATE_LINE_RE = re.compile(
    r"^(\d{1,2}\s+[A-Za-z]{3}\s+\d{2,4}|\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
    re.IGNORECASE,
)
_AMOUNT_RE = re.compile(r"INR\s+([\d,]+\.\d{2})", re.IGNORECASE)


def _group_blocks(text: str) -> list[str]:
    """Group multi-line PDF text into per-transaction blocks.
    Each block starts with a date line.
    """
    blocks: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # skip header/footer lines
        if re.match(r"^(date|transaction|details|debits|credits|balance)",
                    stripped, re.IGNORECASE):
            continue
        if _DATE_LINE_RE.match(stripped):
            if current:
                blocks.append(" ".join(current))
            current = [stripped]
        else:
            current.append(stripped)
    if current:
        blocks.append(" ".join(current))
    return blocks


def _extract_merchant(block: str) -> str:
    """Pull the most useful merchant name from a UPI block.
    UPI format: BANKCODE/MERCHANT NAME/XXXXX/upi@handle/UPI/refno/...
    """
    # remove date prefix
    block = _DATE_LINE_RE.sub("", block).strip()
    # remove INR amounts and trailing junk
    block = _AMOUNT_RE.sub("", block)
    block = re.sub(r"BRANCH\s*:\s*ATM SERVICE BRANCH", "", block, flags=re.IGNORECASE)
    block = re.sub(r"/UPI/\d+", "", block)
    block = re.sub(r"[A-Z0-9]+@[a-z]+", "", block)   # remove UPI handles
    block = re.sub(r"XXXXX\w*", "", block)             # remove masked acc
    block = re.sub(r"[A-Z]{4}\d[A-Z0-9]{6}", "", block)  # remove IFSC codes

    # split on / and pick the longest meaningful part
    parts = [p.strip() for p in block.split("/") if p.strip()]
    parts = [p for p in parts if len(p) > 2 and not re.match(r"^[\d\s]+$", p)]
    if not parts:
        return block.strip()
    # longest part is usually the merchant name
    return max(parts, key=len).strip()


def _parse_text_lines(text: str) -> list[dict]:
    """Parse both single-line and multi-line (PDF) bank statement formats."""
    transactions = []
    blocks = _group_blocks(text)

    for block in blocks:
        # extract date
        date_match = _DATE_LINE_RE.match(block)
        if not date_match:
            continue
        date = _parse_date(date_match.group(1))
        if not date:
            continue

        # find all INR amounts in block
        amounts = _AMOUNT_RE.findall(block)
        if not amounts:
            continue

        # determine debit/credit
        # pattern: INR debit_amount - INR balance  OR  - INR credit_amount INR balance
        # a dash before INR credit means it's a credit transaction
        is_credit = bool(re.search(r"-\s*INR\s+[\d,]+\.\d{2}\s+INR", block, re.IGNORECASE))
        # also check if first amount slot is empty ("  - INR 700" style from PDF)
        debit_match = re.search(
            r"INR\s+([\d,]+\.\d{2})\s+-\s+INR", block, re.IGNORECASE
        )
        if not debit_match:
            # no debit amount found — skip (credit only)
            continue

        amount = _clean_amount(debit_match.group(1))
        if not amount or amount <= 0:
            continue

        description = _extract_merchant(block)
        if not description:
            continue

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

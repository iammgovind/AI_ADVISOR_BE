import csv
import io
import re
from datetime import datetime

import pdfplumber

from app.models.expense import ExpenseCategory

# ---------------------------------------------------------------------------
# Category keyword map (Indian context)
# (keyword, whole_word_only) — whole_word=True uses \b to avoid false matches
# ---------------------------------------------------------------------------
_CATEGORY_KEYWORDS: list[tuple[ExpenseCategory, list[tuple[str, bool]]]] = [
    (ExpenseCategory.food, [
        ("swiggy", False), ("zomato", False), ("restaurant", False), ("cafe", False),
        ("kitchen", False), ("dhaba", False), ("biryani", False), ("pizza", False),
        ("burger", False), ("bakery", False), ("canteen", False), ("dominos", False),
        ("kfc", True), ("mcdonalds", False), ("subway", False), ("haldirams", False),
        ("barbeque", False), ("eatery", False), ("diner", False), ("starbucks", False),
        ("foodcourt", False), ("tiffin", False), ("coffee", False), ("hotel", True),
    ]),
    (ExpenseCategory.transport, [
        ("uber", False), ("ola", True), ("rapido", False), ("petrol", False),
        ("fuel", False), ("metro", False), ("irctc", False), ("redbus", False),
        ("makemytrip", False), ("goibibo", False), ("indigo", False), ("spicejet", False),
        ("airindia", False), ("fastag", False), ("diesel", False), ("railway", False),
        ("parking", False), ("tollway", False),
    ]),
    (ExpenseCategory.shopping, [
        ("amazon", False), ("flipkart", False), ("myntra", False), ("meesho", False),
        ("ajio", False), ("nykaa", False), ("snapdeal", False), ("bigbasket", False),
        ("blinkit", False), ("zepto", False), ("grofers", False), ("dmart", False),
        ("croma", False), ("vijaysales", False), ("shopify", False),
        ("stores", False), ("fancy", False), ("enterprises", False), ("traders", False),
        ("tex", False), ("textiles", False), ("plazza", False), ("plaza", False),
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
    """Return (category, confidence). Splits on / - _ | to handle UPI descriptions."""
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
# Date / amount helpers
# ---------------------------------------------------------------------------
_DATE_FORMATS = [
    "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y",
    "%Y-%m-%d", "%d %b %Y", "%d %b %y", "%d%b%Y", "%d%b%y",
    "%d/%m/%Y %H:%M:%S", "%d-%m-%Y %H:%M:%S", "%d %B %Y",
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
# Account info extraction
# ---------------------------------------------------------------------------
def extract_account_info(text: str) -> dict:
    info: dict = {"bank_name": None, "account_number": None, "account_holder": None}

    acc_match = re.search(
        r"(?:a/?c\s*(?:no\.?|number)?|account\s*(?:no\.?|number)?|acct\.?\s*(?:no\.?)?)"
        r"[:\s#\-]*([Xx*\d][Xx*\d\s]{2,18}[Xx*\d])",
        text, re.IGNORECASE,
    )
    if acc_match:
        info["account_number"] = re.sub(r"\s+", "", acc_match.group(1)).strip()

    if not info["account_number"]:
        bare_match = re.search(r"(?:^|\s)(\d{9,18})(?:\s|$)", text, re.MULTILINE)
        if bare_match:
            info["account_number"] = bare_match.group(1).strip()

    holder_match = re.search(
        r"(?:name|account\s*holder|a/?c\s*holder)[:\s]+([A-Za-z][A-Za-z\s]{2,48})",
        text, re.IGNORECASE,
    )
    if holder_match:
        info["account_holder"] = holder_match.group(1).strip()

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
# PDF multi-line block helpers
# ---------------------------------------------------------------------------
_DATE_LINE_RE = re.compile(
    r"^(\d{1,2}\s+[A-Za-z]{3}\s+\d{2,4}|\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
    re.IGNORECASE,
)
_AMOUNT_RE = re.compile(r"INR\s+([\d,]+\.\d{2})", re.IGNORECASE)


def _group_blocks(text: str) -> list[str]:
    """Group multi-line PDF text into per-transaction blocks starting with a date."""
    blocks: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^(date|transaction|details|debits|credits|balance)", stripped, re.IGNORECASE):
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
    """Extract clean merchant name from a raw UPI transaction block/line."""
    block = re.sub(r"[\r\n]+", " ", block)
    block = re.sub(r"\s{2,}", " ", block)
    block = _DATE_LINE_RE.sub("", block).strip()
    block = _AMOUNT_RE.sub("", block)
    block = re.sub(r"[₹$][\d,]+\.?\d*", "", block)
    block = re.sub(r"\b(DR|CR)\b", "", block, flags=re.IGNORECASE)
    block = re.sub(r"BRANCH\s*:\s*ATM SERVICE BRANCH", "", block, flags=re.IGNORECASE)
    block = re.sub(r"/UPI/\d+", "", block)
    block = re.sub(r"/Pay Request", "", block, flags=re.IGNORECASE)
    block = re.sub(r"[\w.+-]+@[\w]+", "", block)        # UPI handles
    block = re.sub(r"XXXXX\w*", "", block)               # masked acc
    block = re.sub(r"\b[A-Z]{4}\d[A-Z0-9]{6}\b", "", block)  # IFSC codes
    block = re.sub(r"\b\d{6,}\b", "", block)             # long ref numbers
    block = re.sub(r"\bUPI\b", "", block, flags=re.IGNORECASE)

    parts = [p.strip() for p in block.split("/") if p.strip()]
    parts = [p for p in parts if len(p) > 2 and not re.match(r"^[\d\s]+$", p)]
    if not parts:
        return block.strip()
    return max(parts, key=len).strip()


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------
def _parse_pdf_blocks(text: str) -> list[dict]:
    """Parse multi-line PDF format: INR X.XX - INR (debit then balance)."""
    transactions = []
    for block in _group_blocks(text):
        date_match = _DATE_LINE_RE.match(block)
        if not date_match:
            continue
        date = _parse_date(date_match.group(1))
        if not date:
            continue
        debit_match = re.search(r"INR\s+([\d,]+\.\d{2})\s+-\s+INR", block, re.IGNORECASE)
        if not debit_match:
            continue
        amount = _clean_amount(debit_match.group(1))
        if not amount or amount <= 0:
            continue
        description = _extract_merchant(block)
        if not description:
            continue
        transactions.append({"date": date, "description": description, "amount": amount})
    return transactions


def _parse_whatsapp_text(text: str) -> list[dict]:
    """Parse WhatsApp mini statement:
    Line 1: *24-10-2026  ₹280.000 DR*
    Line 2: BANKCODE/MERCHANT NAME/XXXXX/upi@handle/...
    """
    transactions = []
    lines = [line.strip() for line in text.splitlines()]
    i = 0
    while i < len(lines):
        header_match = re.search(
            r"(\d{2}-\d{2}-\d{4})\s+[₹Rs.]*\s*([\d,]+\.?\d*)\s+(DR|CR)",
            lines[i], re.IGNORECASE,
        )
        if header_match and header_match.group(3).upper() == "DR":
            date = _parse_date(header_match.group(1))
            amount = _clean_amount(header_match.group(2))
            # find next non-empty line for merchant
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            merchant = _extract_merchant(lines[j]) if j < len(lines) else ""
            if date and amount and merchant:
                transactions.append({"date": date, "description": merchant, "amount": amount})
        i += 1
    return transactions


def _parse_simple_lines(text: str) -> list[dict]:
    """Parse single-line formats: Dr 250.00 / 250.00 Dr."""
    transactions = []
    line_re = re.compile(
        r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{1,2}\s+[A-Za-z]{3}\s+\d{2,4})"
        r"(.+?)"
        r"([\d,]+\.\d{2})"
        r"[^\d]*$",
        re.IGNORECASE,
    )
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = line_re.search(line)
        if not m:
            continue
        date = _parse_date(m.group(1))
        amount = _clean_amount(m.group(3))
        description = re.sub(r"\s+", " ", m.group(2)).strip(" :-|")
        if not date or not amount or not description:
            continue
        if re.search(r"\b(cr|credit)\b", line, re.IGNORECASE):
            continue
        transactions.append({"date": date, "description": description, "amount": amount})
    return transactions


def _parse_text_lines(text: str) -> list[dict]:
    """Try WhatsApp → PDF blocks → simple lines."""
    transactions = _parse_whatsapp_text(text)
    if not transactions:
        transactions = _parse_pdf_blocks(text)
    if not transactions:
        transactions = _parse_simple_lines(text)
    return transactions


# ---------------------------------------------------------------------------
# Public parsers
# ---------------------------------------------------------------------------
def parse_pdf(file_bytes: bytes) -> tuple[dict, list[dict]]:
    text = ""
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text += (page.extract_text() or "") + "\n"
    return extract_account_info(text), _parse_text_lines(text)


def parse_csv(file_bytes: bytes) -> tuple[dict, list[dict]]:
    text = file_bytes.decode("utf-8", errors="ignore")
    account_info = extract_account_info(text)
    transactions = []

    reader = csv.DictReader(io.StringIO(text))
    headers = [h.lower().strip() for h in (reader.fieldnames or [])]

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

    if not transactions:
        transactions = _parse_text_lines(text)

    return account_info, transactions


def parse_raw_text(text: str) -> tuple[dict, list[dict]]:
    return extract_account_info(text), _parse_text_lines(text)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def parse_statement(
    source: str,
    file_bytes: bytes | None = None,
    raw_text: str | None = None,
) -> tuple[dict, list[dict]]:
    if source == "pdf" and file_bytes:
        return parse_pdf(file_bytes)
    if source == "csv" and file_bytes:
        return parse_csv(file_bytes)
    if source == "text" and raw_text:
        return parse_raw_text(raw_text)
    return {}, []

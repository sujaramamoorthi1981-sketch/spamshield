"""Rule-based spam signals. Used (a) as the fallback engine when no trained model exists and
(b) to give human-readable reasons alongside the trained model's score."""
import math
import re

URL_RE = re.compile(r"(https?://|www\.)\S+|\b\S+\.(com|net|org|info|biz|xyz|top|click|ru|tk)\b", re.I)
PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{8,}\d)")
MONEY_RE = re.compile(r"[$£€₹]\s?\d|\b\d+\s?(usd|gbp|eur|inr|dollars|pounds)\b", re.I)
SHORTCODE_RE = re.compile(r"\b(text|send|reply|call)\s+(stop|yes|win|claim|\w+)\s+to\s+\d{3,6}\b", re.I)

# (label shown to the user, regex, weight)
SIGNALS: list[tuple[str, re.Pattern, float]] = [
    ("Prize or reward language", re.compile(r"\b(winner|you (have )?won|prize|reward|jackpot|free gift|lucky|congratulations|claim)\b", re.I), 1.6),
    ("Urgency or pressure", re.compile(r"\b(urgent|act now|immediately|last chance|expires?|limited time|hurry|today only|final notice)\b", re.I), 1.2),
    ("Free or cheap offer", re.compile(r"\b(free|100% free|no cost|cheap|discount|bonus|cashback|guaranteed)\b", re.I), 0.9),
    ("Account or security bait", re.compile(r"\b(verify|suspended|locked|confirm your (account|identity)|password|otp|kyc|bank details|unusual activity)\b", re.I), 1.5),
    ("Call-to-action link wording", re.compile(r"\b(click|tap|visit|log ?in)\b.{0,30}\b(link|here|below|now)\b", re.I), 1.1),
    ("Premium-rate or opt-out instructions", SHORTCODE_RE, 1.8),
    ("Loan, investment or crypto pitch", re.compile(r"\b(loan|credit|investment|crypto|bitcoin|forex|earn \$?\d+|work from home|double your)\b", re.I), 1.1),
]


def _features(text: str) -> dict:
    letters = [c for c in text if c.isalpha()]
    caps_ratio = sum(c.isupper() for c in letters) / len(letters) if letters else 0.0
    return {
        "has_url": bool(URL_RE.search(text)),
        "has_phone": bool(PHONE_RE.search(text)),
        "has_money": bool(MONEY_RE.search(text)),
        "caps_ratio": round(caps_ratio, 2),
        "exclamations": text.count("!"),
        "length": len(text),
    }


def heuristic_analysis(text: str) -> tuple[float, list[str]]:
    """Returns (spam probability, reasons). Probability is a squashed rule score, not a calibrated one."""
    score, reasons = -1.8, []
    for label, pattern, weight in SIGNALS:
        if pattern.search(text):
            score += weight
            reasons.append(label)
    f = _features(text)
    if f["has_url"]:
        score += 1.0; reasons.append("Contains a link")
    if f["has_phone"]:
        score += 0.6; reasons.append("Contains a phone number")
    if f["has_money"]:
        score += 0.8; reasons.append("Mentions money amounts")
    if f["caps_ratio"] > 0.5 and f["length"] > 15:
        score += 0.9; reasons.append("Mostly capital letters")
    if f["exclamations"] >= 3:
        score += 0.6; reasons.append("Heavy use of exclamation marks")
    return 1 / (1 + math.exp(-score)), reasons

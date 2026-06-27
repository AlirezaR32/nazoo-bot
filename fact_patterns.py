"""
fact_patterns.py — استخراج فکت از متن با regex (فارسی + انگلیسی)
استفاده مشترک در memory.py (SQLite/polling) و api/webhook.py (Redis/serverless)
"""
import re

_EN_PATTERNS: list[tuple[str, str]] = [
    (r"\bmy name(?:'s| is)\s+(\w+)",                          "Name: {0}"),
    (r"\bi(?:'m| am)\s+(\d+)\s+years?\s+old",                 "Age: {0}"),
    (r"\bi(?:'m| am)\s+from\s+([\w\s]+?)(?:[.,!?]|\band\b|\bbut\b|$)",      "From: {0}"),
    (r"\bi\s+live\s+in\s+([\w\s]+?)(?:[.,!?]|\band\b|\bbut\b|$)",           "Location: {0}"),
    (r"\bi(?:'m| am)\s+(?:a|an)\s+([\w\s]+?)(?:[.,!?]|\band\b|\bbut\b|$)",  "Occupation: {0}"),
    (r"\bmy\s+(?:job|work|profession)\s+is\s+([\w\s]+?)(?:[.,!?]|\band\b|\bbut\b|$)", "Job: {0}"),
    (r"\bi\s+(?:love|adore|really\s+like)\s+([\w\s]+?)(?:[.,!?]|\band\b|\bbut\b|$)",  "Loves: {0}"),
    (r"\bi\s+(?:hate|dislike|can't\s+stand)\s+([\w\s]+?)(?:[.,!?]|\band\b|\bbut\b|$)","Dislikes: {0}"),
    (r"\bmy\s+favorite\s+(\w+)\s+is\s+([\w\s]+?)(?:[.,!?]|\band\b|\bbut\b|$)",        "Favorite {0}: {1}"),
    (r"\bi(?:'m| am)\s+(?:studying|a\s+student\s+of)\s+([\w\s]+?)(?:[.,!?]|\band\b|\bbut\b|$)", "Studies: {0}"),
]

_FA_PATTERNS: list[tuple[str, str]] = [
    (r"اسمم\s+([\u0600-\u06FF\w]+)",                          "اسم: {0}"),
    (r"اسم\s+من\s+([\u0600-\u06FF\w]+)",                      "اسم: {0}"),
    (r"من\s+([\u0600-\u06FF\w\s]+?)\s+هستم",                  "هویت: {0}"),
    (r"(\d+)\s*سالمه",                                         "سن: {0} سال"),
    (r"(\d+)\s*ساله\s*هستم",                                  "سن: {0} سال"),
    (r"اهل\s+([\u0600-\u06FF\w\s]+?)(?:\s+هستم|[،.!؟]|$)",    "اهل: {0}"),
    (r"تو\s+([\u0600-\u06FF\w\s]+?)\s+زندگی\s+می",            "شهر: {0}"),
    (r"ساکن\s+([\u0600-\u06FF\w\s]+?)(?:\s+هستم|[،.!؟]|$)",   "شهر: {0}"),
    (r"کارم\s+([\u0600-\u06FF\w\s]+?)\s+هست",                 "شغل: {0}"),
    (r"دارم\s+([\u0600-\u06FF\w\s]+?)\s+می.خونم",             "رشته: {0}"),
    (r"دوست\s+دارم\s+([\u0600-\u06FF\w\s]+?)(?:[،.!؟]|$)",    "علاقه: {0}"),
    (r"ازدواج\s+کردم",                                         "وضعیت: متاهل"),
    (r"مجردم",                                                 "وضعیت: مجرد"),
]


def _apply(text: str, patterns: list[tuple[str, str]]) -> list[str]:
    out: list[str] = []
    for pattern, template in patterns:
        m = re.search(pattern, text, re.IGNORECASE | re.UNICODE)
        if not m:
            continue
        groups = [g.strip().title() if g else "" for g in m.groups()]
        if any(len(g) > 60 for g in groups):
            continue
        try:
            fact = template.format(*groups)
            if 3 < len(fact) < 120:
                out.append(fact)
        except (IndexError, KeyError):
            pass
    return out


def extract_facts(text: str) -> list[str]:
    """از یه پیام، فکت‌های قابل‌استخراج (فارسی + انگلیسی) رو برمی‌گردونه."""
    facts: list[str] = []
    facts.extend(_apply(text, _EN_PATTERNS))
    facts.extend(_apply(text, _FA_PATTERNS))
    return facts

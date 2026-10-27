import re


def normalize_phone(phone):
    """Turn Tanzanian phone numbers into one format: +255XXXXXXXXX.

    Examples: '0712 345 678', '255712345678' and '+255712345678' all become '+255712345678'.
    Numbers that don't look Tanzanian are returned with only spaces and dashes removed.
    """
    cleaned = re.sub(r'[\s\-()]', '', str(phone or ''))
    if re.fullmatch(r'0[67]\d{8}', cleaned):
        return '+255' + cleaned[1:]
    if re.fullmatch(r'255[67]\d{8}', cleaned):
        return '+' + cleaned
    return cleaned


def phone_too_long(phone):
    """True if the number has too many digits, checked before normalize_phone.

    Without a country code at most 10 digits (0712345678), with Tanzania's at most 12 (+255712345678),
    and with any other country code at most 15 (the international maximum). The app's phone box
    uses the same rule.
    """
    cleaned = re.sub(r'[\s\-()]', '', str(phone or ''))
    digits = len(re.sub(r'\D', '', cleaned))
    if re.match(r'\+?255', cleaned):
        return digits > 12
    return digits > (15 if cleaned.startswith('+') else 10)

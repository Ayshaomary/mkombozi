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

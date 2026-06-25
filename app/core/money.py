"""Para tutarı formatlama ve ayrıştırma (integer + scale)."""


def format_amount(value: int, scale: int) -> str:
    """
    Tamsayı en küçük birimden kullanıcıya gösterilecek metne çevirir.
    Float kullanma.
    Örnek:
    value=12345, scale=2 -> "123,45"
    value=2500, scale=3 -> "2,500"
    """
    sign = "-" if value < 0 else ""
    v = abs(value)
    base = 10 ** scale
    whole, frac = divmod(v, base)
    if scale == 0:
        return f"{sign}{whole}"
    return f"{sign}{whole},{str(frac).zfill(scale)}"


def format_amount_with_grouping(value: int, scale: int) -> str:
    """Binlik ayırıcılı tutar formatı. Float kullanılmaz."""
    sign = "-" if value < 0 else ""
    v = abs(value)
    base = 10 ** scale
    whole, frac = divmod(v, base)

    whole_str = str(whole)
    parts: list[str] = []
    while len(whole_str) > 3:
        parts.insert(0, whole_str[-3:])
        whole_str = whole_str[:-3]
    if whole_str:
        parts.insert(0, whole_str)
    grouped_whole = ".".join(parts) if parts else "0"

    if scale == 0:
        return f"{sign}{grouped_whole}"
    return f"{sign}{grouped_whole},{str(frac).zfill(scale)}"


def parse_amount(text: str, scale: int) -> int:
    """
    Kullanıcının girdiği metni en küçük birim integer değere çevirir.
    Float kullanma.
    Decimal kullan.
    Nokta binlik ayırıcı, virgül ondalık ayırıcı kabul edilsin.
    Örnek:
    "123,45", scale=2 -> 12345
    "2,500", scale=3 -> 2500
    """
    from decimal import Decimal, InvalidOperation

    cleaned = text.strip().replace(".", "").replace(",", ".")
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        raise ValueError("Geçersiz tutar formatı")

    return int((value * (10 ** scale)).to_integral_value())

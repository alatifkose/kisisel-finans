"""Girdi doğrulama yardımcıları.

Bu aşamada yalnızca iskelet; iş kuralları ileride service katmanına taşınacak.
"""


def is_non_empty_text(value: str) -> bool:
    """Metin alanının boş olmadığını kontrol eder."""
    return bool(value and value.strip())

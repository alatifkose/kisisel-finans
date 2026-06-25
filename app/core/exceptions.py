"""Uygulama genelinde kullanılan temel istisna sınıfları."""


class AppError(Exception):
    """Tüm uygulama istisnalarının taban sınıfı."""


class ValidationError(AppError):
    """Doğrulama hatası."""


class NotFoundError(AppError):
    """Kayıt bulunamadı hatası."""


class RepositoryError(AppError):
    """Veri erişim katmanı hatası."""

"""Referans verisi iş mantığı."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.constants import VALID_CATEGORY_NATURES, VALID_COMPONENT_NATURES, Nature
from app.core.exceptions import AppError, NotFoundError, RepositoryError, ValidationError
from app.core.validators import is_non_empty_text
from app.repositories.asset_repository import AssetRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.component_type_repository import ComponentTypeRepository
from app.repositories.currency_repository import CurrencyRepository


class ReferenceService:
    """Para birimi, kategori, varlık ve bileşen tipi yönetimi."""

    MIN_SCALE = 0
    MAX_SCALE = 6

    def __init__(
        self,
        currency_repo: Optional[CurrencyRepository] = None,
        category_repo: Optional[CategoryRepository] = None,
        asset_repo: Optional[AssetRepository] = None,
        component_type_repo: Optional[ComponentTypeRepository] = None,
    ) -> None:
        self._currency_repo = currency_repo or CurrencyRepository()
        self._category_repo = category_repo or CategoryRepository()
        self._asset_repo = asset_repo or AssetRepository()
        self._component_type_repo = component_type_repo or ComponentTypeRepository()

    # --- Para birimi ---

    def list_currencies(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        return self._currency_repo.list_currencies(include_inactive=include_inactive)

    def create_currency(self, code: str, symbol: str, scale: int) -> int:
        normalized_code = self._validate_currency_code(code)
        normalized_symbol = (symbol or "").strip()
        validated_scale = self._validate_scale(scale)
        try:
            return self._currency_repo.create_currency(
                normalized_code,
                normalized_symbol,
                validated_scale,
            )
        except RepositoryError as exc:
            raise ValidationError(str(exc)) from exc

    def update_currency(
        self,
        currency_id: int,
        code: str,
        symbol: str,
        scale: int,
        is_active: bool,
    ) -> None:
        normalized_code = self._validate_currency_code(code)
        normalized_symbol = (symbol or "").strip()
        validated_scale = self._validate_scale(scale)
        try:
            self._currency_repo.update_currency(
                currency_id,
                normalized_code,
                normalized_symbol,
                validated_scale,
                is_active,
            )
        except NotFoundError as exc:
            raise ValidationError(str(exc)) from exc
        except RepositoryError as exc:
            raise ValidationError(str(exc)) from exc

    def delete_currency(self, currency_id: int) -> None:
        try:
            self._currency_repo.soft_delete_currency(currency_id)
        except NotFoundError as exc:
            raise ValidationError("Silinecek para birimi bulunamadı.") from exc
        except RepositoryError as exc:
            raise AppError(str(exc)) from exc

    # --- Kategori ---

    def list_categories(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        return self._category_repo.list_categories(include_inactive=include_inactive)

    def create_category(
        self,
        name: str,
        nature: str,
        parent_id: Optional[int] = None,
    ) -> int:
        normalized_name = self._validate_category_name(name)
        normalized_nature = self._validate_category_nature(nature)
        self._validate_parent_category(parent_id)
        try:
            return self._category_repo.create_category(
                normalized_name,
                normalized_nature,
                parent_id,
            )
        except RepositoryError as exc:
            raise ValidationError(str(exc)) from exc

    def update_category(
        self,
        category_id: int,
        name: str,
        nature: str,
        parent_id: Optional[int],
        is_active: bool,
    ) -> None:
        normalized_name = self._validate_category_name(name)
        normalized_nature = self._validate_category_nature(nature)
        self._validate_parent_category(parent_id, category_id=category_id)
        try:
            self._category_repo.update_category(
                category_id,
                normalized_name,
                normalized_nature,
                parent_id,
                is_active,
            )
        except NotFoundError as exc:
            raise ValidationError(str(exc)) from exc
        except RepositoryError as exc:
            raise ValidationError(str(exc)) from exc

    def delete_category(self, category_id: int) -> None:
        try:
            self._category_repo.soft_delete_category(category_id)
        except NotFoundError as exc:
            raise ValidationError("Silinecek kategori bulunamadı.") from exc
        except RepositoryError as exc:
            raise AppError(str(exc)) from exc

    # --- Varlık ---

    def list_assets(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        return self._asset_repo.list_assets(include_inactive=include_inactive)

    def create_asset(self, name: str, type_: str) -> int:
        normalized_name = self._validate_asset_name(name)
        normalized_type = (type_ or "other").strip() or "other"
        try:
            return self._asset_repo.create_asset(normalized_name, normalized_type)
        except RepositoryError as exc:
            raise ValidationError(str(exc)) from exc

    def update_asset(self, asset_id: int, name: str, type_: str, is_active: bool) -> None:
        normalized_name = self._validate_asset_name(name)
        normalized_type = (type_ or "other").strip() or "other"
        try:
            self._asset_repo.update_asset(asset_id, normalized_name, normalized_type, is_active)
        except NotFoundError as exc:
            raise ValidationError(str(exc)) from exc
        except RepositoryError as exc:
            raise ValidationError(str(exc)) from exc

    def delete_asset(self, asset_id: int) -> None:
        try:
            self._asset_repo.soft_delete_asset(asset_id)
        except NotFoundError as exc:
            raise ValidationError("Silinecek varlık bulunamadı.") from exc
        except RepositoryError as exc:
            raise AppError(str(exc)) from exc

    # --- Bileşen tipi ---

    def list_component_types(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        return self._component_type_repo.list_component_types(include_inactive=include_inactive)

    def create_component_type(
        self,
        code: str,
        name: str,
        nature: str,
        default_category_id: Optional[int] = None,
    ) -> int:
        normalized_code = self._validate_component_code(code)
        normalized_name = self._validate_component_name(name)
        normalized_nature = self._validate_component_nature(nature)
        validated_category_id = self._validate_component_default_category(
            normalized_nature,
            default_category_id,
        )
        try:
            return self._component_type_repo.create_component_type(
                normalized_code,
                normalized_name,
                normalized_nature,
                validated_category_id,
            )
        except RepositoryError as exc:
            raise ValidationError(str(exc)) from exc

    def update_component_type(
        self,
        component_type_id: int,
        code: str,
        name: str,
        nature: str,
        is_active: bool,
        default_category_id: Optional[int] = None,
    ) -> None:
        normalized_code = self._validate_component_code(code)
        normalized_name = self._validate_component_name(name)
        normalized_nature = self._validate_component_nature(nature)
        validated_category_id = self._validate_component_default_category(
            normalized_nature,
            default_category_id,
        )
        try:
            self._component_type_repo.update_component_type(
                component_type_id,
                normalized_code,
                normalized_name,
                normalized_nature,
                is_active,
                validated_category_id,
            )
        except NotFoundError as exc:
            raise ValidationError(str(exc)) from exc
        except RepositoryError as exc:
            raise ValidationError(str(exc)) from exc

    def delete_component_type(self, component_type_id: int) -> None:
        try:
            self._component_type_repo.soft_delete_component_type(component_type_id)
        except NotFoundError as exc:
            raise ValidationError("Silinecek bileşen tipi bulunamadı.") from exc
        except RepositoryError as exc:
            raise AppError(str(exc)) from exc

    # --- Validasyon yardımcıları ---

    def _validate_currency_code(self, code: str) -> str:
        if not is_non_empty_text(code):
            raise ValidationError("Para birimi kodu boş olamaz.")
        return code.strip().upper()

    def _validate_scale(self, scale: int) -> int:
        if not isinstance(scale, int):
            raise ValidationError("Scale değeri tam sayı olmalıdır.")
        if scale < self.MIN_SCALE or scale > self.MAX_SCALE:
            raise ValidationError(f"Scale {self.MIN_SCALE} ile {self.MAX_SCALE} arasında olmalıdır.")
        return scale

    def _validate_category_name(self, name: str) -> str:
        if not is_non_empty_text(name):
            raise ValidationError("Kategori adı boş olamaz.")
        return name.strip()

    def _validate_category_nature(self, nature: str) -> str:
        normalized = (nature or "").strip().lower()
        if normalized not in VALID_CATEGORY_NATURES:
            raise ValidationError(
                "Kategori niteliği yalnızca gelir, gider veya masraf olabilir."
            )
        return normalized

    def _validate_component_code(self, code: str) -> str:
        if not is_non_empty_text(code):
            raise ValidationError("Bileşen tipi kodu boş olamaz.")
        return code.strip().lower()

    def _validate_component_name(self, name: str) -> str:
        if not is_non_empty_text(name):
            raise ValidationError("Bileşen tipi adı boş olamaz.")
        return name.strip()

    def _validate_component_nature(self, nature: str) -> str:
        normalized = (nature or "").strip().lower()
        if normalized not in VALID_COMPONENT_NATURES:
            raise ValidationError(
                "Bileşen tipi niteliği yalnızca anapara veya gider olabilir."
            )
        return normalized

    def _validate_asset_name(self, name: str) -> str:
        if not is_non_empty_text(name):
            raise ValidationError("Varlık adı boş olamaz.")
        return name.strip()

    def _validate_parent_category(
        self,
        parent_id: Optional[int],
        category_id: Optional[int] = None,
    ) -> None:
        if parent_id is None:
            return
        if category_id is not None and parent_id == category_id:
            raise ValidationError("Kategori kendi üst kategorisi olamaz.")
        parent = self._category_repo.get_category(parent_id)
        if parent is None:
            raise ValidationError("Seçilen üst kategori bulunamadı.")

    def _validate_component_default_category(
        self,
        component_nature: str,
        default_category_id: Optional[int],
    ) -> Optional[int]:
        if component_nature == Nature.PRINCIPAL:
            if default_category_id is not None:
                raise ValidationError("Anapara bileşen tipi için gider kategorisi seçilemez.")
            return None
        if default_category_id is None:
            return None
        category = self._category_repo.get_category(int(default_category_id))
        if category is None:
            raise ValidationError("Seçilen varsayılan gider kategorisi bulunamadı.")
        if category["nature"] != Nature.EXPENSE:
            raise ValidationError("Varsayılan kategori niteliği gider olmalıdır.")
        return int(default_category_id)

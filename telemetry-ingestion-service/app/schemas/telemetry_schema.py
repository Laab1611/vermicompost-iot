from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, field_validator


class CamaCreate(BaseModel):
    nombre: str
    ubicacion: str
    latitud: Optional[Decimal] = None
    longitud: Optional[Decimal] = None

    @field_validator("nombre", "ubicacion")
    @classmethod
    def required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("El campo no puede ser vacio")
        return cleaned

    @field_validator("latitud")
    @classmethod
    def valid_latitude(cls, value: Optional[Decimal]) -> Optional[Decimal]:
        if value is not None and (value < Decimal("-90") or value > Decimal("90")):
            raise ValueError("Latitud fuera de rango")
        return value

    @field_validator("longitud")
    @classmethod
    def valid_longitude(cls, value: Optional[Decimal]) -> Optional[Decimal]:
        if value is not None and (value < Decimal("-180") or value > Decimal("180")):
            raise ValueError("Longitud fuera de rango")
        return value


class CamaUpdate(CamaCreate):
    pass


class CamaResponse(CamaCreate):
    cama_id: int
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class NodoCreate(BaseModel):
    cama_id: int
    codigo_nodo: str

    @field_validator("codigo_nodo")
    @classmethod
    def non_empty_code(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("codigo_nodo no puede ser vacio")
        return cleaned


class NodoUpdate(BaseModel):
    cama_id: int
    codigo_nodo: str


class NodoResponse(BaseModel):
    nodo_id: int
    cama_id: int
    codigo_nodo: str
    ultima_lectura_recibida: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TipoVariableCreate(BaseModel):
    nombre: str
    unidad_medida: str

    @field_validator("nombre", "unidad_medida")
    @classmethod
    def non_empty_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("El campo no puede ser vacio")
        return cleaned


class TipoVariableUpdate(TipoVariableCreate):
    pass


class TipoVariableResponse(TipoVariableCreate):
    tipo_variable_id: int

    model_config = {"from_attributes": True}


class LecturaCreate(BaseModel):
    nodo_id: int
    tipo_variable_id: int
    valor: Decimal
    fecha_medicion: datetime
    fecha_recepcion: Optional[datetime] = None

    @field_validator("valor", mode="before")
    @classmethod
    def parse_decimal_value(cls, value: object) -> Decimal:
        try:
            return Decimal(str(value))
        except Exception as exc:
            raise ValueError("valor debe ser decimal") from exc


class LecturaUpdate(LecturaCreate):
    pass


class LecturaResponse(BaseModel):
    lectura_id: int
    nodo_id: int
    tipo_variable_id: int
    valor: Decimal
    fecha_medicion: datetime
    fecha_recepcion: datetime

    model_config = {"from_attributes": True}


class IngestionCreate(BaseModel):
    nodo_id: int
    tipo_variable_id: int
    valor: Decimal
    fecha_medicion: datetime
    fecha_recepcion: Optional[datetime] = None

    @field_validator("valor", mode="before")
    @classmethod
    def parse_decimal_value(cls, value: object) -> Decimal:
        try:
            return Decimal(str(value))
        except Exception as exc:
            raise ValueError("valor debe ser decimal") from exc


class IngestionResponse(BaseModel):
    message: str
    lectura_id: Optional[int] = None
    es_valida: bool
    motivo_invalidacion: Optional[str] = None
    persistida: bool
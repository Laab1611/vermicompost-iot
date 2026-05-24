from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class CamaResponse(BaseModel):
    cama_id: int
    nombre: str
    ubicacion: str
    latitud: Optional[Decimal] = None
    longitud: Optional[Decimal] = None

    model_config = {"from_attributes": True}


class NodoResponse(BaseModel):
    nodo_id: int
    cama_id: int
    codigo_nodo: str
    created_at: Optional[datetime] = None
    ultima_lectura_recibida: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TipoVariableResponse(BaseModel):
    tipo_variable_id: int
    nombre: str
    unidad_medida: str

    model_config = {"from_attributes": True}


class LecturaDetalle(BaseModel):
    lectura_id: int
    nodo_id: Optional[int] = None
    cama_id: Optional[int] = None
    codigo_nodo: Optional[str] = None
    tipo_variable_id: Optional[int] = None
    tipo_variable: Optional[str] = None
    unidad_medida: Optional[str] = None
    valor: Decimal | str
    fecha_medicion: datetime | str
    fecha_recepcion: datetime
    es_valida: bool
    motivo_invalidacion: Optional[str] = None


class NodoEstado(BaseModel):
    nodo_id: int
    cama_id: int
    codigo_nodo: str
    ultima_lectura_recibida: Optional[datetime] = None
    conectado: bool
    lecturas_actuales: dict[str, Optional[Decimal]]


class NodoEstadoResumen(BaseModel):
    nodo_id: int
    codigo_nodo: str
    conectado: bool


class CamaEstado(BaseModel):
    cama_id: int
    nombre: str
    nodos: list[NodoEstado]


class CamaEstadoResumen(BaseModel):
    cama_id: int
    nombre: str
    nodos: list[NodoEstadoResumen]


class MonitoringSummary(BaseModel):
    total_camas: int
    total_nodos: int
    nodos_conectados: int
    nodos_desconectados: int
    lecturas_invalidas: int
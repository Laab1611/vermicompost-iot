from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class NodoTwinState(BaseModel):
    nodo_id: int
    cama_id: int
    codigo_nodo: str
    ultima_lectura_recibida: Optional[datetime] = None
    lecturas_actuales: dict[str, Optional[Decimal]]


class CamaTwinState(BaseModel):
    cama_id: int
    nombre: str
    nodos: list[NodoTwinState]


class TwinOverview(BaseModel):
    total_camas: int
    total_nodos: int
    lecturas_validas: int
    lecturas_invalidas: int

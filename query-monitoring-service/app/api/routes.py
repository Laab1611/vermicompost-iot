from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.exceptions import NotFoundError, PersistenceError, ValidationError
from app.schemas.query_schema import (
    CamaEstado,
    CamaEstadoResumen,
    LecturaDetalle,
    MonitoringSummary,
    NodoEstado,
    NodoResponse,
    TipoVariableResponse,
)
from app.services import query_service

router = APIRouter()


def _rows_to_lecturas(rows) -> list[LecturaDetalle]:
    return [
        LecturaDetalle(
            lectura_id=r[0],
            nodo_id=r[1],
            cama_id=r[2],
            codigo_nodo=r[3],
            tipo_variable_id=r[4],
            tipo_variable=r[5],
            unidad_medida=r[6],
            valor=r[7],
            fecha_medicion=r[8],
            fecha_recepcion=r[9],
            es_valida=r[10],
            motivo_invalidacion=r[11],
        )
        for r in rows
    ]


@router.get("/health")
def health():
    return {"status": "ok", "service": "query-monitoring-service"}


@router.get("/api/v1/camas", response_model=list[CamaEstadoResumen])
def get_camas(
    minutes: int = Query(15, ge=1, le=43200),
    db: Session = Depends(get_db),
):
    try:
        return query_service.get_all_camas_estado(db, minutes)
    except PersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/v1/nodos", response_model=list[NodoResponse])
def get_nodos(db: Session = Depends(get_db)):
    try:
        return query_service.list_nodos(db)
    except PersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/v1/tipos-variable", response_model=list[TipoVariableResponse])
def get_tipos_variable(db: Session = Depends(get_db)):
    try:
        return query_service.list_tipos_variable(db)
    except PersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/v1/lecturas/historico/nodo/{nodo_id}", response_model=list[LecturaDetalle])
def get_lecturas_nodo(
    nodo_id: int = Path(..., ge=1),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    try:
        rows = query_service.get_lecturas_by_nodo(db, nodo_id, limit)
        return _rows_to_lecturas(rows)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/v1/lecturas/historico/cama/{cama_id}", response_model=list[LecturaDetalle])
def get_lecturas_cama(
    cama_id: int = Path(..., ge=1),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    try:
        rows = query_service.get_lecturas_by_cama(db, cama_id, limit)
        return _rows_to_lecturas(rows)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/v1/lecturas/historico/tipo-variable/{tipo_variable_id}", response_model=list[LecturaDetalle])
def get_lecturas_tipo(
    tipo_variable_id: int = Path(..., ge=1),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    try:
        rows = query_service.get_lecturas_by_tipo_variable(db, tipo_variable_id, limit)
        return _rows_to_lecturas(rows)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/v1/lecturas/historico/rango-tiempo", response_model=list[LecturaDetalle])
def get_lecturas_rango(
    start: datetime,
    end: datetime,
    limit: int = Query(300, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    try:
        rows = query_service.get_lecturas_by_rango(db, start, end, limit)
        return _rows_to_lecturas(rows)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/v1/estado/nodo/{nodo_id}", response_model=NodoEstado)
def get_estado_nodo(
    nodo_id: int = Path(..., ge=1),
    minutes: int = Query(15, ge=1, le=43200),
    db: Session = Depends(get_db),
):
    try:
        return query_service.get_estado_actual_por_nodo(db, nodo_id, minutes)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/v1/estado/cama/{cama_id}", response_model=CamaEstado)
def get_estado_cama(
    cama_id: int = Path(..., ge=1),
    minutes: int = Query(15, ge=1, le=43200),
    db: Session = Depends(get_db),
):
    try:
        return query_service.get_estado_actual_por_cama(db, cama_id, minutes)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/v1/lecturas/invalidas", response_model=list[LecturaDetalle])
def get_invalid_readings(limit: int = Query(300, ge=1, le=1000), db: Session = Depends(get_db)):
    try:
        rows = query_service.get_lecturas_invalidas(db, limit)
        return _rows_to_lecturas(rows)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/v1/nodos/desconectados", response_model=list[NodoResponse])
def get_disconnected_nodes(minutes: int = Query(15, ge=1, le=43200), db: Session = Depends(get_db)):
    try:
        return query_service.get_nodos_desconectados(db, minutes)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/v1/monitoring/summary", response_model=MonitoringSummary)
def get_summary(db: Session = Depends(get_db)):
    try:
        return query_service.get_monitoring_summary(db)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
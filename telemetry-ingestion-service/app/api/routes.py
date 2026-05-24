from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.exceptions import ConflictError, DependencyError, NotFoundError, PersistenceError, ValidationError
from app.schemas.telemetry_schema import (
    CamaCreate,
    CamaResponse,
    CamaUpdate,
    IngestionResponse,
    LecturaCreate,
    LecturaResponse,
    LecturaUpdate,
    NodoCreate,
    NodoResponse,
    NodoUpdate,
    TipoVariableCreate,
    TipoVariableResponse,
    TipoVariableUpdate,
)
from app.services import telemetry_service

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok", "service": "telemetry-ingestion-service"}


@router.post("/api/v1/ingestion", response_model=IngestionResponse)
def ingest_telemetry(payload: dict, db: Session = Depends(get_db)):
    try:
        return IngestionResponse(**telemetry_service.ingest_telemetry_request(db, payload))
    except PersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/v1/camas", response_model=CamaResponse)
def create_cama(payload: CamaCreate, db: Session = Depends(get_db)):
    try:
        return telemetry_service.create_cama(db, payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/v1/camas", response_model=list[CamaResponse])
def list_camas(db: Session = Depends(get_db)):
    return telemetry_service.list_camas(db)


@router.get("/api/v1/camas/{cama_id}", response_model=CamaResponse)
def get_cama(cama_id: int, db: Session = Depends(get_db)):
    try:
        return telemetry_service.get_cama_or_fail(db, cama_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/api/v1/camas/{cama_id}", response_model=CamaResponse)
def update_cama(cama_id: int, payload: CamaUpdate, db: Session = Depends(get_db)):
    try:
        return telemetry_service.update_cama(db, cama_id, payload)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/api/v1/camas/{cama_id}")
def delete_cama(cama_id: int, db: Session = Depends(get_db)):
    try:
        telemetry_service.delete_cama(db, cama_id)
        return {"message": "Cama eliminada"}
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DependencyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/v1/nodos", response_model=NodoResponse)
def create_nodo(payload: NodoCreate, db: Session = Depends(get_db)):
    try:
        return telemetry_service.create_nodo(db, payload)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/v1/nodos", response_model=list[NodoResponse])
def list_nodos(db: Session = Depends(get_db)):
    return telemetry_service.list_nodos(db)


@router.get("/api/v1/nodos/{nodo_id}", response_model=NodoResponse)
def get_nodo(nodo_id: int, db: Session = Depends(get_db)):
    try:
        return telemetry_service.get_nodo_or_fail(db, nodo_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/api/v1/nodos/{nodo_id}", response_model=NodoResponse)
def update_nodo(nodo_id: int, payload: NodoUpdate, db: Session = Depends(get_db)):
    try:
        return telemetry_service.update_nodo(db, nodo_id, payload)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/api/v1/nodos/{nodo_id}")
def delete_nodo(nodo_id: int, db: Session = Depends(get_db)):
    try:
        telemetry_service.delete_nodo(db, nodo_id)
        return {"message": "Nodo eliminado"}
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DependencyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/v1/tipos-variable", response_model=TipoVariableResponse)
def create_tipo_variable(payload: TipoVariableCreate, db: Session = Depends(get_db)):
    try:
        return telemetry_service.create_tipo_variable(db, payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/v1/tipos-variable", response_model=list[TipoVariableResponse])
def list_tipos_variable(db: Session = Depends(get_db)):
    return telemetry_service.list_tipos_variable(db)


@router.get("/api/v1/tipos-variable/{tipo_variable_id}", response_model=TipoVariableResponse)
def get_tipo_variable(tipo_variable_id: int, db: Session = Depends(get_db)):
    try:
        return telemetry_service.get_tipo_variable_or_fail(db, tipo_variable_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/api/v1/tipos-variable/{tipo_variable_id}", response_model=TipoVariableResponse)
def update_tipo_variable(tipo_variable_id: int, payload: TipoVariableUpdate, db: Session = Depends(get_db)):
    try:
        return telemetry_service.update_tipo_variable(db, tipo_variable_id, payload)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/api/v1/tipos-variable/{tipo_variable_id}")
def delete_tipo_variable(tipo_variable_id: int, db: Session = Depends(get_db)):
    try:
        telemetry_service.delete_tipo_variable(db, tipo_variable_id)
        return {"message": "Tipo de variable eliminado"}
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DependencyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/v1/lecturas", response_model=LecturaResponse)
def create_lectura(payload: LecturaCreate, db: Session = Depends(get_db)):
    try:
        return telemetry_service.create_lectura(db, payload)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/v1/lecturas", response_model=list[LecturaResponse])
def list_lecturas(db: Session = Depends(get_db)):
    return telemetry_service.list_lecturas(db)


@router.get("/api/v1/lecturas/{lectura_id}", response_model=LecturaResponse)
def get_lectura(lectura_id: int, db: Session = Depends(get_db)):
    try:
        return telemetry_service.get_lectura_or_fail(db, lectura_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/api/v1/lecturas/{lectura_id}", response_model=LecturaResponse)
def update_lectura(lectura_id: int, payload: LecturaUpdate, db: Session = Depends(get_db)):
    try:
        return telemetry_service.update_lectura(db, lectura_id, payload)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/api/v1/lecturas/{lectura_id}")
def delete_lectura(lectura_id: int, db: Session = Depends(get_db)):
    try:
        telemetry_service.delete_lectura(db, lectura_id)
        return {"message": "Lectura eliminada"}
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
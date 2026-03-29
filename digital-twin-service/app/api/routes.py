from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.exceptions import NotFoundError, PersistenceError, ValidationError
from app.schemas.digital_schema import CamaTwinState, NodoTwinState, TwinOverview
from app.services import digital_service

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok", "service": "digital-twin-service"}


@router.get("/api/v1/twins/overview", response_model=TwinOverview)
def get_overview(db: Session = Depends(get_db)):
    return digital_service.get_twin_overview(db)


@router.get("/api/v1/twins", response_model=list[CamaTwinState])
def get_all_twins(
    readings_limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    try:
        return digital_service.get_all_camas_twin_state(db, readings_limit)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/v1/twins/camas/{cama_id}", response_model=CamaTwinState)
def get_cama_twin(
    cama_id: int = Path(..., ge=1),
    readings_limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    try:
        return digital_service.get_cama_twin_state(db, cama_id, readings_limit)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/v1/twins/nodos/{nodo_id}", response_model=NodoTwinState)
def get_nodo_twin(
    nodo_id: int = Path(..., ge=1),
    readings_limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    try:
        return digital_service.get_nodo_twin_state(db, nodo_id, readings_limit)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

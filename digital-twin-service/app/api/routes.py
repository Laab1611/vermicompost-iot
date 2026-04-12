import logging

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.exceptions import NotFoundError, PersistenceError, ValidationError
from app.schemas.digital_schema import CamaTwinState, NodoTwinState, TwinOverview
from app.services import digital_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
def health():
    return {"status": "ok", "service": "digital-twin-service"}


@router.get("/api/v1/twins/overview", response_model=TwinOverview)
def get_overview(db: Session = Depends(get_db)):
    try:
        result = digital_service.get_twin_overview(db)
        logger.info(
            "Digital twin overview requested: total_camas=%s total_nodos=%s",
            result["total_camas"],
            result["total_nodos"],
        )
        return result
    except PersistenceError as exc:
        logger.exception("Digital twin overview failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/v1/twins", response_model=list[CamaTwinState])
def get_all_twins(
    readings_limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    try:
        result = digital_service.get_all_camas_twin_state(db, readings_limit)
        logger.info("Digital twin list requested: camas=%s readings_limit=%s", len(result), readings_limit)
        return result
    except ValidationError as exc:
        logger.warning("Digital twin list validation error: readings_limit=%s", readings_limit)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PersistenceError as exc:
        logger.exception("Digital twin list failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/v1/twins/camas/{cama_id}", response_model=CamaTwinState)
def get_cama_twin(
    cama_id: int = Path(..., ge=1),
    readings_limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    try:
        result = digital_service.get_cama_twin_state(db, cama_id, readings_limit)
        logger.info(
            "Digital twin cama requested: cama_id=%s nodos=%s readings_limit=%s",
            cama_id,
            len(result["nodos"]),
            readings_limit,
        )
        return result
    except NotFoundError as exc:
        logger.warning("Digital twin cama not found: cama_id=%s", cama_id)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        logger.warning("Digital twin cama validation error: cama_id=%s readings_limit=%s", cama_id, readings_limit)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PersistenceError as exc:
        logger.exception("Digital twin cama failed: cama_id=%s", cama_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/v1/twins/nodos/{nodo_id}", response_model=NodoTwinState)
def get_nodo_twin(
    nodo_id: int = Path(..., ge=1),
    readings_limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    try:
        result = digital_service.get_nodo_twin_state(db, nodo_id, readings_limit)
        logger.info(
            "Digital twin nodo requested: nodo_id=%s lecturas_actuales=%s readings_limit=%s",
            nodo_id,
            len(result["lecturas_actuales"]),
            readings_limit,
        )
        return result
    except NotFoundError as exc:
        logger.warning("Digital twin nodo not found: nodo_id=%s", nodo_id)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        logger.warning("Digital twin nodo validation error: nodo_id=%s readings_limit=%s", nodo_id, readings_limit)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PersistenceError as exc:
        logger.exception("Digital twin nodo failed: nodo_id=%s", nodo_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

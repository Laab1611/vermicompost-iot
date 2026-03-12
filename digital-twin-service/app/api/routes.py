from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.digital_schema import TwinUpdateRequest, TwinResponse, SystemStateResponse
from app.services import digital_service

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok", "service": "digital-twin-service"}


@router.post("/api/v1/twins/update")
def update_twin(payload: TwinUpdateRequest, db: Session = Depends(get_db)):
    digital_service.update_twin(db, payload)
    return {"message": "Digital twin updated successfully"}


@router.get("/api/v1/twins/system-state", response_model=SystemStateResponse)
def get_system_state(db: Session = Depends(get_db)):
    return digital_service.get_system_state(db)


@router.get("/api/v1/twins")
def get_all_twins(db: Session = Depends(get_db)):
    twins = digital_service.get_all_twins(db)
    return [digital_service.to_response(t) for t in twins]


@router.get("/api/v1/twins/{device_id}", response_model=TwinResponse)
def get_twin(device_id: int, db: Session = Depends(get_db)):
    twin = digital_service.get_twin(db, device_id)
    if not twin:
        raise HTTPException(status_code=404, detail="Digital twin not found")
    return digital_service.to_response(twin)


@router.post("/api/v1/twins/{device_id}/recalculate")
def recalculate(device_id: int, db: Session = Depends(get_db)):
    twin = digital_service.recalculate_twin(db, device_id)
    if not twin:
        raise HTTPException(status_code=404, detail="Digital twin not found")
    return {"message": "Digital twin recalculated", "risk_level": twin.risk_level}

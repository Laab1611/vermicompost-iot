from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database.connection import get_db
from app.schemas.telemetry_schema import (
    TelemetryCreate,
    TelemetryResponse,
    TelemetryBatchResponse,
    TelemetryValidateResponse,
)
from app.services import telemetry_service

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok", "service": "telemetry-ingestion-service"}


@router.post("/api/v1/telemetry", response_model=TelemetryResponse)
def ingest_telemetry(payload: TelemetryCreate, db: Session = Depends(get_db)):
    record = telemetry_service.save_telemetry(db, payload)
    data = payload.model_dump(mode="json")
    telemetry_service.notify_alert_service(data)
    telemetry_service.notify_digital_twin_service(data)
    return TelemetryResponse(message="Telemetry received successfully", telemetry_id=record.id)


@router.post("/api/v1/telemetry/batch", response_model=TelemetryBatchResponse)
def ingest_batch(payloads: List[TelemetryCreate], db: Session = Depends(get_db)):
    ids = []
    for payload in payloads:
        record = telemetry_service.save_telemetry(db, payload)
        ids.append(record.id)
        data = payload.model_dump(mode="json")
        telemetry_service.notify_alert_service(data)
        telemetry_service.notify_digital_twin_service(data)
    return TelemetryBatchResponse(
        message=f"{len(ids)} telemetry records received",
        telemetry_ids=ids,
    )


@router.post("/api/v1/telemetry/validate", response_model=TelemetryValidateResponse)
def validate_telemetry(payload: TelemetryCreate):
    telemetry_service.normalize(payload)
    return TelemetryValidateResponse(valid=True, normalized=True)
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from app.database.connection import get_db
from app.schemas.query_schema import (
    DeviceResponse,
    TelemetryReading,
    MonitoringSummary,
)
from app.services import query_service

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok", "service": "query-monitoring-service"}


# Note: static paths (/status) must be declared before parameterized paths (/{device_id})
@router.get("/api/v1/devices")
def get_devices(db: Session = Depends(get_db)):
    devices = query_service.get_all_devices(db)
    return [DeviceResponse.model_validate(d) for d in devices]


@router.get("/api/v1/devices/status")
def get_devices_status(db: Session = Depends(get_db)):
    return query_service.get_devices_status(db)


@router.get("/api/v1/devices/{device_id}")
def get_device(device_id: int, db: Session = Depends(get_db)):
    device = query_service.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return DeviceResponse.model_validate(device)


@router.get("/api/v1/devices/{device_id}/latest")
def get_latest(device_id: int, db: Session = Depends(get_db)):
    reading = query_service.get_latest_reading(db, device_id)
    if not reading:
        raise HTTPException(status_code=404, detail="No readings found for this device")
    return TelemetryReading.model_validate(reading)


@router.get("/api/v1/devices/{device_id}/history")
def get_history(
    device_id: int,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    readings = query_service.get_device_history(db, device_id, start, end, limit)
    return [TelemetryReading.model_validate(r) for r in readings]


@router.get("/api/v1/monitoring/summary", response_model=MonitoringSummary)
def get_summary(db: Session = Depends(get_db)):
    return query_service.get_monitoring_summary(db)


@router.get("/api/v1/telemetry/recent")
def get_recent_telemetry(limit: int = 50, db: Session = Depends(get_db)):
    readings = query_service.get_recent_telemetry(db, limit)
    return [TelemetryReading.model_validate(r) for r in readings]
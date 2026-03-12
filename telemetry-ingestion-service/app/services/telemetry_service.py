import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models.telemetry_model import Device, Telemetry
from app.schemas.telemetry_schema import TelemetryCreate


def normalize(data: TelemetryCreate) -> TelemetryCreate:
    updates = {}
    if data.temperature is not None:
        updates["temperature"] = round(data.temperature, 2)
    if data.humidity is not None:
        updates["humidity"] = round(data.humidity, 2)
    if data.soil_moisture is not None:
        updates["soil_moisture"] = round(data.soil_moisture, 2)
    if data.ph is not None:
        updates["ph"] = round(data.ph, 2)
    return data.model_copy(update=updates) if updates else data


def save_telemetry(db: Session, data: TelemetryCreate) -> Telemetry:
    data = normalize(data)
    # Auto-register device if not present
    device = db.query(Device).filter(Device.id == data.device_id).first()
    if not device:
        device = Device(id=data.device_id, name=f"device-{data.device_id}")
        db.add(device)
        db.flush()
    record = Telemetry(
        device_id=data.device_id,
        temperature=data.temperature,
        humidity=data.humidity,
        soil_moisture=data.soil_moisture,
        ph=data.ph,
        timestamp=data.timestamp,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def notify_alert_service(payload: dict) -> None:
    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(f"{settings.ALERT_SERVICE_URL}/api/v1/alerts/evaluate", json=payload)
    except Exception:
        pass


def notify_digital_twin_service(payload: dict) -> None:
    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(f"{settings.DIGITAL_TWIN_SERVICE_URL}/api/v1/twins/update", json=payload)
    except Exception:
        pass
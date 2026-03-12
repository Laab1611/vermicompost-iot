from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from app.models.query_model import Device, Telemetry, Alert


def get_all_devices(db: Session) -> List[Device]:
    return db.query(Device).all()


def get_device_by_id(db: Session, device_id: int) -> Optional[Device]:
    return db.query(Device).filter(Device.id == device_id).first()


def get_latest_reading(db: Session, device_id: int) -> Optional[Telemetry]:
    return (
        db.query(Telemetry)
        .filter(Telemetry.device_id == device_id)
        .order_by(desc(Telemetry.timestamp))
        .first()
    )


def get_device_history(
    db: Session,
    device_id: int,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = 100,
) -> List[Telemetry]:
    query = db.query(Telemetry).filter(Telemetry.device_id == device_id)
    if start:
        query = query.filter(Telemetry.timestamp >= start)
    if end:
        query = query.filter(Telemetry.timestamp <= end)
    return query.order_by(desc(Telemetry.timestamp)).limit(limit).all()


def get_devices_status(db: Session) -> List[dict]:
    devices = db.query(Device).all()
    threshold = datetime.now(timezone.utc) - timedelta(minutes=5)
    result = []
    for device in devices:
        latest = (
            db.query(Telemetry)
            .filter(Telemetry.device_id == device.id)
            .order_by(desc(Telemetry.timestamp))
            .first()
        )
        last_seen = latest.timestamp if latest else None
        status = "online" if latest and latest.timestamp >= threshold else "offline"
        result.append({"device_id": device.id, "last_seen": last_seen, "status": status})
    return result


def get_monitoring_summary(db: Session) -> dict:
    total_devices = db.query(Device).count()
    threshold = datetime.now(timezone.utc) - timedelta(minutes=5)
    online_devices = (
        db.query(func.count(func.distinct(Telemetry.device_id)))
        .filter(Telemetry.timestamp >= threshold)
        .scalar()
        or 0
    )
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    total_readings_today = (
        db.query(Telemetry).filter(Telemetry.timestamp >= today_start).count()
    )
    active_alerts = db.query(Alert).filter(Alert.resolved == False).count()  # noqa: E712
    return {
        "total_devices": total_devices,
        "online_devices": online_devices,
        "total_readings_today": total_readings_today,
        "active_alerts": active_alerts,
    }


def get_recent_telemetry(db: Session, limit: int = 50) -> List[Telemetry]:
    return (
        db.query(Telemetry)
        .order_by(desc(Telemetry.timestamp))
        .limit(limit)
        .all()
    )
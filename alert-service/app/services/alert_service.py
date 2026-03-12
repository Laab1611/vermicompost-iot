from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import List, Optional

from app.models.alert_model import Alert, AlertRule
from app.schemas.alert_schema import TelemetryPayload, AlertItem, AlertRuleCreate

_DEFAULT_THRESHOLDS = {
    "temperature_max": 34.0,
    "humidity_min": 40.0,
    "soil_moisture_min": 30.0,
    "ph_min": 6.0,
    "ph_max": 8.0,
}


def _get_thresholds(db: Session) -> dict:
    rule = db.query(AlertRule).order_by(AlertRule.id.desc()).first()
    if not rule:
        return _DEFAULT_THRESHOLDS
    return {
        "temperature_max": rule.temperature_max or _DEFAULT_THRESHOLDS["temperature_max"],
        "humidity_min": rule.humidity_min or _DEFAULT_THRESHOLDS["humidity_min"],
        "soil_moisture_min": rule.soil_moisture_min or _DEFAULT_THRESHOLDS["soil_moisture_min"],
        "ph_min": rule.ph_min or _DEFAULT_THRESHOLDS["ph_min"],
        "ph_max": rule.ph_max or _DEFAULT_THRESHOLDS["ph_max"],
    }


def evaluate(db: Session, payload: TelemetryPayload) -> List[AlertItem]:
    t = _get_thresholds(db)
    alerts: List[AlertItem] = []

    if payload.temperature is not None and payload.temperature > t["temperature_max"]:
        alerts.append(AlertItem(
            type="HIGH_TEMPERATURE",
            level="warning",
            message=f"Temperature {payload.temperature} exceeded threshold {t['temperature_max']}",
        ))

    if payload.humidity is not None and payload.humidity < t["humidity_min"]:
        alerts.append(AlertItem(
            type="LOW_HUMIDITY",
            level="warning",
            message=f"Humidity {payload.humidity} below threshold {t['humidity_min']}",
        ))

    if payload.soil_moisture is not None and payload.soil_moisture < t["soil_moisture_min"]:
        alerts.append(AlertItem(
            type="LOW_SOIL_MOISTURE",
            level="critical",
            message=f"Soil moisture {payload.soil_moisture} below threshold {t['soil_moisture_min']}",
        ))

    if payload.ph is not None:
        if payload.ph > t["ph_max"]:
            alerts.append(AlertItem(
                type="HIGH_PH",
                level="warning",
                message=f"pH {payload.ph} above threshold {t['ph_max']}",
            ))
        if payload.ph < t["ph_min"]:
            alerts.append(AlertItem(
                type="LOW_PH",
                level="warning",
                message=f"pH {payload.ph} below threshold {t['ph_min']}",
            ))

    for item in alerts:
        db.add(Alert(
            device_id=payload.device_id,
            alert_type=item.type,
            level=item.level,
            message=item.message,
            resolved=False,
        ))
    if alerts:
        db.commit()

    return alerts


def get_all_alerts(
    db: Session,
    device_id: Optional[int] = None,
    level: Optional[str] = None,
    resolved: Optional[bool] = None,
) -> List[Alert]:
    query = db.query(Alert)
    if device_id is not None:
        query = query.filter(Alert.device_id == device_id)
    if level is not None:
        query = query.filter(Alert.level == level)
    if resolved is not None:
        query = query.filter(Alert.resolved == resolved)
    return query.order_by(Alert.created_at.desc()).all()


def get_active_alerts(db: Session) -> List[Alert]:
    return (
        db.query(Alert)
        .filter(Alert.resolved == False)  # noqa: E712
        .order_by(Alert.created_at.desc())
        .all()
    )


def get_alert_by_id(db: Session, alert_id: int) -> Optional[Alert]:
    return db.query(Alert).filter(Alert.id == alert_id).first()


def resolve_alert(db: Session, alert_id: int) -> Optional[Alert]:
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        return None
    alert.resolved = True
    alert.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)
    return alert


def get_rules(db: Session) -> Optional[AlertRule]:
    return db.query(AlertRule).order_by(AlertRule.id.desc()).first()


def create_rules(db: Session, data: AlertRuleCreate) -> AlertRule:
    rule = AlertRule(**data.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.database.connection import get_db
from app.schemas.alert_schema import (
    TelemetryPayload,
    AlertEvaluateResponse,
    AlertResponse,
    AlertRuleCreate,
    AlertRuleResponse,
)
from app.services import alert_service

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok", "service": "alert-service"}


@router.post("/api/v1/alerts/evaluate", response_model=AlertEvaluateResponse)
def evaluate_alerts(payload: TelemetryPayload, db: Session = Depends(get_db)):
    alerts = alert_service.evaluate(db, payload)
    return AlertEvaluateResponse(alerts_generated=len(alerts), alerts=alerts)


@router.get("/api/v1/alerts/active")
def get_active_alerts(db: Session = Depends(get_db)):
    alerts = alert_service.get_active_alerts(db)
    return [AlertResponse.model_validate(a) for a in alerts]


@router.get("/api/v1/alerts/rules")
def get_rules(db: Session = Depends(get_db)):
    rule = alert_service.get_rules(db)
    if not rule:
        return {}
    return AlertRuleResponse.model_validate(rule)


@router.post("/api/v1/alerts/rules", response_model=AlertRuleResponse)
def create_rules(data: AlertRuleCreate, db: Session = Depends(get_db)):
    rule = alert_service.create_rules(db, data)
    return AlertRuleResponse.model_validate(rule)


@router.get("/api/v1/alerts")
def get_alerts(
    device_id: Optional[int] = None,
    level: Optional[str] = None,
    resolved: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    alerts = alert_service.get_all_alerts(db, device_id, level, resolved)
    return [AlertResponse.model_validate(a) for a in alerts]


@router.get("/api/v1/alerts/{alert_id}", response_model=AlertResponse)
def get_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = alert_service.get_alert_by_id(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertResponse.model_validate(alert)


@router.patch("/api/v1/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = alert_service.resolve_alert(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"message": "Alert resolved successfully"}

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class TelemetryPayload(BaseModel):
    device_id: int
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    soil_moisture: Optional[float] = None
    ph: Optional[float] = None
    timestamp: datetime


class AlertItem(BaseModel):
    type: str
    level: str
    message: str


class AlertEvaluateResponse(BaseModel):
    alerts_generated: int
    alerts: List[AlertItem]


class AlertResponse(BaseModel):
    id: int
    device_id: int
    alert_type: str
    level: str
    message: Optional[str] = None
    resolved: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AlertRuleCreate(BaseModel):
    temperature_max: Optional[float] = None
    humidity_min: Optional[float] = None
    soil_moisture_min: Optional[float] = None
    ph_min: Optional[float] = None
    ph_max: Optional[float] = None


class AlertRuleResponse(BaseModel):
    id: int
    temperature_max: Optional[float] = None
    humidity_min: Optional[float] = None
    soil_moisture_min: Optional[float] = None
    ph_min: Optional[float] = None
    ph_max: Optional[float] = None

    model_config = {"from_attributes": True}

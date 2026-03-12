from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class TwinUpdateRequest(BaseModel):
    device_id: int
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    soil_moisture: Optional[float] = None
    ph: Optional[float] = None
    timestamp: Optional[datetime] = None


class TwinState(BaseModel):
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    soil_moisture: Optional[float] = None
    ph: Optional[float] = None


class TwinResponse(BaseModel):
    device_id: int
    current_state: TwinState
    risk_level: str
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SystemStateResponse(BaseModel):
    total_units: int
    healthy_units: int
    warning_units: int
    critical_units: int

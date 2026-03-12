from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class TelemetryCreate(BaseModel):
    device_id: int
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    soil_moisture: Optional[float] = None
    ph: Optional[float] = None
    timestamp: datetime


class TelemetryResponse(BaseModel):
    message: str
    telemetry_id: int


class TelemetryBatchResponse(BaseModel):
    message: str
    telemetry_ids: List[int]


class TelemetryValidateResponse(BaseModel):
    valid: bool
    normalized: bool
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class DeviceResponse(BaseModel):
    id: int
    name: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TelemetryReading(BaseModel):
    device_id: int
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    soil_moisture: Optional[float] = None
    ph: Optional[float] = None
    timestamp: datetime

    model_config = {"from_attributes": True}


class DeviceStatus(BaseModel):
    device_id: int
    last_seen: Optional[datetime] = None
    status: str


class MonitoringSummary(BaseModel):
    total_devices: int
    online_devices: int
    total_readings_today: int
    active_alerts: int
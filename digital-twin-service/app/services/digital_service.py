from sqlalchemy.orm import Session
from typing import List, Optional

from app.models.digital_model import DigitalTwin
from app.schemas.digital_schema import TwinUpdateRequest, TwinResponse, TwinState, SystemStateResponse

_THRESHOLDS = {
    "temperature_warning": 34.0,
    "temperature_critical": 38.0,
    "humidity_warning": 40.0,
    "humidity_critical": 25.0,
    "soil_moisture_warning": 30.0,
    "soil_moisture_critical": 15.0,
    "ph_min_warning": 6.0,
    "ph_max_warning": 8.0,
    "ph_min_critical": 5.0,
    "ph_max_critical": 9.0,
}


def calculate_risk_level(data: TwinUpdateRequest) -> str:
    t, h, sm, ph = data.temperature, data.humidity, data.soil_moisture, data.ph
    is_critical = (
        (t is not None and t >= _THRESHOLDS["temperature_critical"])
        or (h is not None and h <= _THRESHOLDS["humidity_critical"])
        or (sm is not None and sm <= _THRESHOLDS["soil_moisture_critical"])
        or (ph is not None and (ph <= _THRESHOLDS["ph_min_critical"] or ph >= _THRESHOLDS["ph_max_critical"]))
    )
    if is_critical:
        return "critical"

    is_warning = (
        (t is not None and t >= _THRESHOLDS["temperature_warning"])
        or (h is not None and h <= _THRESHOLDS["humidity_warning"])
        or (sm is not None and sm <= _THRESHOLDS["soil_moisture_warning"])
        or (ph is not None and (ph <= _THRESHOLDS["ph_min_warning"] or ph >= _THRESHOLDS["ph_max_warning"]))
    )
    if is_warning:
        return "warning"

    return "normal"


def update_twin(db: Session, data: TwinUpdateRequest) -> DigitalTwin:
    risk_level = calculate_risk_level(data)
    twin = db.query(DigitalTwin).filter(DigitalTwin.device_id == data.device_id).first()
    if twin:
        twin.temperature = data.temperature
        twin.humidity = data.humidity
        twin.soil_moisture = data.soil_moisture
        twin.ph = data.ph
        twin.risk_level = risk_level
    else:
        twin = DigitalTwin(
            device_id=data.device_id,
            temperature=data.temperature,
            humidity=data.humidity,
            soil_moisture=data.soil_moisture,
            ph=data.ph,
            risk_level=risk_level,
        )
        db.add(twin)
    db.commit()
    db.refresh(twin)
    return twin


def get_twin(db: Session, device_id: int) -> Optional[DigitalTwin]:
    return db.query(DigitalTwin).filter(DigitalTwin.device_id == device_id).first()


def get_all_twins(db: Session) -> List[DigitalTwin]:
    return db.query(DigitalTwin).all()


def get_system_state(db: Session) -> dict:
    twins = db.query(DigitalTwin).all()
    return {
        "total_units": len(twins),
        "healthy_units": sum(1 for t in twins if t.risk_level == "normal"),
        "warning_units": sum(1 for t in twins if t.risk_level == "warning"),
        "critical_units": sum(1 for t in twins if t.risk_level == "critical"),
    }


def recalculate_twin(db: Session, device_id: int) -> Optional[DigitalTwin]:
    twin = db.query(DigitalTwin).filter(DigitalTwin.device_id == device_id).first()
    if not twin:
        return None
    data = TwinUpdateRequest(
        device_id=twin.device_id,
        temperature=twin.temperature,
        humidity=twin.humidity,
        soil_moisture=twin.soil_moisture,
        ph=twin.ph,
    )
    twin.risk_level = calculate_risk_level(data)
    db.commit()
    db.refresh(twin)
    return twin


def to_response(twin: DigitalTwin) -> TwinResponse:
    return TwinResponse(
        device_id=twin.device_id,
        current_state=TwinState(
            temperature=twin.temperature,
            humidity=twin.humidity,
            soil_moisture=twin.soil_moisture,
            ph=twin.ph,
        ),
        risk_level=twin.risk_level,
        updated_at=twin.updated_at,
    )

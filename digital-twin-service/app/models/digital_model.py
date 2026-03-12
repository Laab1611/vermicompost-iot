from sqlalchemy import Column, Integer, Float, DateTime, String
from sqlalchemy.sql import func
from app.database.base import Base


class DigitalTwin(Base):
    __tablename__ = "digital_twin"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, nullable=False, unique=True, index=True)
    temperature = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    soil_moisture = Column(Float, nullable=True)
    ph = Column(Float, nullable=True)
    risk_level = Column(String, default="normal", nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

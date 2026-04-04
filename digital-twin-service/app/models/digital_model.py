from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database.base import Base


class CamaVermicompostaje(Base):
    __tablename__ = "cama_vermicompostaje"

    cama_id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(120), nullable=False)
    ubicacion = Column(String(200), nullable=False)
    latitud = Column(Numeric(9, 6), nullable=True)
    longitud = Column(Numeric(9, 6), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    nodos = relationship("NodoSensor", back_populates="cama")


class NodoSensor(Base):
    __tablename__ = "nodo_sensor"

    nodo_id = Column(Integer, primary_key=True, index=True)
    cama_id = Column(Integer, ForeignKey("cama_vermicompostaje.cama_id"), nullable=False, index=True)
    codigo_nodo = Column(String(120), nullable=False, unique=True)
    ultima_lectura_recibida = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    cama = relationship("CamaVermicompostaje", back_populates="nodos")
    lecturas = relationship("Lectura", back_populates="nodo")
    lecturas_invalidas = relationship("LecturaInvalida", back_populates="nodo")


class TipoVariable(Base):
    __tablename__ = "tipo_variable"

    tipo_variable_id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(120), nullable=False, unique=True)
    unidad_medida = Column(String(20), nullable=False)

    lecturas = relationship("Lectura", back_populates="tipo_variable")
    lecturas_invalidas = relationship("LecturaInvalida", back_populates="tipo_variable")


class Lectura(Base):
    __tablename__ = "lectura"

    lectura_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nodo_id = Column(Integer, ForeignKey("nodo_sensor.nodo_id"), nullable=False, index=True)
    tipo_variable_id = Column(Integer, ForeignKey("tipo_variable.tipo_variable_id"), nullable=False, index=True)
    valor = Column(Numeric(12, 4), nullable=False)
    fecha_medicion = Column(DateTime(timezone=True), nullable=False)
    fecha_recepcion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    nodo = relationship("NodoSensor", back_populates="lecturas")
    tipo_variable = relationship("TipoVariable", back_populates="lecturas")


class LecturaInvalida(Base):
    __tablename__ = "lectura_invalida"

    lectura_invalida_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nodo_id = Column(Integer, ForeignKey("nodo_sensor.nodo_id"), nullable=True, index=True)
    tipo_variable_id = Column(Integer, ForeignKey("tipo_variable.tipo_variable_id"), nullable=True, index=True)
    valor_recibido = Column(String(200), nullable=False)
    fecha_medicion = Column(String(120), nullable=False)
    fecha_recepcion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    tipo_error = Column(String(60), nullable=False, index=True)

    nodo = relationship("NodoSensor", back_populates="lecturas_invalidas")
    tipo_variable = relationship("TipoVariable", back_populates="lecturas_invalidas")

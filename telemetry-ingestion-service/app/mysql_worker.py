from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
import json
import logging
import os
import re
import signal
import threading
import time
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.broker.factory import create_broker
from app.config import settings
from app.database.connection import SessionLocal
from app.models.telemetry_model import TipoVariable

logger = logging.getLogger(__name__)

_stop_event = threading.Event()
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")


@dataclass(slots=True)
class LegacyRow:
    cama_vermicompostaje: int
    nodo_sensor: int
    fecha: datetime
    temperatura: Decimal | None
    humedad: Decimal | None
    ph: Decimal | None


def _setup_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level_name, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _is_safe_identifier(value: str) -> bool:
    return bool(_IDENTIFIER_PATTERN.fullmatch(value))


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            raise ValueError("fecha vacia")
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    raise ValueError("fecha invalida")


def _format_datetime(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat(sep=" ")


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"valor entero invalido: {value!r}") from exc


def _resolve_tipo_variable_id(session: Session, nombre: str, configured_id: int) -> int:
    if configured_id > 0:
        return configured_id

    tipo = session.query(TipoVariable).filter(TipoVariable.nombre == nombre).first()
    if tipo:
        return tipo.tipo_variable_id

    tipo_aliases = {
        "Temperatura ambiental": ["Temperatura", "temperatura"],
        "Humedad relativa": ["Humedad", "humedad"],
        "pH": ["PH", "ph"],
    }
    for alias in tipo_aliases.get(nombre, []):
        tipo = session.query(TipoVariable).filter(TipoVariable.nombre == alias).first()
        if tipo:
            return tipo.tipo_variable_id

    raise RuntimeError(f"No se encontro tipo_variable para {nombre!r}")


def _resolve_nodo_id(legacy_node_id: int) -> int:
    mapping = settings.mysql_node_id_map
    return mapping.get(legacy_node_id, legacy_node_id)


def _json_safe_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _load_checkpoint(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("No se pudo leer el checkpoint, se reiniciara desde cero")
        return None


def _save_checkpoint(path: Path, checkpoint: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(checkpoint, ensure_ascii=False), encoding="utf-8")
    temp_path.replace(path)


def _row_from_mapping(row: dict[str, Any]) -> LegacyRow:
    return LegacyRow(
        cama_vermicompostaje=_safe_int(row["cama_vermicompostaje"]),
        nodo_sensor=_safe_int(row["nodo_sensor"]),
        fecha=_parse_datetime(row["fecha"]),
        temperatura=_parse_decimal(row.get("temperatura")),
        humedad=_parse_decimal(row.get("humedad")),
        ph=_parse_decimal(row.get("ph")),
    )


def _row_to_payloads(
    row: LegacyRow,
    *,
    temperature_type_id: int,
    humidity_type_id: int,
    ph_type_id: int,
) -> list[dict[str, Any]]:
    nodo_id = _resolve_nodo_id(row.nodo_sensor)
    return [
        {
            "nodo_id": nodo_id,
            "tipo_variable_id": temperature_type_id,
            "valor": _json_safe_value(row.temperatura),
            "fecha_medicion": _json_safe_value(row.fecha),
        },
        {
            "nodo_id": nodo_id,
            "tipo_variable_id": humidity_type_id,
            "valor": _json_safe_value(row.humedad),
            "fecha_medicion": _json_safe_value(row.fecha),
        },
        {
            "nodo_id": nodo_id,
            "tipo_variable_id": ph_type_id,
            "valor": _json_safe_value(row.ph),
            "fecha_medicion": _json_safe_value(row.fecha),
        },
    ]


def _build_mysql_engine():
    mysql_url = settings.mysql_connection_url
    if not mysql_url:
        raise RuntimeError(
            "Faltan credenciales de MySQL. Define MYSQL_URL o MYSQL_HOST/MYSQL_PORT/MYSQL_USER/MYSQL_PASSWORD/MYSQL_DATABASE."
        )

    return create_engine(mysql_url, pool_pre_ping=True, future=True)


def _build_query() -> str:
    table = settings.mysql_table
    if not _is_safe_identifier(table):
        raise RuntimeError("MYSQL_TABLE contiene un nombre no valido")

    for column in (
        "cama_vermicompostaje",
        "nodo_sensor",
        "fecha",
        "temperatura",
        "humedad",
        "ph",
    ):
        if not _is_safe_identifier(column):
            raise RuntimeError(f"Nombre de columna no valido: {column}")

    return f"""
        SELECT
            cama_vermicompostaje,
            nodo_sensor,
            fecha,
            temperatura,
            humedad,
            ph
        FROM `{table}`
        WHERE
            (:last_fecha IS NULL)
            OR (fecha > :last_fecha)
            OR (fecha = :last_fecha AND cama_vermicompostaje > :last_cama)
            OR (fecha = :last_fecha AND cama_vermicompostaje = :last_cama AND nodo_sensor > :last_nodo)
        ORDER BY fecha ASC, cama_vermicompostaje ASC, nodo_sensor ASC
        LIMIT :batch_size
    """


def _fetch_batch(engine, checkpoint: dict[str, Any] | None) -> list[LegacyRow]:
    query = _build_query()
    params = {
        "last_fecha": _parse_datetime(checkpoint["fecha"]) if checkpoint and checkpoint.get("fecha") else None,
        "last_cama": checkpoint.get("cama_vermicompostaje", -1) if checkpoint else -1,
        "last_nodo": checkpoint.get("nodo_sensor", -1) if checkpoint else -1,
        "batch_size": settings.mysql_batch_size,
    }

    with engine.connect() as connection:
        result = connection.execute(text(query), params)
        rows = result.mappings().fetchall()

    return [_row_from_mapping(dict(row)) for row in rows]


def _resolve_tipo_variable_ids() -> tuple[int, int, int]:
    db = SessionLocal()
    try:
        temperature_type_id = _resolve_tipo_variable_id(db, "Temperatura ambiental", settings.mysql_temperature_type_id)
        humidity_type_id = _resolve_tipo_variable_id(db, "Humedad relativa", settings.mysql_humidity_type_id)
        ph_type_id = _resolve_tipo_variable_id(db, "pH", settings.mysql_ph_type_id)
        return temperature_type_id, humidity_type_id, ph_type_id
    finally:
        db.close()


def _publish_batch(broker, rows: list[LegacyRow], tipo_ids: tuple[int, int, int]) -> dict[str, Any]:
    temperature_type_id, humidity_type_id, ph_type_id = tipo_ids
    published = 0
    last_checkpoint: dict[str, Any] | None = None

    for row in rows:
        payloads = _row_to_payloads(
            row,
            temperature_type_id=temperature_type_id,
            humidity_type_id=humidity_type_id,
            ph_type_id=ph_type_id,
        )
        for payload in payloads:
            broker.publish(
                topic=settings.broker_queue_name,
                payload=payload,
                headers={"service": "telemetry-mysql-sync-worker", "source": "mysql-legacy"},
            )
            published += 1

        last_checkpoint = {
            "fecha": _format_datetime(row.fecha),
            "cama_vermicompostaje": row.cama_vermicompostaje,
            "nodo_sensor": row.nodo_sensor,
        }

    return {"published": published, "checkpoint": last_checkpoint}


def _handle_signal(signum, _frame) -> None:
    logger.info("Received signal %s, stopping MySQL sync worker", signum)
    _stop_event.set()


def main() -> None:
    _setup_logging()
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    mysql_engine = _build_mysql_engine()
    broker = create_broker(settings, logger=logger)
    tipo_variable_ids = _resolve_tipo_variable_ids()
    checkpoint_path = Path(settings.mysql_checkpoint_path)
    checkpoint = _load_checkpoint(checkpoint_path)

    logger.info(
        "MySQL sync worker started: table=%s batch_size=%s poll_interval_seconds=%.2f checkpoint=%s",
        settings.mysql_table,
        settings.mysql_batch_size,
        settings.mysql_poll_interval_seconds,
        checkpoint_path,
    )

    try:
        while not _stop_event.is_set():
            try:
                rows = _fetch_batch(mysql_engine, checkpoint)
                if not rows:
                    time.sleep(settings.mysql_poll_interval_seconds)
                    continue

                result = _publish_batch(broker, rows, tipo_variable_ids)
                if result["checkpoint"] is not None:
                    checkpoint = result["checkpoint"]
                    _save_checkpoint(checkpoint_path, checkpoint)

                logger.info(
                    "MySQL sync batch processed: rows=%s published=%s checkpoint=%s",
                    len(rows),
                    result["published"],
                    checkpoint,
                )
            except SQLAlchemyError:
                logger.exception("Error reading from MySQL source")
                time.sleep(settings.mysql_poll_interval_seconds)
            except Exception:
                logger.exception("Unexpected error in MySQL sync worker")
                time.sleep(settings.mysql_poll_interval_seconds)
    finally:
        broker.close()
        mysql_engine.dispose()
        logger.info("MySQL sync worker stopped")


if __name__ == "__main__":
    main()
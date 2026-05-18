# Repository Instructions

## Shape Of The Repo

- Three Python 3.11 FastAPI services live in `telemetry-ingestion-service/`, `query-monitoring-service/`, and `digital-twin-service/`; each uses `uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log` inside its own Docker context.
- Compose service `digital-twin-integration-service` is built from `digital-twin-service/`. Gateway routes are `/telemetry/`, `/query/`, and `/twins/` in `api-gateway/nginx.conf`.
- `telemetry-ingestion-service/` is the write side and owns master-data CRUD plus `POST /api/v1/ingestion`; the other two services are read-only projections over the same tables.
- The SQLAlchemy schema is duplicated in `app/models/telemetry_model.py`, `app/models/query_model.py`, and `app/models/digital_model.py`. Keep schema changes synchronized across all three services.
- There is no Alembic or migration workflow in this repo. `Base.metadata.create_all()` appears only in tests.

## Commands

- Full stack uses the Podman Compose wrapper: `source ~/Documents/code/py_venvs/podman_compose/bin/activate`, then `podman-compose up --build -d`.
- Gateway smoke checks: `curl http://localhost:8080/telemetry/health`, `curl http://localhost:8080/query/health`, `curl http://localhost:8080/twins/health`.
- Run a service locally from its service directory: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log`.
- Run the ingestion worker locally from `telemetry-ingestion-service/`: `python -m app.worker`.
- Recommended repo-level verification: `python -m pytest telemetry-ingestion-service/tests`, `python -m pytest query-monitoring-service/tests`, `python -m pytest digital-twin-service/tests`, then `python -m compileall telemetry-ingestion-service query-monitoring-service digital-twin-service`.
- Focused test from a service directory: `python -m pytest tests/test_<file>.py -k <expr>`.

## Environment And Testing Gotchas

- `pytest` is used by the tests but is not pinned in any `requirements.txt`; a fresh virtualenv from service requirements alone will not have it.
- Unit tests use in-memory SQLite and do not need PostgreSQL, Redis, or Docker.
- App settings load `.env` from the current working directory. Compose uses the repo root `.env`; ad hoc local runs need `DATABASE_URL` exported or a matching `.env` in the service directory.
- Podman Compose defaults ingestion to broker mode with Redis: `INGESTION_MODE=broker`, `BROKER_PROVIDER=redis`, API consumer disabled, and `telemetry-ingestion-worker` enabled.
- RabbitMQ code and Compose service are present but commented or disabled; do not assume RabbitMQ is active.

## Operational Notes

- Prometheus and Grafana provisioning lives under `monitoring/`; edit provisioned files there, not running containers.
- Query service publishes custom Prometheus gauges from a background refresh loop in `query-monitoring-service/app/main.py`.
- Ingestion treats non-decimal values as `valor_fuera_de_rango`; numeric outliers are still valid because operational thresholds are handled in Grafana, not backend validation.
- Invalid ingestion payloads are persisted in `lectura_invalida`; query and twin overview counts read invalids from that table.

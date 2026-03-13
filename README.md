# Vermicompost IoT - Sistema de Monitoreo por Microservicios

Sistema IoT para monitoreo de vermicompostaje basado en microservicios con Python, FastAPI, PostgreSQL, Prometheus, Nginx y Docker.

---

## Arquitectura general

```
Sensor / Dispositivo IoT
        │
        ▼
┌──────────────────────────────┐
│      Nginx (api-gateway)     │  :80
│   Reverse proxy por prefijo  │
└──────────────┬───────────────┘
               │
     ┌─────────┼──────────┬─────────────┐
     ▼         ▼          ▼             ▼
 /telemetry  /query    /alerts       /twins
     │         │          │             │
     ▼         ▼          ▼             ▼
┌─────────┐ ┌───────┐ ┌────────┐ ┌──────────┐
│Telemetry│ │Query  │ │Alert   │ │ Digital  │
│Ingestion│ │Monit. │ │Service │ │  Twin    │
│:8001    │ │:8002  │ │:8003   │ │:8004     │
└────┬────┘ └───┬───┘ └───┬────┘ └────┬─────┘
     │          │         │           │
     └──────────┴─────────┴───────────┘
                          │
                          ▼
                   ┌────────────┐
                   │ PostgreSQL │
                   │  :5432     │
                   └────────────┘
                          │
                   ┌────────────┐
                   │ Prometheus │
                   │  :9090     │
                   └─────┬──────┘
                         │
                         ▼
                   ┌────────────┐
                   │ Grafana    │
                   │  :3000     │
                   └────────────┘
```

---

## Flujo de trabajo principal

### 1. Ingesta de telemetría

```
Sensor
  └── POST /telemetry/api/v1/telemetry
            │
            ▼
  telemetry-ingestion-service
    ├── Valida el payload (Pydantic)
    ├── Normaliza los valores (redondeo)
    ├── Persiste en tabla `telemetry` (PostgreSQL)
    ├── POST http://alert-service:8000/api/v1/alerts/evaluate  ──► alert-service
    └── POST http://digital-twin-service:8000/api/v1/twins/update ──► digital-twin-service
```

### 2. Evaluación de alertas (alert-service)

```
telemetry-ingestion-service
  └── POST /api/v1/alerts/evaluate
            │
            ▼
  alert-service
    ├── Lee umbrales configurados desde tabla `alert_rules`
    │   (usa defaults si no hay reglas: temp >34°C, humedad <40%, etc.)
    ├── Evalúa cada campo: temperatura, humedad, moisture, pH
    ├── Genera alertas con nivel warning / critical
    └── Persiste alertas en tabla `alerts` (PostgreSQL)
```

### 3. Actualización del gemelo digital (digital-twin-service)

```
telemetry-ingestion-service
  └── POST /api/v1/twins/update
            │
            ▼
  digital-twin-service
    ├── Calcula risk_level (normal / warning / critical)
    │   según umbrales internos
    ├── Hace upsert del estado en tabla `digital_twin`
    │   (una fila por device_id)
    └── Expone el estado procesado del sistema
```

### 4. Consulta y monitoreo (query-monitoring-service)

```
Dashboard / Grafana / Frontend
  └── GET /query/api/v1/...
            │
            ▼
  query-monitoring-service
    ├── Lee directamente de PostgreSQL (tablas: devices, telemetry, alerts)
    ├── Expone última lectura por dispositivo
    ├── Expone histórico con filtros por rango de fechas
    ├── Expone estado online/offline de todos los dispositivos
    └── Expone resumen de monitoreo (total lecturas, alertas activas, etc.)
```

---

## Microservicios

| Servicio | Puerto | Responsabilidad |
|---|---|---|
| `telemetry-ingestion-service` | 8001 | Recibir, validar, normalizar y persistir telemetría |
| `query-monitoring-service` | 8002 | Consultar históricos, estado actual y resúmenes |
| `alert-service` | 8003 | Evaluar umbrales, generar y gestionar alertas |
| `digital-twin-service` | 8004 | Mantener el estado procesado del gemelo digital |
| `postgres` | 5432 | Base de datos relacional |
| `prometheus` | 9090 | Scraping de métricas de los 4 servicios |
| `nginx` (api-gateway) | 80 | Reverse proxy de entrada |
| `grafana` | 3000 | Visualización de métricas (Prometheus) |

---

## Endpoints por servicio

### telemetry-ingestion-service

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/health` | Estado del servicio |
| `GET` | `/metrics` | Métricas Prometheus |
| `POST` | `/api/v1/telemetry` | Ingresar una lectura de sensor |
| `POST` | `/api/v1/telemetry/batch` | Ingresar múltiples lecturas |
| `POST` | `/api/v1/telemetry/validate` | Validar sin persistir |

### query-monitoring-service

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/health` | Estado del servicio |
| `GET` | `/metrics` | Métricas Prometheus |
| `GET` | `/api/v1/devices` | Listar dispositivos |
| `GET` | `/api/v1/devices/{device_id}` | Detalle de un dispositivo |
| `GET` | `/api/v1/devices/status` | Estado online/offline de todos |
| `GET` | `/api/v1/devices/{device_id}/latest` | Última lectura |
| `GET` | `/api/v1/devices/{device_id}/history` | Histórico con filtros |
| `GET` | `/api/v1/monitoring/summary` | Resumen global del sistema |
| `GET` | `/api/v1/telemetry/recent` | Lecturas recientes globales |

### alert-service

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/health` | Estado del servicio |
| `GET` | `/metrics` | Métricas Prometheus |
| `POST` | `/api/v1/alerts/evaluate` | Evaluar telemetría y generar alertas |
| `GET` | `/api/v1/alerts` | Listar alertas (con filtros opcionales) |
| `GET` | `/api/v1/alerts/active` | Alertas no resueltas |
| `GET` | `/api/v1/alerts/{alert_id}` | Detalle de una alerta |
| `PATCH` | `/api/v1/alerts/{alert_id}/resolve` | Marcar alerta como resuelta |
| `GET` | `/api/v1/alerts/rules` | Ver umbrales configurados |
| `POST` | `/api/v1/alerts/rules` | Crear/actualizar umbrales |

### digital-twin-service

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/health` | Estado del servicio |
| `GET` | `/metrics` | Métricas Prometheus |
| `POST` | `/api/v1/twins/update` | Actualizar estado del gemelo |
| `GET` | `/api/v1/twins` | Listar todos los gemelos |
| `GET` | `/api/v1/twins/system-state` | Estado global del sistema |
| `GET` | `/api/v1/twins/{device_id}` | Estado de un gemelo específico |
| `POST` | `/api/v1/twins/{device_id}/recalculate` | Recalcular risk_level |

---

## Tablas en PostgreSQL

| Tabla | Servicio escritor | Descripción |
|---|---|---|
| `devices` | telemetry-ingestion | Dispositivos registrados |
| `telemetry` | telemetry-ingestion | Lecturas de sensores |
| `alerts` | alert-service | Alertas generadas |
| `alert_rules` | alert-service | Umbrales configurables |
| `digital_twin` | digital-twin-service | Estado actual del gemelo por dispositivo |

Las tablas se crean automáticamente al iniciar cada servicio mediante `Base.metadata.create_all`.

---

## Estructura del proyecto

```
vermicompost-iot/
├── docker-compose.yml
├── api-gateway/
│   ├── Dockerfile
│   └── nginx.conf
├── monitoring/
│   └── prometheus.yml
├── telemetry-ingestion-service/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── api/routes.py
│       ├── services/telemetry_service.py
│       ├── models/telemetry_model.py
│       ├── schemas/telemetry_schema.py
│       ├── database/connection.py
│       ├── database/base.py
│       └── metrics/prometheus.py
├── query-monitoring-service/
│   └── app/ (misma estructura)
├── alert-service/
│   └── app/ (misma estructura)
└── digital-twin-service/
    └── app/ (misma estructura)
```

---

## Payload de telemetría

```json
{
  "device_id": 1,
  "temperature": 28.4,
  "humidity": 76.3,
  "soil_moisture": 58.1,
  "ph": 6.8,
  "timestamp": "2026-03-11T18:00:00Z"
}
```

---

## Umbrales por defecto (alert-service)

| Variable | Umbral | Nivel |
|---|---|---|
| Temperatura | > 34 °C | warning |
| Humedad | < 40 % | warning |
| Moisture suelo | < 30 % | critical |
| pH | < 6.0 o > 8.0 | warning |

Configurables vía `POST /api/v1/alerts/rules`.

---

## Niveles de riesgo (digital-twin-service)

| Nivel | Condición |
|---|---|
| `normal` | Todos los valores dentro de rango |
| `warning` | Temperatura ≥ 34 °C, humedad ≤ 40 %, moisture ≤ 30 %, pH fuera de [6–8] |
| `critical` | Temperatura ≥ 38 °C, humedad ≤ 25 %, moisture ≤ 15 %, pH fuera de [5–9] |

---

## Stack tecnológico

| Tecnología | Uso |
|---|---|
| Python 3.11 | Lenguaje base |
| FastAPI | Framework web y validación |
| SQLAlchemy 2 | ORM para PostgreSQL |
| Pydantic v2 | Schemas y validación de entrada |
| pydantic-settings | Configuración por variables de entorno |
| psycopg2-binary | Driver PostgreSQL |
| prometheus-fastapi-instrumentator | Exposición automática de `/metrics` |
| httpx | Comunicación HTTP entre servicios |
| PostgreSQL 15 | Base de datos relacional |
| Prometheus | Recolección de métricas |
| Nginx | Reverse proxy y API gateway |
| Docker / Docker Compose | Contenedorización y orquestación |

---

## Levantamiento con Docker Compose

### Requisitos previos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) ≥ 24 (incluye Docker Compose v2)
- Puertos `80`, `3000`, `5432`, `8001–8004` y `9090` disponibles en la máquina local

Verificar que Docker está activo:

```bash
docker --version
docker compose version
```

---

### Paso 1 — Clonar el repositorio

```bash
git clone <url-del-repositorio>
cd vermicompost-iot
```

---

### Paso 2 — Configurar las variables de entorno

Copiar el archivo de ejemplo y ajustar las credenciales:

```bash
cp .env.example .env
```

Editar `.env` con los valores deseados:

```ini
# PostgreSQL
POSTGRES_USER=vermicompost
POSTGRES_PASSWORD=vermicompost
POSTGRES_DB=vermicompost

# Microservicios
DATABASE_URL=postgresql://vermicompost:vermicompost@postgres:5432/vermicompost
ALERT_SERVICE_URL=http://alert-service:8000
DIGITAL_TWIN_SERVICE_URL=http://digital-twin-service:8000
```

> **Nota:** `.env` está en `.gitignore` y **nunca se sube al repositorio**. Solo `.env.example` se versiona.

---

### Paso 3 — Construir las imágenes e iniciar los contenedores

```bash
# Primera vez o tras cambios en el código
docker compose up --build -d
```

Docker Compose realizará las siguientes acciones en orden:

1. Construye las 4 imágenes Python (`python:3.11-slim` + dependencias de `requirements.txt`)
2. Inicia `postgres` y espera a que pase el health-check (`pg_isready`)
3. Una vez PostgreSQL está listo, inicia los 4 microservicios (que crean sus tablas automáticamente vía SQLAlchemy)
4. Inicia `prometheus` y `nginx`

El flag `-d` ejecuta todo en segundo plano (detached mode).

---

### Paso 4 — Verificar que todos los servicios están en pie

```bash
docker compose ps
```

Salida esperada (todos en estado `Up`):

```
NAME                                         STATUS          PORTS
vermicompost-iot-nginx-1                     Up              0.0.0.0:80->80/tcp
vermicompost-iot-alert-service-1             Up              0.0.0.0:8003->8000/tcp
vermicompost-iot-digital-twin-service-1      Up              0.0.0.0:8004->8000/tcp
vermicompost-iot-grafana-enterprise-1        Up              0.0.0.0:3000->3000/tcp
vermicompost-iot-postgres-1                  Up (healthy)    0.0.0.0:5432->5432/tcp
vermicompost-iot-prometheus-1                Up              0.0.0.0:9090->9090/tcp
vermicompost-iot-query-monitoring-service-1  Up              0.0.0.0:8002->8000/tcp
vermicompost-iot-telemetry-ingestion-service-1  Up           0.0.0.0:8001->8000/tcp
```

Health-check rápido de los 4 microservicios:

```bash
curl http://localhost:8001/health   # telemetry-ingestion-service
curl http://localhost:8002/health   # query-monitoring-service
curl http://localhost:8003/health   # alert-service
curl http://localhost:8004/health   # digital-twin-service
```

Respuesta esperada en cada uno:

```json
{ "status": "ok", "service": "<nombre-del-servicio>" }
```

---

### Paso 5 — Enviar la primera telemetría (prueba end-to-end)

```bash
curl -X POST http://localhost:8001/api/v1/telemetry \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": 1,
    "temperature": 35.5,
    "humidity": 38.0,
    "soil_moisture": 28.0,
    "ph": 5.5,
    "timestamp": "2026-03-11T10:00:00Z"
  }'
```

Verificar que se generaron alertas y el gemelo digital:

```bash
curl http://localhost:8003/api/v1/alerts/active       # alertas generadas
curl http://localhost:8004/api/v1/twins                # estado del gemelo
curl http://localhost:8002/api/v1/monitoring/summary   # resumen del sistema
```

---

### URLs disponibles tras el levantamiento

| Servicio | URL local |
|---|---|
| Nginx (entrada principal) | http://localhost:80 |
| telemetry-ingestion-service | http://localhost:8001 |
| query-monitoring-service | http://localhost:8002 |
| alert-service | http://localhost:8003 |
| digital-twin-service | http://localhost:8004 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |
| PostgreSQL | localhost:5432 |

---

### Comandos útiles

```bash
# Ver logs de un servicio en tiempo real
docker compose logs -f telemetry-ingestion-service

# Ver logs de todos los servicios
docker compose logs -f

# Reiniciar un servicio sin reconstruir
docker compose restart alert-service

# Reconstruir y reiniciar solo un servicio tras cambiar su código
docker compose up --build -d telemetry-ingestion-service

# Detener todos los contenedores (conserva los volúmenes/datos)
docker compose down

# Detener y eliminar volúmenes (borra la base de datos)
docker compose down -v
```

---

## Variables de entorno

Las variables se centralizan en el archivo `.env` en la raíz del proyecto (ver `.env.example`). Docker Compose las inyecta en cada contenedor vía `env_file: .env`. Los servicios también las leen directamente con `pydantic-settings` cuando se ejecutan fuera de Docker.

| Variable | Descripción | Ejemplo |
|---|---|---|
| `POSTGRES_USER` | Usuario de PostgreSQL | `vermicompost` |
| `POSTGRES_PASSWORD` | Contraseña de PostgreSQL | `vermicompost` |
| `POSTGRES_DB` | Nombre de la base de datos | `vermicompost` |
| `DATABASE_URL` | Cadena de conexión completa | `postgresql://user:pass@postgres:5432/db` |
| `ALERT_SERVICE_URL` | URL interna del alert-service | `http://alert-service:8000` |
| `DIGITAL_TWIN_SERVICE_URL` | URL interna del digital-twin-service | `http://digital-twin-service:8000` |
| `GRAFANA_USER` | Usuario admin para Grafana | `vermicompostingMonitor` |
| `GRAFANA_PASSWORD` | Contraseña admin para Grafana | `vermiComposting1*` |

> `ALERT_SERVICE_URL` y `DIGITAL_TWIN_SERVICE_URL` solo las utiliza `telemetry-ingestion-service`.

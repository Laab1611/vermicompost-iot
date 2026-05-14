# Telemetry Ingestion Service

Servicio de escritura del dominio. Gestiona datos maestros (camas, nodos, tipos de variable) y lecturas de telemetria.

Puerto local: 8001
Base URL por gateway: http://localhost/telemetry

## Endpoints

- GET /health
- POST /api/v1/ingestion
- POST /api/v1/camas
- GET /api/v1/camas
- GET /api/v1/camas/{cama_id}
- PUT /api/v1/camas/{cama_id}
- DELETE /api/v1/camas/{cama_id}
- POST /api/v1/nodos
- GET /api/v1/nodos
- GET /api/v1/nodos/{nodo_id}
- PUT /api/v1/nodos/{nodo_id}
- DELETE /api/v1/nodos/{nodo_id}
- POST /api/v1/tipos-variable
- GET /api/v1/tipos-variable
- GET /api/v1/tipos-variable/{tipo_variable_id}
- PUT /api/v1/tipos-variable/{tipo_variable_id}
- DELETE /api/v1/tipos-variable/{tipo_variable_id}
- POST /api/v1/lecturas
- GET /api/v1/lecturas
- GET /api/v1/lecturas/{lectura_id}
- PUT /api/v1/lecturas/{lectura_id}
- DELETE /api/v1/lecturas/{lectura_id}

## Modo broker para ingestion

Variables de entorno:

- INGESTION_MODE=sync|broker
- BROKER_PROVIDER=redis|memory
- BROKER_QUEUE_NAME=telemetry.ingestion
- BROKER_CONSUMER_ENABLED=true|false
- BROKER_PREFETCH_COUNT=100
- BROKER_BATCH_SIZE=100
- BROKER_FLUSH_SECONDS=1.0
- REDIS_URL=redis://redis:6379/0
- REDIS_CONSUMER_GROUP=telemetry-ingestion-group
- REDIS_CONSUMER_NAME=telemetry-ingestion-consumer
- REDIS_POLL_TIMEOUT_MS=1000
<!-- - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/%2F -->
<!-- - RABBITMQ_EXCHANGE= -->
<!-- - RABBITMQ_ROUTING_KEY= -->

## Worker provisional de sincronizacion MySQL -> broker

Este worker lee la tabla legacy de MySQL en modo solo lectura, separa cada fila en tres lecturas normalizadas y publica al broker existente. El worker actual sigue haciendo la validacion, el batch y la persistencia en PostgreSQL.

Variables de entorno:

- MYSQL_URL o, en su defecto, MYSQL_HOST/MYSQL_PORT/MYSQL_USER/MYSQL_PASSWORD/MYSQL_DATABASE
- MYSQL_TABLE=sensoresiot
- MYSQL_BATCH_SIZE=100
- MYSQL_CHECKPOINT_PATH=/var/lib/mysql-sync/checkpoint.json


Comportamiento:

- En `sync`, `POST /api/v1/ingestion` mantiene comportamiento historico.
- En `broker`, `POST /api/v1/ingestion` encola y responde inmediatamente con `persistida=false`.
- En `broker` con Redis Streams, el consumidor valida cada payload y persiste lecturas validas en lotes.
- Batch actual: tamaño 100 y flush por tiempo para evitar latencias altas en rafagas.

## Reglas de validacion relevantes

- create_nodo asigna created_at en backend.
- El valor de lectura se parsea como decimal.
- create_lectura y update_lectura validan fechas:
  - fecha_medicion no puede ser futura.
  - fecha_recepcion no puede ser futura.
  - fecha_recepcion no puede ser anterior a fecha_medicion.
- En POST /api/v1/ingestion, la invalidez se clasifica automaticamente con estos motivos:
  - timestamp_invalido
  - nodo_no_registrado
  - tipo_variable_no_soportado
  - payload_incompleto
  - valor_fuera_de_rango
  - error_desconocido
- Persistencia en ingestion:
  - Toda lectura invalida se guarda en lectura_invalida con datos crudos:
    - valor_recibido como texto exacto.
    - fecha_medicion como texto exacto.
    - nodo_id y tipo_variable_id como NULL cuando no se pueden resolver.
- Validacion de unidad para tipos conocidos en CRUD de tipo_variable:
  - Temperatura ambiental -> degC
  - Humedad relativa -> %
  - pH -> pH
- valor_fuera_de_rango aplica cuando valor no puede parsearse como decimal (por ejemplo, texto).
- Los umbrales y rangos operativos se gestionan en Grafana, no en backend.

## Errores HTTP esperados

- 200: ingestion aceptada (valida o invalida clasificada).
- 400: validacion de payload o reglas de negocio en endpoints CRUD.
- 404: recurso no encontrado.
- 409: conflicto (duplicados/dependencias).
- 500: error de persistencia no controlado.

## Curl de validacion

### Salud

```bash
curl http://localhost/telemetry/health
```

### Flujo base (datos maestros + ingesta valida)

```bash
curl -X POST http://localhost/telemetry/api/v1/camas \
  -H "Content-Type: application/json" \
  -d '{"nombre":"Cama 1","ubicacion":"Zona Norte","latitud":4.6097,"longitud":-74.0817}'
```

```bash
curl -X POST http://localhost/telemetry/api/v1/nodos \
  -H "Content-Type: application/json" \
  -d '{"cama_id":1,"codigo_nodo":"NODO-001"}'
```

```bash
curl -X POST http://localhost/telemetry/api/v1/tipos-variable \
  -H "Content-Type: application/json" \
  -d '{"nombre":"Temperatura ambiental","unidad_medida":"degC"}'
```

```bash
curl -X POST http://localhost/telemetry/api/v1/ingestion \
  -H "Content-Type: application/json" \
  -d '{"nodo_id":1,"tipo_variable_id":1,"valor":27.8,"fecha_medicion":"2026-03-20T15:00:00Z"}'
```

### Casos invalidos de ingestion

1) nodo no existe -> 200 con motivo nodo_no_registrado y persistida=true

```bash
curl -X POST http://localhost/telemetry/api/v1/ingestion \
  -H "Content-Type: application/json" \
  -d '{"nodo_id":9999,"tipo_variable_id":1,"valor":27.8,"fecha_medicion":"2026-03-20T15:00:00Z"}'
```

2) fecha_medicion futura -> 200 con motivo timestamp_invalido y persistida=true

```bash
curl -X POST http://localhost/telemetry/api/v1/ingestion \
  -H "Content-Type: application/json" \
  -d '{"nodo_id":1,"tipo_variable_id":1,"valor":27.8,"fecha_medicion":"2099-01-01T00:00:00Z"}'
```

3) fecha_recepcion menor que fecha_medicion -> 200 con motivo timestamp_invalido y persistida=true

```bash
curl -X POST http://localhost/telemetry/api/v1/ingestion \
  -H "Content-Type: application/json" \
  -d '{"nodo_id":1,"tipo_variable_id":1,"valor":27.8,"fecha_medicion":"2026-03-20T15:00:00Z","fecha_recepcion":"2026-03-20T14:59:59Z"}'
```

4) tipo_variable no existe -> 200 con motivo tipo_variable_no_soportado y persistida=true

```bash
curl -X POST http://localhost/telemetry/api/v1/ingestion \
  -H "Content-Type: application/json" \
  -d '{"nodo_id":1,"tipo_variable_id":999999,"valor":27.8,"fecha_medicion":"2026-03-20T15:00:00Z"}'
```

5) payload incompleto -> 200 con motivo payload_incompleto y persistida=true

```bash
curl -X POST http://localhost/telemetry/api/v1/ingestion \
  -H "Content-Type: application/json" \
  -d '{"nodo_id":1}'
```

Verificacion de lecturas invalidas (desde query service):

```bash
curl "http://localhost/query/api/v1/lecturas/invalidas?limit=50"
```

Nota: este endpoint muestra invalidas persistidas en lectura_invalida.

6) valor no decimal -> 200 con motivo valor_fuera_de_rango y persistida=true

```bash
curl -X POST http://localhost/telemetry/api/v1/ingestion \
  -H "Content-Type: application/json" \
  -d '{"nodo_id":1,"tipo_variable_id":1,"valor":"texto-invalido","fecha_medicion":"2026-03-20T15:00:00Z"}'
```

Nota: este endpoint muestra invalidas persistidas en lectura_invalida.

### CRUD rapido

```bash
curl http://localhost/telemetry/api/v1/camas
curl http://localhost/telemetry/api/v1/nodos
curl http://localhost/telemetry/api/v1/tipos-variable
curl http://localhost/telemetry/api/v1/lecturas
```

## Pruebas locales

```bash
python -m pytest telemetry-ingestion-service/tests
python -m compileall app
```

La suite incluye casos positivos y negativos para la logica de ingestion y persistencia de lecturas invalidas.
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
- Persistencia en ingestion:
  - timestamp_invalido -> persistida=true (se guarda en lectura).
  - nodo_no_registrado, tipo_variable_no_soportado y payload_incompleto -> persistida=false (no se guarda en lectura).
- Validacion de unidad para tipos conocidos en CRUD de tipo_variable:
  - Temperatura ambiental -> degC
  - Humedad relativa -> %
  - pH -> pH
- Los umbrales de rango no invalidan automaticamente en backend; ese control se delega a Grafana.

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

1) nodo no existe -> 200 con motivo nodo_no_registrado y persistida=false

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

4) tipo_variable no existe -> 200 con motivo tipo_variable_no_soportado y persistida=false

```bash
curl -X POST http://localhost/telemetry/api/v1/ingestion \
  -H "Content-Type: application/json" \
  -d '{"nodo_id":1,"tipo_variable_id":999999,"valor":27.8,"fecha_medicion":"2026-03-20T15:00:00Z"}'
```

5) payload incompleto -> 200 con motivo payload_incompleto y persistida=false

```bash
curl -X POST http://localhost/telemetry/api/v1/ingestion \
  -H "Content-Type: application/json" \
  -d '{"nodo_id":1}'
```

Verificacion de lecturas invalidas (desde query service):

```bash
curl "http://localhost/query/api/v1/lecturas/invalidas?limit=50"
```

Nota: este endpoint muestra invalidas persistidas en lectura.

### CRUD rapido

```bash
curl http://localhost/telemetry/api/v1/camas
curl http://localhost/telemetry/api/v1/nodos
curl http://localhost/telemetry/api/v1/tipos-variable
curl http://localhost/telemetry/api/v1/lecturas
```
# Query Monitoring Service

Servicio de lectura analitica/operativa sobre el modelo DER.

Puerto local: 8002
Base URL por gateway: http://localhost/query

## Endpoints

- GET /health
- GET /api/v1/camas
- GET /api/v1/nodos
- GET /api/v1/tipos-variable
- GET /api/v1/lecturas/historico/nodo/{nodo_id}?limit=
- GET /api/v1/lecturas/historico/cama/{cama_id}?limit=
- GET /api/v1/lecturas/historico/tipo-variable/{tipo_variable_id}?limit=
- GET /api/v1/lecturas/historico/rango-tiempo?start=&end=&limit=
- GET /api/v1/estado/nodo/{nodo_id}?minutes=
- GET /api/v1/estado/cama/{cama_id}?minutes=
- GET /api/v1/lecturas/invalidas?limit=
- GET /api/v1/nodos/desconectados?minutes=
- GET /api/v1/monitoring/summary

## Validaciones de entrada

- limit: 1..1000
- minutes: 1..43200
- start <= end en historico por rango

## Errores HTTP esperados

- 400: parametro invalido (limit, minutes, rango de fechas)
- 404: nodo/cama/tipo no existe
- 500: error de persistencia

## Nota sobre lecturas invalidas

- GET /api/v1/lecturas/invalidas consulta lectura_invalida.
- Devuelve invalidas con trazabilidad aun cuando nodo_id o tipo_variable_id sean NULL.
- El campo motivo_invalidacion corresponde a lectura_invalida.tipo_error.
- lecturas historicas validas siguen saliendo de lectura.

## Curl de validacion

### Casos exitosos

```bash
curl http://localhost/query/health
curl http://localhost/query/api/v1/monitoring/summary
curl "http://localhost/query/api/v1/lecturas/historico/nodo/1?limit=50"
curl "http://localhost/query/api/v1/lecturas/historico/cama/1?limit=50"
curl "http://localhost/query/api/v1/lecturas/historico/tipo-variable/1?limit=50"
curl "http://localhost/query/api/v1/lecturas/historico/rango-tiempo?start=2026-03-20T00:00:00Z&end=2026-03-20T23:59:59Z&limit=100"
curl "http://localhost/query/api/v1/estado/nodo/1?minutes=15"
curl "http://localhost/query/api/v1/estado/cama/1?minutes=15"
curl "http://localhost/query/api/v1/lecturas/invalidas?limit=100"
curl "http://localhost/query/api/v1/nodos/desconectados?minutes=15"
```

### Casos de error controlado

```bash
# limit invalido -> 422 por validacion de FastAPI
curl "http://localhost/query/api/v1/lecturas/historico/nodo/1?limit=0"

# rango invalido -> 400
curl "http://localhost/query/api/v1/lecturas/historico/rango-tiempo?start=2026-03-21T00:00:00Z&end=2026-03-20T00:00:00Z&limit=100"

# nodo no existe -> 404
curl "http://localhost/query/api/v1/estado/nodo/9999?minutes=15"
```

## Pruebas locales

```bash
python -m pytest query-monitoring-service/tests
python -m compileall app
```

La suite incluye casos positivos y negativos para historicos, lecturas invalidas, estado de nodos y resumen global.
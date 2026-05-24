# Servicio de Consulta y Monitoreo

Servicio de lectura analítica y operativa sobre el modelo DER.

Puerto local: interno en 8000
URL base por gateway: https://localhost:8443/query

## Puntos de acceso

- GET /health
- GET /api/v1/camas?minutes=
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
- start <= end en histórico por rango

## Nota sobre GET /api/v1/camas

- La respuesta ahora incluye `nodos` asociados por cama.
- Cada nodo devuelve solo `nodo_id`, `codigo_nodo` y `conectado`.
- `minutes` controla la ventana usada para considerar un nodo conectado. El valor por defecto es 15.

## Errores HTTP esperados

- 400: parámetro inválido (limit, minutes, rango de fechas)
- 404: nodo/cama/tipo no existe
- 500: error de persistencia

## Nota sobre lecturas inválidas

- GET /api/v1/lecturas/invalidas consulta lectura_invalida.
- Devuelve inválidas con trazabilidad aun cuando nodo_id o tipo_variable_id sean NULL.
- El campo motivo_invalidacion corresponde a lectura_invalida.tipo_error.
- lecturas históricas válidas siguen saliendo de lectura.

## Curl de validación

### Casos exitosos

```bash
curl -k https://localhost:8443/query/health
curl -k https://localhost:8443/query/api/v1/monitoring/summary
curl -k "https://localhost:8443/query/api/v1/lecturas/historico/nodo/1?limit=50"
curl -k "https://localhost:8443/query/api/v1/lecturas/historico/cama/1?limit=50"
curl -k "https://localhost:8443/query/api/v1/lecturas/historico/tipo-variable/1?limit=50"
curl -k "https://localhost:8443/query/api/v1/lecturas/historico/rango-tiempo?start=2026-03-20T00:00:00Z&end=2026-03-20T23:59:59Z&limit=100"
curl -k "https://localhost:8443/query/api/v1/estado/nodo/1?minutes=15"
curl -k "https://localhost:8443/query/api/v1/estado/cama/1?minutes=15"
curl -k "https://localhost:8443/query/api/v1/lecturas/invalidas?limit=100"
curl -k "https://localhost:8443/query/api/v1/nodos/desconectados?minutes=15"
```

### Casos de error controlado

```bash
# limit inválido -> 422 por validación de FastAPI
curl -k "https://localhost:8443/query/api/v1/lecturas/historico/nodo/1?limit=0"

# rango inválido -> 400
curl -k "https://localhost:8443/query/api/v1/lecturas/historico/rango-tiempo?start=2026-03-21T00:00:00Z&end=2026-03-20T00:00:00Z&limit=100"

# nodo no existe -> 404
curl -k "https://localhost:8443/query/api/v1/estado/nodo/9999?minutes=15"
```

## Pruebas locales

```bash
python -m pytest query-monitoring-service/tests
python -m compileall app
```

La suite incluye casos positivos y negativos para históricos, lecturas inválidas, estado de nodos y resumen global.
